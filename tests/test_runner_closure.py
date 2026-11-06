"""Keep the hook archive inside the actual Deploy Studio source limits."""
import json
from pathlib import Path, PurePosixPath
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_runner_archive_is_bounded_and_excludes_viewer_ui_and_corpus_payloads():
    manifest = json.loads((ROOT / "terraform/deploy-studio.json").read_text(encoding="utf-8"))
    roots = [PurePosixPath(manifest["terraform"]["path"]),
        PurePosixPath(manifest["preflight"]["entrypoint"]).parent,
        PurePosixPath(manifest["post_apply"]["entrypoint"]).parent,
        *(PurePosixPath(name) for name in manifest["post_apply"]["include_paths"])]
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    selected = [PurePosixPath(name) for name in tracked if name and any(
        PurePosixPath(name) == parent or parent in PurePosixPath(name).parents for parent in roots)]
    assert selected and len(selected) <= 250
    assert sum((ROOT / str(path)).stat().st_size for path in selected) <= 10 * 1024 * 1024
    for path in selected:
        assert not {".oci", ".terraform", "__pycache__", "media", "posts", "evaluation", "frontend", ".upstream"} & set(path.parts), path
    assert PurePosixPath(manifest["preflight"]["entrypoint"]) in selected
    assert PurePosixPath(manifest["post_apply"]["entrypoint"]) in selected
    assert len(manifest["post_apply"]["include_paths"]) <= 20


def test_runner_declares_private_assets_without_hook_tokens():
    manifest = json.loads((ROOT / "terraform/deploy-studio.json").read_text(encoding="utf-8"))
    prefixes = {"gods-eye-view-api", "gods-eye-view", "gods-eye-view-gateway"}
    names = {prefix + suffix for prefix in prefixes for suffix in ("-release.json", "-image-amd64.tar.gz")}
    for phase in ("preflight", "post_apply"):
        assets = manifest[phase]["release_assets"]
        assert len(assets) == 6 and {item["name"] for item in assets} == names
        assert sum(item["max_bytes"] for item in assets) <= 8 * 1024 ** 3
        for item in assets:
            assert 0 < item["max_bytes"] <= 4 * 1024 ** 3
            assert item["download"] == (phase == "post_apply" or item["name"].endswith(".json"))
        assert "release_download_token" not in manifest[phase]["secret_inputs"]
    assert manifest["preflight"]["secret_inputs"] == []
    assert set(manifest["post_apply"]["secret_inputs"]) == {"tls_certificate", "tls_key"}
