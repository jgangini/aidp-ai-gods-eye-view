import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/release"))
import package_candidate as candidate
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/deployment"))
import image_assets as release_loader


COMMIT = "b" * 40
IMAGE_ID = "sha256:" + "a" * 64
PAYLOAD = b"simulated Docker archive\0" * 100000


class Docker:
    def __init__(self, *, identity=IMAGE_ID, platform="linux/amd64", save_status=0):
        self.identity, self.platform, self.save_status = identity, platform, save_status
        self.calls, self.reads = [], []

    def run(self, command, **kwargs):
        self.calls.append(command)
        assert kwargs["check"] is True
        if command[:3] == ["docker", "image", "inspect"]:
            return SimpleNamespace(stdout=self.identity + " " + self.platform)
        assert command[:3] == ["docker", "image", "tag"]

    def popen(self, command, **kwargs):
        self.calls.append(command)
        assert command[:2] == ["docker", "save"]
        assert kwargs["stdout"] == subprocess.PIPE
        assert kwargs["stderr"].writable()
        owner = self

        class Stream(io.BytesIO):
            def read(self, size=-1):
                assert 0 < size <= candidate.CHUNK_SIZE
                owner.reads.append(size)
                return super().read(size)

        class Process:
            stdout = Stream(PAYLOAD)
            def wait(self):
                return owner.save_status
            def poll(self):
                return owner.save_status
            def kill(self):
                pytest.fail("A completed process must not be killed")

        return Process()


@pytest.mark.parametrize("component,name", list(candidate.COMPONENTS.items()))
@pytest.mark.parametrize("release", ["candidate", "v1.2.3"])
def test_packages_only_selected_local_image_with_exact_digest_and_contract(tmp_path, component, name, release):
    docker = Docker()
    path = candidate.package_candidate(component, "built:local", COMMIT, release, tmp_path,
                                       run=docker.run, popen=docker.popen)
    assert path.name == name + "-release.json"
    manifest = json.loads(path.read_text())
    archive = tmp_path / (name + "-image-amd64.tar.gz")
    compressed = archive.read_bytes()
    assert gzip.decompress(compressed) == PAYLOAD
    assert compressed[4:8] == b"\0\0\0\0"
    assert compressed[3] & 8 == 0  # No original filename in the gzip header.
    assert manifest["repository"] == "https://github.com/jgangini/aidp-ai-gods-eye-view"
    assert manifest["image"]["image_id"] == IMAGE_ID
    digest = hashlib.sha256(compressed).hexdigest()
    checked = release_loader._manifest(manifest, name, release, COMMIT, digest)
    assert checked["image_tag"] == name + ":" + COMMIT
    assert checked["image_id"] == IMAGE_ID
    assert len(docker.reads) >= 3
    assert ["docker", "image", "tag", IMAGE_ID, name + ":" + COMMIT] in docker.calls
    assert ["docker", "save", name + ":" + COMMIT] in docker.calls
    assert not any(command[1] in {"build", "pull", "push", "load"} for command in docker.calls)


def test_gzip_is_deterministic_for_the_same_docker_archive(tmp_path):
    results = []
    for name in ("first", "second"):
        docker = Docker()
        path = candidate.package_candidate("api", "built:local", COMMIT, "candidate", tmp_path / name,
                                           run=docker.run, popen=docker.popen)
        results.append((path.parent / json.loads(path.read_text())["image"]["asset_name"]).read_bytes())
    assert results[0] == results[1]


@pytest.mark.parametrize("changes", [
    {"component": "portal"}, {"commit": "b" * 39}, {"commit": "B" * 40},
    {"release": "main"}, {"release": "v1.2.3-rc1"}, {"release": "v01.2.3"},
    {"image": "--all"}, {"image": "built:tag\n--all"}, {"image": ""},
])
def test_invalid_requests_do_not_call_docker_or_create_outputs(tmp_path, changes):
    docker = Docker()
    values = dict(component="api", image="built:local", commit=COMMIT, release="candidate", output=tmp_path / "absent")
    with pytest.raises(ValueError):
        candidate.package_candidate(**(values | changes), run=docker.run, popen=docker.popen)
    assert docker.calls == [] and not values["output"].exists()


@pytest.mark.parametrize("identity,platform", [("not-a-digest", "linux/amd64"),
    ("sha256:" + "a" * 63, "linux/amd64"), (IMAGE_ID, "linux/arm64"), (IMAGE_ID, "windows/amd64")])
def test_invalid_image_identity_or_platform_cannot_be_tagged_or_saved(tmp_path, identity, platform):
    docker = Docker(identity=identity, platform=platform)
    with pytest.raises(ValueError):
        candidate.package_candidate("viewer", "built:local", COMMIT, "candidate", tmp_path,
                                    run=docker.run, popen=docker.popen)
    assert len(docker.calls) == 1 and not list(tmp_path.iterdir())


def test_failed_docker_save_never_publishes_partial_artifacts(tmp_path):
    docker = Docker(save_status=1)
    with pytest.raises(subprocess.CalledProcessError):
        candidate.package_candidate("gateway", "built:local", COMMIT, "candidate", tmp_path,
                                    run=docker.run, popen=docker.popen)
    assert not list(tmp_path.iterdir())


def test_existing_artifacts_are_preserved_without_calling_docker(tmp_path):
    docker = Docker()
    path = tmp_path / "gods-eye-view-api-release.json"
    path.write_text("keep")
    with pytest.raises(FileExistsError):
        candidate.package_candidate("api", "built:local", COMMIT, "candidate", tmp_path,
                                    run=docker.run, popen=docker.popen)
    assert path.read_text() == "keep" and not docker.calls


@pytest.mark.parametrize("changed_inspection", [2, 3])
def test_tag_drift_before_or_during_export_never_publishes_artifacts(tmp_path, changed_inspection):
    class ChangingDocker(Docker):
        inspections = 0
        def run(self, command, **kwargs):
            if command[:3] == ["docker", "image", "inspect"]:
                self.inspections += 1
                if self.inspections == changed_inspection:
                    self.identity = "sha256:" + "c" * 64
            return super().run(command, **kwargs)

    docker = ChangingDocker()
    with pytest.raises(ValueError, match="image|Image"):
        candidate.package_candidate("api", "built:local", COMMIT, "candidate", tmp_path,
                                    run=docker.run, popen=docker.popen)
    assert not list(tmp_path.iterdir())


def test_stream_failure_reaps_export_process_and_removes_partial_archive(tmp_path):
    docker = Docker()
    lifecycle = []
    class BrokenStream(io.BytesIO):
        def read(self, size=-1):
            raise OSError("fixture stream failure")
    class Process:
        stdout = BrokenStream()
        def poll(self):
            return None
        def kill(self):
            lifecycle.append("killed")
        def wait(self):
            lifecycle.append("waited")
            return 1

    with pytest.raises(OSError, match="stream failure"):
        candidate.package_candidate("api", "built:local", COMMIT, "candidate", tmp_path,
                                    run=docker.run, popen=lambda *_args, **_kwargs: Process())
    assert lifecycle == ["killed", "waited"]
    assert not list(tmp_path.iterdir())


def test_candidate_artifacts_do_not_unlock_stable_deployment(monkeypatch):
    class NoNetwork:
        def send(self, *_args, **_kwargs):
            pytest.fail("A candidate must be rejected before release lookup")
    with pytest.raises(ValueError, match="stable release"):
        release_loader.inspect_release({"inputs": {"release_tag": "candidate", "source_commit_sha": COMMIT}},
            {"release_download_token": "test-only-token"}, client=NoNetwork())
