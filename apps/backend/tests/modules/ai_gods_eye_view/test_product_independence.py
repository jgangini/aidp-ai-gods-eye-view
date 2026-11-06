"""Load the product from its checkout with no monolith process or sibling paths."""
import ast
from pathlib import Path

from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.packages.catalog import load_package, package_catalog

ROOT = Path(__file__).resolve().parents[5]


def test_composition_is_lazy_health_is_runnable_and_has_no_installation_surface(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Importing/starting unconfigured product must not contact OCI")
    monkeypatch.setattr("app.main.IdentityClient", fail)
    monkeypatch.setattr("app.main.AidpClient", fail)
    app = create_app(Settings(gods_eye_view_enabled=False,
        session_secret_file=str(tmp_path / "session.key"), aidp_settings_file=str(tmp_path / "settings.json")))
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status":"ok", "product":"gods_eye_view"}
        assert client.get("/api/gods-eye-view/snapshot").status_code == 401
        assert client.post("/api/admin/gods-eye-view/module/deploy").status_code == 404
        assert client.get("/api/admin/gods-eye-view/module").status_code == 404
        assert client.post("/api/admin/login").status_code == 404


def test_active_composition_and_transport_have_no_other_product_imports():
    files = [ROOT / "apps/backend/app" / path for path in (
        "main.py", "config.py", "services/oci/identity.py", "services/oci/aidp.py")]
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not any(name in (node.module or "") for name in (
                    "ai_data_governance", "ai_market_intelligence", "kits", "autonomous")), path
    assert [item.lab_id for item in package_catalog()] == ["gods_eye_view"]
    assert load_package("gods_eye_view").runtime_files
