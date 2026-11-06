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
