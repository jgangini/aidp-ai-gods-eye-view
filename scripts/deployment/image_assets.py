"""Stage verified private release images without delivering GitHub credentials to a VM."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

REPOSITORY = "https://github.com/jgangini/aidp-ai-gods-eye-view"
API = "https://api.github.com/repos/jgangini/aidp-ai-gods-eye-view"
COMPONENTS = {"api": "gods-eye-view-api", "viewer": "gods-eye-view", "gateway": "gods-eye-view-gateway"}
ALLOWED_HOSTS = frozenset({"api.github.com", "github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"})
MAX_IMAGE_BYTES = 4 * 1024 ** 3
MAX_MANIFEST_BYTES = 65536
MAX_METADATA_BYTES = 2 * 1024 ** 2
HANDOFF_IMAGE_LIMITS = {"gods-eye-view-api": 512 * 1024 ** 2,
    "gods-eye-view": 1024 ** 3, "gods-eye-view-gateway": 128 * 1024 ** 2}
SHA = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
TAG = re.compile(r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")


def _url(url):
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS
                or parsed.port not in (None, 443) or parsed.username or parsed.password or parsed.fragment):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError("Release download destination is not allowed") from None
    return parsed


def _download(client, url, token, destination, maximum, *, digest=None, size=None, accept="application/octet-stream"):
    """Follow at most five approved redirects; bearer credentials never cross hosts."""
    authorized_host = _url(url).hostname
    auth_allowed = authorized_host == "api.github.com"
    for attempt in range(6):
        parsed = _url(url)
        headers = {"Accept": accept, "Accept-Encoding": "identity", "User-Agent": "aidp-ai-gods-eye-view-runner"}
        if auth_allowed and parsed.hostname == authorized_host:
            headers["Authorization"] = "Bearer " + token
        # Build an independent request so injected client defaults/cookies/auth cannot leak.
        request = httpx.Request("GET", url, headers=headers,
            extensions={"timeout": {"connect": 10.0, "read": 60.0, "write": 60.0, "pool": 10.0}})
        try:
            response = client.send(request, stream=True, follow_redirects=False, auth=None)
            try:
                if response.status_code in {301, 302, 303, 307, 308}:
                    if attempt == 5 or not response.headers.get("location"):
                        raise ValueError("Release download redirect limit exceeded")
                    target = urljoin(url, response.headers["location"])
                    next_host = _url(target).hostname
                    if next_host != parsed.hostname:
                        auth_allowed = False
                    url = target
                    continue
                if response.status_code != 200:
                    raise ValueError("Private release asset is unavailable or unauthorized")
                if response.headers.get("content-encoding", "identity") not in {"", "identity"}:
                    raise ValueError("Unexpected release transfer encoding")
                total, checksum = 0, hashlib.sha256()
                with destination.open("wb") as output:
                    for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                        total += len(chunk)
                        if total > maximum or (size is not None and total > size):
                            raise ValueError("Release asset exceeds its size limit")
                        checksum.update(chunk)
                        output.write(chunk)
                if size is not None and total != size:
                    raise ValueError("Release asset size does not match metadata")
                if digest is not None and checksum.hexdigest() != digest:
                    raise ValueError("Release asset checksum mismatch")
                return
            finally:
                response.close()
        except httpx.HTTPError:
            raise ValueError("Private release transfer failed") from None
    raise ValueError("Release download redirect limit exceeded")


def _json(client, url, token, root, name):
    destination = root / name
    _download(client, url, token, destination, MAX_METADATA_BYTES, accept="application/vnd.github+json")
    try:
        result = json.loads(destination.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        raise ValueError("Invalid release metadata") from None
    if not isinstance(result, dict):
        raise ValueError("Invalid release metadata")
    return result


def _tag_commit(client, token, root, tag, commit):
    item = _json(client, API + "/git/ref/tags/" + tag, token, root, "ref.json")
    if item.get("ref") != "refs/tags/" + tag:
        raise ValueError("Release tag identity does not match")
    target = item.get("object")
    for depth in range(6):
        if not isinstance(target, dict) or not isinstance(target.get("sha"), str) or not SHA.fullmatch(target["sha"]):
            raise ValueError("Invalid release tag target")
        if target.get("type") == "commit":
            if target["sha"] != commit:
                raise ValueError("Release tag does not match the selected source SHA")
            return
        if target.get("type") != "tag" or depth == 5:
            raise ValueError("Unsupported or excessively nested release tag")
        annotated = _json(client, API + "/git/tags/" + target["sha"], token, root, "tag.json")
        if annotated.get("sha") != target["sha"]:
            raise ValueError("Annotated release tag identity does not match")
        target = annotated.get("object")


def _assets(release, tag):
    release_id = release.get("id")
    if (type(release_id) is not int or release_id <= 0 or release.get("url") != API + "/releases/" + str(release_id)
            or release.get("html_url") != REPOSITORY + "/releases/tag/" + tag
            or release.get("tag_name") != tag or release.get("immutable") is not True
            or release.get("draft") is not False or release.get("prerelease") is not False):
        raise ValueError("Selected release is not the exact immutable stable product release")
    assets = release.get("assets")
    if not isinstance(assets, list) or len(assets) != 6:
        raise ValueError("Release must contain exactly six component assets")
    selected = {}
    for component in COMPONENTS.values():
        for suffix, limit in (("-release.json", MAX_MANIFEST_BYTES), ("-image-amd64.tar.gz", MAX_IMAGE_BYTES)):
            name = component + suffix
            matches = [item for item in assets if isinstance(item, dict) and item.get("name") == name]
            if len(matches) != 1:
                raise ValueError("Required release asset is missing or ambiguous")
            asset = matches[0]
            asset_id, size = asset.get("id"), asset.get("size")
            digest = asset.get("digest")
            if (type(asset_id) is not int or asset_id <= 0 or type(size) is not int or not 0 < size <= limit
                    or not isinstance(digest, str) or not digest.startswith("sha256:")
                    or not SHA256.fullmatch(digest[7:]) or asset.get("state") != "uploaded"
                    or asset.get("url") != API + "/releases/assets/" + str(asset_id)):
                raise ValueError("Release asset identity, size or digest is invalid")
            selected[name] = {"url": asset["url"], "size": size, "sha256": digest[7:], "limit": limit}
    if len({item["url"] for item in selected.values()}) != len(selected):
        raise ValueError("Release asset IDs must be distinct")
    return selected


def _manifest(document, component, tag, commit, archive_sha256):
    if not isinstance(document, dict):
        raise ValueError("Invalid release image manifest")
    image = document.get("image")
    if (type(document.get("schema_version")) is not int or document.get("schema_version") != 1
            or type(document.get("updater_protocol")) is not int or document.get("updater_protocol") != 1
            or document.get("repository") != REPOSITORY or document.get("release") != tag
            or document.get("commit_sha") != commit or not isinstance(image, dict)
            or image.get("platform") != "linux/amd64" or image.get("asset_name") != component + "-image-amd64.tar.gz"
            or image.get("sha256") != archive_sha256 or image.get("image_tag") != component + ":" + commit
            or not isinstance(image.get("image_id"), str) or not image["image_id"].startswith("sha256:")
            or not SHA256.fullmatch(image["image_id"][7:])):
        raise ValueError("Release image manifest does not match the selected product, SHA or archive")
    return image


def _verify_existing(storage, namespace, bucket, name, expected, size, head):
    headers = {key.lower(): str(value) for key, value in head.headers.items()}
    metadata = headers.get("opc-meta-archive-sha256")
    if metadata is not None:
        if metadata != expected or headers.get("content-length") != str(size):
            raise ValueError("Existing release object conflicts with the selected archive")
        return
    response = storage.get_object(namespace, bucket, name)
    data = response.data
    try:
        raw = getattr(data, "raw", None)
        chunks = raw.stream(1024 * 1024, decode_content=False) if raw is not None else (data.content,)
        total, checksum = 0, hashlib.sha256()
        for chunk in chunks:
            total += len(chunk)
            if total > size:
                raise ValueError("Existing release object conflicts with the selected archive")
            checksum.update(chunk)
        if total != size or checksum.hexdigest() != expected:
            raise ValueError("Existing release object conflicts with the selected archive")
    finally:
        if callable(getattr(data, "close", None)):
            data.close()


def _upload(storage, namespace, bucket, name, path, digest, size):
    try:
        existing = storage.head_object(namespace, bucket, name)
    except Exception as error:
        if getattr(error, "status", None) != 404:
            raise
    else:
        _verify_existing(storage, namespace, bucket, name, digest, size, existing)
        return
    try:
        with path.open("rb") as stream:
            storage.put_object(namespace, bucket, name, stream, if_none_match="*",
                content_type="application/gzip", opc_meta={"archive-sha256": digest})
    except Exception as error:
        if getattr(error, "status", None) != 412:
            raise
        existing = storage.head_object(namespace, bucket, name)
        _verify_existing(storage, namespace, bucket, name, digest, size, existing)


def _selection_inputs(context, secrets):
    inputs = context["inputs"]
    tag, commit = inputs.get("release_tag"), inputs.get("source_commit_sha")
    token = secrets.get("release_download_token")
    if not isinstance(tag, str) or not TAG.fullmatch(tag) or not isinstance(commit, str) or not SHA.fullmatch(commit):
        raise ValueError("A stable release tag and exact source SHA are required")
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,4096}", token):
        raise ValueError("A private release download credential is required in runner secret inputs")
    return tag, commit, token


def _inspect(client, root, tag, commit, token):
    release = _json(client, API + "/releases/tags/" + tag, token, root, "release.json")
    selected = _assets(release, tag)
    _tag_commit(client, token, root, tag, commit)
    descriptors = []
    for key, component in COMPONENTS.items():
        manifest_name, archive_name = component + "-release.json", component + "-image-amd64.tar.gz"
        asset = selected[manifest_name]
        _download(client, asset["url"], token, root / manifest_name, asset["limit"], digest=asset["sha256"], size=asset["size"])
        try:
            document = json.loads((root / manifest_name).read_text(encoding="utf-8"))
        except (ValueError, UnicodeError):
            raise ValueError("Invalid release image manifest") from None
        image = _manifest(document, component, tag, commit, selected[archive_name]["sha256"])
        descriptors.append({"component": key, "object_name": "releases/" + commit + "/" + archive_name,
            "archive_sha256": selected[archive_name]["sha256"], "image_id": image["image_id"], "image_tag": image["image_tag"]})
    return descriptors, selected


def inspect_release(context, secrets, client=None):
    """Read-only preflight of exact release metadata and manifest bytes, not image bytes."""
    tag, commit, token = _selection_inputs(context, secrets)
    owned_client = client is None
    client = client or httpx.Client(trust_env=False)
    try:
        with tempfile.TemporaryDirectory(prefix="gods-eye-view-release-inspect-") as directory:
            descriptors, _ = _inspect(client, Path(directory), tag, commit, token)
            return descriptors
    finally:
        if owned_client:
            client.close()


def stage_images(context, secrets, storage, client=None):
    """Verify all archive bytes and return protected-object descriptors, never runner secrets."""
    tag, commit, token = _selection_inputs(context, secrets)
    outputs = context["terraform_outputs"]
    namespace, bucket = outputs.get("objectstorage_namespace"), outputs.get("artifacts_bucket_name")
    if (not isinstance(namespace, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", namespace)
            or not isinstance(bucket, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,256}", bucket)):
        raise ValueError("The selected artifacts bucket and namespace are required")
    owned_client = client is None
    client = client or httpx.Client(trust_env=False)
    try:
        with tempfile.TemporaryDirectory(prefix="gods-eye-view-release-") as directory:
            root = Path(directory)
            descriptors, selected = _inspect(client, root, tag, commit, token)
            for descriptor in descriptors:
                name = descriptor["object_name"].rsplit("/", 1)[1]
                asset = selected[name]
                _download(client, asset["url"], token, root / name, asset["limit"], digest=asset["sha256"], size=asset["size"])
            # Validate every component before any storage mutation.
            for descriptor in descriptors:
                name = descriptor["object_name"].rsplit("/", 1)[1]
                _upload(storage, namespace, bucket, descriptor["object_name"], root / name,
                    descriptor["archive_sha256"], selected[name]["size"])
            return descriptors
    finally:
        if owned_client:
            client.close()


def _local_path(value):
    """Reject symlinks/reparse points, including directory components, before opening."""
    try:
        if not isinstance(value, str) or not value or "\x00" in value:
            raise ValueError()
        path = Path(value)
        if not path.is_absolute() or ".." in path.parts:
            raise ValueError()
        initial = None
        for component in (path, *path.parents):
            info = component.lstat()
            if (stat.S_ISLNK(info.st_mode)
                    or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
                raise ValueError()
            if initial is None:
                initial = info
        if not stat.S_ISREG(initial.st_mode):
            raise ValueError()
        return path, initial
    except (OSError, ValueError):
        raise ValueError("A local release asset must be an absolute regular file without symbolic links") from None


def _handoff_metadata(context, *, require_archives):
    """Revalidate the trusted runner handoff against the exact product/source bindings."""
    if not isinstance(context, dict) or type(require_archives) is not bool:
        raise ValueError("Release handoff context and verification mode are invalid")
    inputs, source, handoff = (context.get(name) for name in ("inputs", "source", "release_assets"))
    if not all(isinstance(value, dict) for value in (inputs, source, handoff)):
        raise ValueError("Release handoff, source and inputs are required")
    tag, commit = inputs.get("release_tag"), inputs.get("source_commit_sha")
    if (not isinstance(tag, str) or not TAG.fullmatch(tag) or not isinstance(commit, str) or not SHA.fullmatch(commit)
            or source.get("repository") != REPOSITORY or source.get("commit_sha") != commit or source.get("ref") != tag
            or set(handoff) != {"schema_version", "repository", "ref", "commit_sha", "release_id", "assets"}
            or type(handoff.get("schema_version")) is not int or handoff["schema_version"] != 1
            or handoff.get("repository") != REPOSITORY or handoff.get("ref") != tag
            or handoff.get("commit_sha") != commit or type(handoff.get("release_id")) is not int
            or handoff["release_id"] <= 0):
        raise ValueError("Release handoff does not match the selected product, stable tag or source SHA")
    expected = {component + suffix: limit for component in COMPONENTS.values()
        for suffix, limit in (("-release.json", MAX_MANIFEST_BYTES), ("-image-amd64.tar.gz", HANDOFF_IMAGE_LIMITS[component]))}
    assets = handoff.get("assets")
    if not isinstance(assets, dict) or set(assets) != set(expected):
        raise ValueError("Release handoff must contain exactly six component assets")
    selected, ids = {}, set()
    for name, maximum in expected.items():
        asset = assets[name]
        if (not isinstance(asset, dict) or not {"asset_id", "size", "sha256"}.issubset(asset)
                or set(asset) - {"asset_id", "size", "sha256", "path"}
                or type(asset.get("asset_id")) is not int or asset["asset_id"] <= 0 or asset["asset_id"] in ids
                or type(asset.get("size")) is not int or not 0 < asset["size"] <= maximum
                or not isinstance(asset.get("sha256"), str) or not SHA256.fullmatch(asset["sha256"])):
            raise ValueError("Release handoff asset identity, size or checksum is invalid")
        ids.add(asset["asset_id"])
        if name.endswith(".json") or require_archives or "path" in asset:
            path, info = _local_path(asset.get("path"))
            if info.st_size != asset["size"]:
                raise ValueError("Local release asset size does not match handoff metadata")
        else:
            path = None
        selected[name] = {**asset, "path": path, "limit": maximum}
    return tag, commit, selected


def _copy_local(asset, destination):
    """Verify a bounded snapshot so later source-path changes cannot affect uploads."""
    path, initial = _local_path(str(asset["path"]))
    try:
        flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(os.open(path, flags), "rb") as source:
            opened = os.fstat(source.fileno())
            if ((opened.st_dev, opened.st_ino) != (initial.st_dev, initial.st_ino)
                    or not stat.S_ISREG(opened.st_mode) or opened.st_size != asset["size"]):
                raise ValueError("Local release asset changed before verification")
            total, checksum = 0, hashlib.sha256()
            with destination.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    total += len(chunk)
                    if total > asset["size"] or total > asset["limit"]:
                        raise ValueError("Local release asset exceeds its size limit")
                    checksum.update(chunk)
                    output.write(chunk)
            after = os.fstat(source.fileno())
            if total != asset["size"] or after.st_size != opened.st_size or after.st_mtime_ns != opened.st_mtime_ns:
                raise ValueError("Local release asset changed during verification")
            if checksum.hexdigest() != asset["sha256"]:
                raise ValueError("Local release asset checksum mismatch")
    except OSError:
        raise ValueError("Local release asset could not be read safely") from None


def _handoff_descriptors(root, selected, tag, commit):
    descriptors = []
    for key, component in COMPONENTS.items():
        try:
            document = json.loads((root / (component + "-release.json")).read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError):
            raise ValueError("Invalid local release image manifest") from None
        archive_name = component + "-image-amd64.tar.gz"
        image = _manifest(document, component, tag, commit, selected[archive_name]["sha256"])
        descriptors.append({"component": key, "object_name": "releases/" + commit + "/" + archive_name,
            "archive_sha256": selected[archive_name]["sha256"], "image_id": image["image_id"], "image_tag": image["image_tag"]})
    return descriptors


@contextmanager
def _verified_handoff(context, *, require_archives):
    tag, commit, selected = _handoff_metadata(context, require_archives=require_archives)
    with tempfile.TemporaryDirectory(prefix="gods-eye-view-handoff-") as directory:
        root = Path(directory)
        for name, asset in selected.items():
            if asset["path"] is not None:
                _copy_local(asset, root / name)
        yield root, _handoff_descriptors(root, selected, tag, commit), selected


def inspect_handoff(context, *, require_archives=False):
    """Verify all supplied bytes without network/storage; require all TARs before install."""
    with _verified_handoff(context, require_archives=require_archives) as (_, descriptors, _selected):
        return descriptors


def stage_handoff(context, storage):
    """Verify all six local assets before conditionally staging the three archive snapshots."""
    outputs = context.get("terraform_outputs") if isinstance(context, dict) else None
    if not isinstance(outputs, dict):
        raise ValueError("The selected artifacts bucket and namespace are required")
    namespace, bucket = outputs.get("objectstorage_namespace"), outputs.get("artifacts_bucket_name")
    if (not isinstance(namespace, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", namespace)
            or not isinstance(bucket, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,256}", bucket)):
        raise ValueError("The selected artifacts bucket and namespace are required")
    with _verified_handoff(context, require_archives=True) as (root, descriptors, selected):
        for descriptor in descriptors:
            name = descriptor["object_name"].rsplit("/", 1)[1]
            _upload(storage, namespace, bucket, descriptor["object_name"], root / name,
                descriptor["archive_sha256"], selected[name]["size"])
        return descriptors
