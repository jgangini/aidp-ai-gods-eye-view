from pathlib import Path
import hashlib
import io
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts/deployment"))
from image_assets_vm import load_images, validate_assets


def descriptors(content=b"verified image archive"):
    return [{"component": component, "object_name": "releases/" + "a" * 40 + "/" + prefix + "-image-amd64.tar.gz",
        "archive_sha256": hashlib.sha256(content).hexdigest(), "image_id": "sha256:" + "c" * 64, "image_tag": prefix + ":" + "a" * 40}
        for component, prefix in (("api", "gods-eye-view-api"), ("viewer", "gods-eye-view"), ("gateway", "gods-eye-view-gateway"))]


class Storage:
    def __init__(self, content=b"verified image archive"):
        self.content = content
    def get_object(self, *_args):
        return SimpleNamespace(data=SimpleNamespace(raw=SimpleNamespace(stream=lambda *_a, **_k: [self.content])))


def test_archives_are_verified_before_load_and_platform_checked_after_load():
    calls = []
    def run(args, **kwargs):
        assert Path(args[-1]).read_bytes() == b"verified image archive"
        calls.append(args[:3])
    load_images(Storage(), "namespace", "artifacts", descriptors(), run=run,
        inspect=lambda *_a, **_k: "sha256:" + "c" * 64 + " linux/amd64\n")
    assert calls == [["docker", "load", "--input"]] * 3
    calls.clear()
    with pytest.raises(ValueError, match="SHA-256"):
        load_images(Storage(b"tampered"), "namespace", "artifacts", descriptors(), run=run)
    assert not calls
    with pytest.raises(ValueError, match="platform"):
        load_images(Storage(), "namespace", "artifacts", descriptors(), run=run,
            inspect=lambda *_a, **_k: "sha256:" + "c" * 64 + " linux/arm64")


@pytest.mark.parametrize("change", [{"object_name": "../outside.tar.gz"}, {"image_tag": "foreign:main"}, {"image_id": "mutable:latest"}])
def test_release_scope_cannot_be_replaced_with_other_object_or_image(change):
    values = descriptors()
    values[0] = {**values[0], **change}
    with pytest.raises(ValueError):
        validate_assets(values)
