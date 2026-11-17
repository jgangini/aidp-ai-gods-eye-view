"""Exercise real API authorization using only fake external OCI responses."""
from dataclasses import replace
from types import SimpleNamespace
import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import create_app, LOCAL_COOKIE_NAME
from app.config import Settings
from app.security import issue_session
from app.services.oci.identity import IdentityClient
from tests.support import Identity, ADMIN_OCID


@pytest.fixture
def product(tmp_path):
    settings = Settings(cookie_secure=False, gods_eye_view_enabled=False, gods_eye_view_mode="local",
        admin_user_ocid=ADMIN_OCID, identity_domain_id="ocid1.domain.oc1..test",
        session_secret_file=str(tmp_path / "session.key"), aidp_settings_file=str(tmp_path / "settings.json"))
    app = create_app(settings)
    identity = Identity()
    app.state.identity_factory = lambda: identity
    app.state.gods_eye_view_aidp_factory = lambda: SimpleNamespace()
    client = TestClient(app)
    return client, app, identity


def session(product, user="admin"):
    client, app, _ = product
    client.cookies.set(LOCAL_COOKIE_NAME, issue_session(app.state.session_key, "viewer:" + user))
    return client


@pytest.mark.parametrize("path", ["/api/gods-eye-view/session", "/api/gods-eye-view/snapshot", "/api/admin/session", "/api/admin/gods-eye-view/sources"])
def test_anonymous_and_forged_headers_never_grant_access(product, path):
    client = product[0]
    response = client.get(path, headers={"X-Gods-Eye-View-User": "viewer:admin", "X-Gods-Eye-View-Role": "admin", "Cookie": "invalid=present"})
    assert response.status_code == 401


def test_reader_admin_membership_and_role_revocation(product):
    client = session(product, "reader")
    assert client.get("/api/gods-eye-view/session").json()["role"] == "reader"
    assert client.get("/api/admin/session").status_code == 403
    assert client.put("/api/admin/gods-eye-view/identity", json={"name": "Blocked", "description": ""}).status_code == 403
    client = session(product)
    assert client.get("/api/admin/session").status_code == 200
    assert client.get("/api/gods-eye-view/session").headers["X-Gods-Eye-View-Role"] == "admin"
    product[2].admin_role = False
    assert client.get("/api/admin/session").status_code == 403
    assert client.get("/api/gods-eye-view/session").json()["role"] == "reader"
    product[2].active = False
    assert client.get("/api/gods-eye-view/session").status_code == 401


def test_selected_admin_identity_is_not_a_username_or_operator_substitution(product):
    client = session(product)
    product[1].state.settings = replace(product[1].state.settings, admin_user_ocid="ocid1.user.oc1..different")
    assert client.get("/api/admin/session").status_code == 403
    client.cookies.set(LOCAL_COOKIE_NAME, issue_session(product[1].state.session_key, "admin"))
    assert client.get("/api/admin/session").status_code == 401


@pytest.mark.parametrize("path", ["/api/admin/login", "/api/register", "/api/local/gods-eye-view/login", "/api/admin/gods-eye-view/module/deploy", "/api/admin/users/user/modules/gods_eye_view"])
def test_portal_login_and_installation_are_absent(product, path):
    assert session(product).post(path, json={}).status_code == 404


def test_cross_origin_mutation_denied_before_writing_and_same_origin_persists(product):
    client = session(product)
    payload = {"name": "My viewer", "description": "AIDP evidence"}
    assert client.put("/api/admin/gods-eye-view/identity", json=payload, headers={"Origin": "https://attacker.example"}).status_code == 403
    assert client.get("/api/gods-eye-view/identity").json()["name"] != payload["name"]
    assert client.put("/api/admin/gods-eye-view/identity", json=payload, headers={"Origin": "http://testserver"}).status_code == 200
    assert client.get("/api/gods-eye-view/identity").json() == payload


def test_validation_errors_never_echo_credential_values(product):
    client = session(product)
    secret = "private-test-value-never-echo"
    response = client.put("/api/admin/gods-eye-view/sources/x", json={"private_key": secret})
    assert response.status_code == 422
    assert secret not in response.text
    assert all("input" not in item and "ctx" not in item for item in response.json()["detail"])


@pytest.mark.parametrize("member,active,expected", [(True,True,True),(False,True,False),(True,False,False)])
def test_effective_group_role_uses_exact_ocid_and_current_membership(member, active, expected):
    paths = []
    async def transport(request):
        paths.append(request.url.path)
        if request.url.path.endswith("/Users/user-id"):
            return httpx.Response(200,json={"id":"user-id","ocid":ADMIN_OCID,"active":active,"userName":"admin@example.test"})
        if request.url.path.endswith("/Groups") and request.url.params.get("filter", "").startswith("ocid eq"):
            assert request.url.params["filter"] == 'ocid eq "ocid1.group.oc1..admins"'
            return httpx.Response(200,json={"totalResults":1,"Resources":[{"id":"group-id","ocid":"ocid1.group.oc1..admins"}]})
        if request.url.path.endswith("/Users"):
            assert request.url.params["filter"] == 'id eq "user-id" and groups.value eq "group-id"'
            return httpx.Response(200,json={"Resources":[{"id":"user-id"}] if member else []})
        raise AssertionError(request.url)
    class Aidp:
        async def platform_admin_principals(self):
            return set(), {"ocid1.group.oc1..admins"}
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            identity = IdentityClient(Settings(identity_domain_url="https://domain.example.test"),client=client)
            return await identity.has_aidp_admin_role("user-id", Aidp())
    assert asyncio.run(run()) is expected


def test_nested_native_roles_are_resolved_without_names_or_infinite_cycles():
    from app.services.oci.aidp import AidpClient
    client = object.__new__(AidpClient)
    client._role = lambda name: {"key":"root"}
    roles = {"root":{"assignees":[{"type":"ROLE","target":"nested"}]},
             "nested":{"assignees":[{"type":"USER","target":ADMIN_OCID},{"type":"ROLE","target":"root"}]}}
    client._request = lambda method,path,**kwargs: roles[path.rsplit("/",1)[1]]
    assert client._role_principal_ocids("AI_DATA_PLATFORM_ADMIN") == ({ADMIN_OCID},set())
