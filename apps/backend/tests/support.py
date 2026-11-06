"""Explicit fake OCI boundaries for deterministic domain/API regression checks."""
from dataclasses import replace
from types import SimpleNamespace

from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app as product_app, LOCAL_COOKIE_NAME, COOKIE_NAME
from app.security import issue_session

ADMIN_OCID = "ocid1.user.oc1..admin-test"


class Identity:
    def __init__(self):
        self.active = True
        self.admin_role = True

    async def gods_eye_view_user(self, user_id):
        if not self.active or user_id not in {"admin", "reader"}:
            return None
        return {"id": user_id, "ocid": ADMIN_OCID if user_id == "admin" else "ocid1.user.oc1..reader-test",
                "email": user_id + "@example.test", "active": True}

    async def has_aidp_admin_role(self, user_id, aidp):
        return self.admin_role and user_id == "admin"


def create_app(settings):
    settings = replace(settings, identity_domain_id="ocid1.domain.oc1..domain-test", admin_user_ocid=ADMIN_OCID)
    app = product_app(settings)
    identity = Identity()
    app.state.identity_factory = lambda: identity
    app.state.gods_eye_view_aidp_factory = lambda: SimpleNamespace()
    app.state.test_identity = identity
    return app


def local_settings(tmp_path, **overrides):
    return Settings(gods_eye_view_mode="local", cookie_secure=False,
        aidp_settings_file=str(tmp_path / "settings.json"), session_secret_file=str(tmp_path / "session.key"), **overrides)


def admin_login(client):
    name = COOKIE_NAME if client.app.state.settings.cookie_secure else LOCAL_COOKIE_NAME
    client.cookies.set(name, issue_session(client.app.state.session_key, "viewer:admin"))


def make_client(tmp_path, **overrides):
    return TestClient(create_app(local_settings(tmp_path, **overrides)))


login = admin_login
