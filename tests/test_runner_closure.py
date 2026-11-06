"""Keep the hook archive inside the actual Deploy Studio source limits."""
import json
from collections import Counter
from pathlib import Path, PurePosixPath
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_form_schema2_defines_the_complete_layout_without_legacy_inference():
    manifest = json.loads((ROOT / "terraform/deploy-studio.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 2
    form = manifest["form"]
    groups = form["groups"]
    assert groups[0]["id"] == "credentials"
    assert [(item["kind"], item["name"]) for item in groups[0]["items"]] == [
        ("control", "oci_config"), ("control", "oci_key")]
    assert len({group["id"] for group in groups}) == len(groups)
    assert all(group["title"].strip() and group["items"] for group in groups)
    services = next(group for group in groups if group["id"] == "services")
    assert [item["name"] for item in services["items"]] == [
        "oci_region", "compartment_mode", "new_compartment", "existing_compartment"]
    assert services["items"][0]["span"] == 2
    references = Counter((item["kind"], item["name"]) for group in groups for item in group["items"])
    expected = {(kind, field["name"]) for kind, fields in (("field", form["fields"]), ("file", form.get("files", [])))
        for field in fields}
    controls = {"oci_config", "oci_key", "oci_region", "compartment_mode", "new_compartment", "existing_compartment"}
    assert references == Counter({reference: 1 for reference in expected | {("control", name) for name in controls}})
    for group in groups:
        for item in group["items"]:
            assert item.get("span", 1) in (1, 2)
            if item["kind"] == "control":
                assert item["label"].strip()
                if item["name"] == "compartment_mode":
                    assert [option["value"] for option in item["options"]] == manifest["capabilities"]["compartment_modes"]
                    assert all(option["label"].strip() for option in item["options"])


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
    assert manifest["post_apply"]["secret_inputs"] == []


def test_identity_domain_uses_the_active_domain_selector_with_an_ocid_value():
    import re
    manifest = json.loads((ROOT / "terraform/deploy-studio.json").read_text(encoding="utf-8"))
    field = next(item for item in manifest["form"]["fields"] if item["name"] == "identity_domain_id")
    assert field["type"] == "select" and field["options_source"] == "oci_identity_domains"
    assert field["required"] is True
    assert re.fullmatch(field["pattern"], "ocid1.domain.oc1..selected")
    assert not re.fullmatch(field["pattern"], "domain-name")
