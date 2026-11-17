"""Source identity and publication closure are checked without native calls."""
import ast
import hashlib
import json
from pathlib import Path

from app.packages.aidp import source_file
from app.packages.catalog import load_package, package_root, PackageError
import pytest

ROOT = Path(__file__).resolve().parents[5]


def test_publication_manifest_is_complete_and_every_source_hash_matches():
    manifest = json.loads((ROOT / "aidp/manifest.json").read_text(encoding="utf-8"))
    assert manifest["module_id"] == "gods_eye_view"
    assert manifest["publication_root"] == "/Workspace/medallion/gods_eye_view"
    assert {item["workspace_path"] for item in manifest["assets"]} == {
        manifest["publication_root"] + "/" + path for path in (
            "10_bronze/social_network.py", "10_bronze/sensor_stream.py", "40_report/ai_gods_eye_view.py")}
    sources = set()
    for asset in manifest["assets"]:
        assert asset["generated"] is True and asset["source"] is None
        assert asset["assembly_sources"] and len(asset["assembly_sources"]) == len(set(asset["assembly_sources"]))
        sources.update(asset["assembly_sources"])
    sources.add(manifest["resources"]["definition_source"])
    assert sources == set(manifest["source_hashes"])
    for path, expected in manifest["source_hashes"].items():
        assert hashlib.sha256(source_file(ROOT, path).read_bytes()).hexdigest() == expected, path
        ast.parse(source_file(ROOT, path).read_text(encoding="utf-8"))
    resources = manifest["resources"]
    assert len(resources["workflows"]) == 2 and len(resources["compute"]) == 4
    assert len(set(resources["compute"])) == 4


def test_product_package_rejects_other_modules_and_validates_native_program_bytes():
    assert load_package("gods_eye_view").lab_id == "gods_eye_view"
    for name in ("ai_data_governance", "ai_market_intelligence", "banking", "../secret"):
        with pytest.raises(PackageError):
            package_root(name)
