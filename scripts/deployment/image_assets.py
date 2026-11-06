"""Stage verified private release images without delivering GitHub credentials to a VM."""
from __future__ import annotations

import hashlib
import json
import re
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
