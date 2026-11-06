"""Exercise authenticated release transfer and conditional storage without network or cloud."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("image_assets", ROOT / "scripts/deployment/image_assets.py")
images = importlib.util.module_from_spec(spec)
spec.loader.exec_module(images)
COMMIT, TAG, TOKEN = "a" * 40, "v1.2.3", "github_pat_runner_only_test"
CONTEXT = {"inputs": {"release_tag": TAG, "source_commit_sha": COMMIT},
           "terraform_outputs": {"objectstorage_namespace": "namespace", "artifacts_bucket_name": "artifacts"}}


class StorageError(Exception):
    def __init__(self, status):
        self.status = status


class Storage:
    def __init__(self):
        self.objects, self.uploads, self.downloads = {}, [], []
        self.collide = None

    def head_object(self, namespace, bucket, name):
        assert (namespace, bucket) == ("namespace", "artifacts")
        if name not in self.objects:
            raise StorageError(404)
        body, metadata = self.objects[name]
        return SimpleNamespace(headers={"content-length": str(len(body)), **metadata})

    def get_object(self, namespace, bucket, name):
        self.downloads.append(name)
        return SimpleNamespace(data=SimpleNamespace(content=self.objects[name][0]))

    def put_object(self, namespace, bucket, name, body, **kwargs):
        assert (namespace, bucket) == ("namespace", "artifacts")
        assert kwargs["if_none_match"] == "*"
        data = body.read()
        if self.collide:
            self.objects[name] = self.collide(data, kwargs)
            raise StorageError(412)
        if name in self.objects:
            raise StorageError(412)
        self.objects[name] = (data, {"opc-meta-archive-sha256": kwargs["opc_meta"]["archive-sha256"]})
        self.uploads.append(name)
        return SimpleNamespace(headers={"etag":"new"})


class Release:
    def __init__(self):
        self.requests, self.redirects, self.raw_overrides = [], {}, {}
        self.bodies, self.asset_names, self.manifests = {}, {}, {}
        self.release = {"id": 100, "url": images.API + "/releases/100",
            "html_url": images.REPOSITORY + "/releases/tag/" + TAG,
            "tag_name": TAG, "immutable": True, "draft": False, "prerelease": False, "assets": []}
        self.ref = {"ref":"refs/tags/" + TAG, "object":{"type":"commit", "sha":COMMIT}}
        self.tags = {}
        number = 1
        for key, component in images.COMPONENTS.items():
            archive = ("archive-" + key).encode()
            archive_name = component + "-image-amd64.tar.gz"
            document = {"schema_version":1,"updater_protocol":1,"repository":images.REPOSITORY,
                "release":TAG,"commit_sha":COMMIT,"image":{"asset_name":archive_name,
                    "sha256":hashlib.sha256(archive).hexdigest(),"platform":"linux/amd64",
                    "image_tag":component + ":" + COMMIT,"image_id":"sha256:" + hashlib.sha256(key.encode()).hexdigest()}}
            self.manifests[key] = document
            for name, body in ((component + "-release.json", json.dumps(document).encode()), (archive_name, archive)):
                self.asset_names[name] = number
                self.bodies[number] = body
                self.release["assets"].append({"id":number,"name":name,"url":images.API + "/releases/assets/" + str(number),
                    "digest":"sha256:" + hashlib.sha256(body).hexdigest(),"size":len(body),"state":"uploaded"})
                number += 1

    def manifest_change(self, key, change):
        change(self.manifests[key])
        asset_id = self.asset_names[images.COMPONENTS[key] + "-release.json"]
        self.bodies[asset_id] = json.dumps(self.manifests[key]).encode()
        item = next(item for item in self.release["assets"] if item["id"] == asset_id)
        item.update(size=len(self.bodies[asset_id]), digest="sha256:" + hashlib.sha256(self.bodies[asset_id]).hexdigest())

    def handle(self, request):
        self.requests.append(request)
        if request.url.host == "api.github.com":
            assert request.headers["authorization"] == "Bearer " + TOKEN
            assert "cookie" not in request.headers
            if request.url.path.endswith("/releases/tags/" + TAG):
                return httpx.Response(200, json=self.release)
            if request.url.path.endswith("/git/ref/tags/" + TAG):
                return httpx.Response(200, json=self.ref)
            if "/git/tags/" in request.url.path:
                return httpx.Response(200, json=self.tags[request.url.path.rsplit("/",1)[1]])
            asset_id = int(request.url.path.rsplit("/",1)[1])
            if asset_id in self.redirects:
                return httpx.Response(302, headers={"Location":self.redirects[asset_id]})
            return httpx.Response(200, content=self.raw_overrides.get(asset_id, self.bodies[asset_id]))
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        asset_id = int(request.url.path.rsplit("/",1)[1])
        return httpx.Response(200, content=self.bodies[asset_id])

    def client(self):
        # Poisoned defaults must never be sent to an asset redirect destination.
        return httpx.Client(transport=httpx.MockTransport(self.handle),
            headers={"Authorization":"Bearer inherited-client-secret", "Cookie":"private-client-cookie"})


def stage(release, storage=None, context=CONTEXT):
    storage = storage or Storage()
    with release.client() as client:
        result = images.stage_images(context, {"release_download_token":TOKEN}, storage, client=client)
    return result, storage


def test_success_uses_authenticated_asset_ids_and_returns_only_vm_safe_descriptors(capsys):
    release = Release()
    result, storage = stage(release)
    assert len(result) == len(storage.uploads) == 3
    assert {item["component"] for item in result} == {"api","viewer","gateway"}
    for item in result:
        assert set(item) == {"component","object_name","archive_sha256","image_id","image_tag"}
        component = images.COMPONENTS[item["component"]]
        assert item["object_name"] == f"releases/{COMMIT}/{component}-image-amd64.tar.gz"
        assert item["image_id"] == release.manifests[item["component"]]["image"]["image_id"]
        assert storage.objects[item["object_name"]][1]["opc-meta-archive-sha256"] == item["archive_sha256"]
    assert TOKEN not in json.dumps(result)
    assert TOKEN not in repr(storage.objects)
    assert TOKEN not in str(capsys.readouterr())
    assert len([request for request in release.requests if "/releases/assets/" in request.url.path]) == 6
    assert all("/releases/download/" not in str(request.url) for request in release.requests)


@pytest.mark.parametrize("target", ["repository","commit_sha","release","image_id","image_tag","platform","schema_version"])
def test_forged_manifest_is_rejected_before_any_storage_mutation(target):
    release, storage = Release(), Storage()
    def change(document):
        if target == "image_id": document["image"][target] = "sha256:" + "g" * 64
        elif target in {"image_tag","platform"}: document["image"][target] = "forged"
        elif target == "schema_version": document[target] = True
        else: document[target] = "forged"
    release.manifest_change("gateway", change)
    with pytest.raises(ValueError, match="manifest"):
        stage(release, storage)
    assert storage.uploads == [] and storage.objects == {}


@pytest.mark.parametrize("field,value", [("immutable",False),("draft",True),("prerelease",True),
    ("tag_name","v9.9.9"),("url","https://api.github.com/repos/attacker/product/releases/100"),
    ("html_url","https://github.com/attacker/product/releases/tag/v1.2.3")])
def test_release_identity_and_stability_fail_closed(field, value):
    release = Release()
    release.release[field] = value
    with pytest.raises(ValueError, match="stable"):
        stage(release)


def test_tag_ref_is_resolved_to_exact_commit_including_annotated_tags():
    release = Release()
    release.ref["object"] = {"type":"tag","sha":"b" * 40}
    release.tags["b" * 40] = {"sha":"b" * 40,"object":{"type":"commit","sha":COMMIT}}
    assert len(stage(release)[0]) == 3
    release.tags["b" * 40]["object"]["sha"] = "c" * 40
    with pytest.raises(ValueError, match="source SHA"):
        stage(release)


def test_archive_hash_mismatch_and_manifest_metadata_mismatch_never_upload():
    release, storage = Release(), Storage()
    asset_id = release.asset_names["gods-eye-view-gateway-image-amd64.tar.gz"]
    release.raw_overrides[asset_id] = b"x" * len(release.bodies[asset_id])
    with pytest.raises(ValueError, match="checksum"):
        stage(release, storage)
    assert storage.uploads == []
    release = Release()
    release.raw_overrides[1] = b"x" * len(release.bodies[1])
    with pytest.raises(ValueError, match="checksum"):
        stage(release, storage)
    assert storage.uploads == []


@pytest.mark.parametrize("host", ["objects.githubusercontent.com","release-assets.githubusercontent.com","github.com"])
def test_redirects_to_approved_hosts_strip_default_and_bearer_credentials(host):
    release = Release()
    release.redirects[2] = f"https://{host}/2?signature=private-signed-location"
    result, _ = stage(release)
    redirected = next(request for request in release.requests if request.url.host == host)
    assert "authorization" not in redirected.headers and "cookie" not in redirected.headers
    assert "signature" not in json.dumps(result)


@pytest.mark.parametrize("destination", ["http://release-assets.githubusercontent.com/2", "https://attacker.example/2",
    "https://api.github.com.attacker.example/2", "https://user:password@objects.githubusercontent.com/2",
    "https://objects.githubusercontent.com:8443/2", "https://objects.githubusercontent.com/2#fragment"])
def test_redirect_destinations_are_checked_before_any_request(destination):
    release = Release()
    release.redirects[2] = destination
    with pytest.raises(ValueError, match="destination"):
        stage(release)
    assert all(request.url.host == "api.github.com" for request in release.requests)


def test_private_unauthorized_errors_are_safe_and_token_is_required_before_network():
    release, storage = Release(), Storage()
    with release.client() as client:
        with pytest.raises(ValueError, match="credential") as error:
            images.stage_images(CONTEXT, {}, storage, client=client)
        assert release.requests == []
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(401, text=TOKEN))) as client:
        with pytest.raises(ValueError) as error:
            images.stage_images(CONTEXT, {"release_download_token":TOKEN}, storage, client=client)
        assert TOKEN not in str(error.value)


def test_existing_objects_are_reused_only_with_matching_metadata_or_bytes():
    release, storage = Release(), Storage()
    result, storage = stage(release, storage)
    storage.uploads.clear()
    assert stage(release, storage)[0] == result
    assert storage.uploads == storage.downloads == []
    first = result[0]["object_name"]
    storage.objects[first] = (storage.objects[first][0], {})
    assert stage(release, storage)[0] == result
    assert storage.downloads == [first] and storage.uploads == []
    storage.objects[first] = (b"tampered", {})
    with pytest.raises(ValueError, match="conflicts"):
        stage(release, storage)
    assert storage.objects[first][0] == b"tampered" and storage.uploads == []


@pytest.mark.parametrize("matching", [True,False])
def test_conditional_upload_race_never_overwrites_and_checks_winning_object(matching):
    release, storage = Release(), Storage()
    storage.collide = lambda body, kwargs: (body if matching else b"different", {})
    if matching:
        assert len(stage(release, storage)[0]) == 3
    else:
        with pytest.raises(ValueError, match="conflicts"):
            stage(release, storage)
        assert next(iter(storage.objects.values()))[0] == b"different"
    assert storage.uploads == []


def test_size_limits_and_metadata_digest_format_are_enforced_before_storage(monkeypatch):
    release, storage = Release(), Storage()
    monkeypatch.setattr(images, "MAX_IMAGE_BYTES", 2)
    with pytest.raises(ValueError, match="size"):
        stage(release, storage)
    assert storage.objects == {}
    monkeypatch.setattr(images, "MAX_IMAGE_BYTES", 4 * 1024 ** 3)
    release.release["assets"][0]["digest"] = "md5:" + "a" * 32
    with pytest.raises(ValueError, match="digest"):
        stage(release, storage)
    assert storage.objects == {}


def test_readonly_inspection_needs_no_terraform_outputs_and_downloads_only_manifests():
    release = Release()
    with release.client() as client:
        result = images.inspect_release({"inputs":CONTEXT["inputs"]}, {"release_download_token":TOKEN}, client=client)
    asset_ids = [int(request.url.path.rsplit("/",1)[1]) for request in release.requests if "/releases/assets/" in request.url.path]
    assert asset_ids == [1,3,5]
    assert {item["component"] for item in result} == {"api","viewer","gateway"}
    assert result == stage(Release())[0]
    assert TOKEN not in json.dumps(result)


def test_readonly_inspection_rejects_unauthorized_token_without_echo_or_archive_request():
    requests = []
    def unauthorized(request):
        requests.append(request)
        return httpx.Response(401,text=TOKEN)
    with httpx.Client(transport=httpx.MockTransport(unauthorized)) as client:
        with pytest.raises(ValueError, match="unauthorized") as error:
            images.inspect_release({"inputs":CONTEXT["inputs"]}, {"release_download_token":TOKEN}, client=client)
    assert TOKEN not in str(error.value)
    assert len(requests) == 1 and "/releases/assets/" not in requests[0].url.path


def test_readonly_inspection_checks_manifest_identity_and_metadata_digest():
    release = Release()
    release.manifest_change("viewer",lambda document: document.update(repository="https://github.com/other/product"))
    with release.client() as client:
        with pytest.raises(ValueError,match="manifest"):
            images.inspect_release({"inputs":CONTEXT["inputs"]},{"release_download_token":TOKEN},client=client)
    assert all(not request.url.path.endswith(("/2","/4","/6")) for request in release.requests)
    release = Release()
    release.raw_overrides[1] = b"x" * len(release.bodies[1])
    with release.client() as client:
        with pytest.raises(ValueError,match="checksum"):
            images.inspect_release({"inputs":CONTEXT["inputs"]},{"release_download_token":TOKEN},client=client)


@pytest.mark.parametrize("method", ["inspect","stage"])
def test_unexpected_extra_release_assets_are_rejected(method):
    release = Release()
    release.release["assets"].append({"id":7,"name":"extra-unreviewed-asset.txt"})
    with pytest.raises(ValueError,match="exactly six"):
        if method == "stage":
            stage(release)
        else:
            with release.client() as client:
                images.inspect_release({"inputs":CONTEXT["inputs"]},{"release_download_token":TOKEN},client=client)


def local_handoff(tmp_path, *, archives=False):
    release = Release()
    assets = {}
    for item in release.release["assets"]:
        asset = {"asset_id":item["id"], "size":item["size"], "sha256":item["digest"][7:]}
        if item["name"].endswith(".json") or archives:
            path = tmp_path / item["name"]
            path.write_bytes(release.bodies[item["id"]])
            asset["path"] = str(path)
        assets[item["name"]] = asset
    return {"inputs":copy.deepcopy(CONTEXT["inputs"]),
        "source":{"repository":images.REPOSITORY,"commit_sha":COMMIT,"ref":TAG},
        "release_assets":{"schema_version":1,"repository":images.REPOSITORY,"ref":TAG,
            "commit_sha":COMMIT,"release_id":100,"assets":assets}}


def local_stage_context(tmp_path):
    context = local_handoff(tmp_path, archives=True)
    context["terraform_outputs"] = copy.deepcopy(CONTEXT["terraform_outputs"])
    return context


def no_network(*args, **kwargs):
    raise AssertionError("Local release handoff must not use HTTP or credentials")


def test_local_preflight_validates_three_manifests_with_tar_metadata_only(tmp_path, monkeypatch):
    context = local_handoff(tmp_path)
    monkeypatch.setattr(images.httpx, "Client", no_network)
    monkeypatch.setattr(images, "_download", no_network)
    descriptors = images.inspect_handoff(context)
    assert {item["component"] for item in descriptors} == {"api","viewer","gateway"}
    assert all("path" not in item for name,item in context["release_assets"]["assets"].items() if name.endswith(".tar.gz"))
    assert all(set(item) == {"component","object_name","archive_sha256","image_id","image_tag"} for item in descriptors)
    assert str(tmp_path) not in json.dumps(descriptors)
    with pytest.raises(ValueError,match="regular file"):
        images.inspect_handoff(context,require_archives=True)


def test_local_install_and_stage_verify_all_tar_bytes_without_network(tmp_path, monkeypatch):
    context = local_stage_context(tmp_path)
    monkeypatch.setattr(images.httpx, "Client", no_network)
    monkeypatch.setattr(images, "_download", no_network)
    expected = images.inspect_handoff(context,require_archives=True)
    storage = Storage()
    assert images.stage_handoff(context,storage) == expected
    assert len(storage.uploads) == 3
    storage.uploads.clear()
    assert images.stage_handoff(context,storage) == expected and storage.uploads == []


@pytest.mark.parametrize("location,field,value", [
    ("source","repository","https://github.com/other/product"),
    ("source","commit_sha","b" * 40),
    ("source","ref","v9.9.9"),
    ("inputs","source_commit_sha","b" * 40),
    ("inputs","release_tag","v1.2.3-rc1"),
    ("release_assets","schema_version",True),
    ("release_assets","schema_version",2),
    ("release_assets","repository","https://github.com/other/product"),
    ("release_assets","commit_sha","b" * 40),
    ("release_assets","ref","v9.9.9"),
    ("release_assets","release_id",True),
    ("release_assets","release_id",0),
])
def test_handoff_source_bindings_fail_closed_without_upload(tmp_path, location, field, value):
    context = local_stage_context(tmp_path)
    context[location][field] = value
    storage = Storage()
    with pytest.raises(ValueError,match="handoff"):
        images.stage_handoff(context,storage)
    assert storage.objects == {} and storage.uploads == []


@pytest.mark.parametrize("change", ["missing","extra","duplicate_id","bad_sha","bad_size","unknown_field"])
def test_handoff_has_exact_six_distinct_assets_with_strict_metadata(tmp_path, change):
    context = local_handoff(tmp_path)
    assets = context["release_assets"]["assets"]
    first,second = list(assets)[:2]
    if change == "missing": assets.pop(first)
    elif change == "extra": assets["unreviewed.txt"] = {}
    elif change == "duplicate_id": assets[second]["asset_id"] = assets[first]["asset_id"]
    elif change == "bad_sha": assets[first]["sha256"] = "sha256:" + "a" * 64
    elif change == "bad_size": assets[first]["size"] = True
    else: assets[first]["url"] = "https://untrusted.example/private"
    with pytest.raises(ValueError,match="handoff"):
        images.inspect_handoff(context)


@pytest.mark.parametrize("component,limit", [("gods-eye-view-api",512 * 1024 ** 2),
    ("gods-eye-view",1024 ** 3),("gods-eye-view-gateway",128 * 1024 ** 2)])
def test_handoff_tar_component_caps_apply_to_both_phases(tmp_path, component, limit):
    context = local_stage_context(tmp_path)
    context["release_assets"]["assets"][component + "-image-amd64.tar.gz"]["size"] = limit + 1
    with pytest.raises(ValueError,match="size"):
        images.inspect_handoff(context)
    storage = Storage()
    with pytest.raises(ValueError,match="size"):
        images.stage_handoff(context,storage)
    assert not storage.uploads


@pytest.mark.parametrize("invalid", ["relative","directory","missing"])
def test_local_manifest_paths_are_absolute_regular_existing_files_and_errors_are_private(tmp_path, invalid):
    context = local_handoff(tmp_path)
    asset = context["release_assets"]["assets"]["gods-eye-view-api-release.json"]
    private = tmp_path / "PRIVATE-PATH-MARKER"
    if invalid == "relative": asset["path"] = "PRIVATE-PATH-MARKER.json"
    elif invalid == "directory": private.mkdir(); asset["path"] = str(private)
    else: asset["path"] = str(private)
    with pytest.raises(ValueError,match="regular file") as error:
        images.inspect_handoff(context)
    assert "PRIVATE-PATH-MARKER" not in str(error.value)


def test_local_handoff_rejects_symlink_before_reading_manifest(tmp_path):
    context = local_handoff(tmp_path)
    asset = context["release_assets"]["assets"]["gods-eye-view-api-release.json"]
    link = tmp_path / "linked-manifest.json"
    try:
        link.symlink_to(asset["path"])
    except OSError as error:
        if getattr(error,"winerror",None) == 1314:
            pytest.skip("Host user lacks Windows symlink creation privilege")
        raise
    asset["path"] = str(link)
    with pytest.raises(ValueError,match="symbolic links"):
        images.inspect_handoff(context)


@pytest.mark.parametrize("asset_name", ["gods-eye-view-api-release.json","gods-eye-view-gateway-image-amd64.tar.gz"])
def test_bad_local_bytes_cause_zero_uploads_even_for_the_last_tar(tmp_path, asset_name):
    context = local_stage_context(tmp_path)
    asset = context["release_assets"]["assets"][asset_name]
    Path(asset["path"]).write_bytes(b"x" * asset["size"])
    storage = Storage()
    with pytest.raises(ValueError,match="checksum"):
        images.stage_handoff(context,storage)
    assert storage.uploads == [] and storage.objects == {}
    with pytest.raises(ValueError,match="checksum"):
        images.inspect_handoff(context)


def test_manifest_semantics_are_rechecked_after_local_hash_validation(tmp_path):
    context = local_stage_context(tmp_path)
    asset = context["release_assets"]["assets"]["gods-eye-view-gateway-release.json"]
    path = Path(asset["path"])
    manifest = json.loads(path.read_text())
    manifest["image"]["platform"] = "linux/arm64"
    body = json.dumps(manifest).encode()
    path.write_bytes(body)
    asset.update(size=len(body),sha256=hashlib.sha256(body).hexdigest())
    storage = Storage()
    with pytest.raises(ValueError,match="manifest"):
        images.stage_handoff(context,storage)
    assert storage.uploads == [] and storage.objects == {}


def test_postapply_requires_all_archive_paths_and_detects_size_change(tmp_path):
    context = local_stage_context(tmp_path)
    archive = context["release_assets"]["assets"]["gods-eye-view-gateway-image-amd64.tar.gz"]
    path = archive.pop("path")
    storage = Storage()
    with pytest.raises(ValueError,match="regular file"):
        images.stage_handoff(context,storage)
    archive["path"] = path
    Path(path).write_bytes(b"different-size")
    with pytest.raises(ValueError,match="size"):
        images.stage_handoff(context,storage)
    assert storage.objects == {} and storage.uploads == []


def test_local_staging_preserves_cas_collision_and_never_overwrites(tmp_path):
    context = local_stage_context(tmp_path)
    storage = Storage()
    storage.collide = lambda body,kwargs: (b"conflicting bytes",{})
    with pytest.raises(ValueError,match="conflicts"):
        images.stage_handoff(context,storage)
    assert storage.uploads == []
    assert next(iter(storage.objects.values()))[0] == b"conflicting bytes"


def test_staging_uploads_verified_snapshots_when_original_paths_change_after_validation(tmp_path):
    context = local_stage_context(tmp_path)
    archive = context["release_assets"]["assets"]["gods-eye-view-gateway-image-amd64.tar.gz"]
    original = Path(archive["path"]).read_bytes()
    class MutatingStorage(Storage):
        def put_object(self,*args,**kwargs):
            Path(archive["path"]).write_bytes(b"modified after validation")
            return super().put_object(*args,**kwargs)
    storage = MutatingStorage()
    result = images.stage_handoff(context,storage)
    viewer = next(item for item in result if item["component"] == "gateway")
    assert storage.objects[viewer["object_name"]][0] == original
    assert len(storage.uploads) == 3
