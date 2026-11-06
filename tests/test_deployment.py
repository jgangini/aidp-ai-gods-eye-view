import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "terraform/hooks"))
sys.path.insert(0, str(ROOT / "scripts/deployment"))
sys.path.insert(0, str(ROOT / "apps/backend"))
import bootstrap_credentials as envelope
from preflight import validate_inputs, verify_administrator, source_context
from post_apply import InstallationJournal, grant_new_platform_admin, wait_viewer_health, install, catalog
import gods_eye_view_bootstrap as native
from types import SimpleNamespace


def test_domain_and_active_admin_are_exact():
    selected = {"identity_domain_id": "ocid1.domain.oc1..one", "admin_user_ocid": "ocid1.user.oc1..selected"}
    user = {"active": True, "ocid": selected["admin_user_ocid"]}
    verify_administrator(selected, {"id": selected["identity_domain_id"], "lifecycle_state": "ACTIVE"}, user)
    for domain, candidate in (({"id": "ocid1.domain.oc1..other", "lifecycle_state": "ACTIVE"}, user),
        ({"id": selected["identity_domain_id"], "lifecycle_state": "ACTIVE"}, {**user, "active": False}),
        ({"id": selected["identity_domain_id"], "lifecycle_state": "ACTIVE"}, {**user, "ocid": "ocid1.user.oc1..operator"})):
        with pytest.raises(ValueError):
            verify_administrator(selected, domain, candidate)


def test_source_sha_comes_from_runner_metadata_and_cannot_be_replaced_by_form():
    context = {"source": {"repository": "https://github.com/jgangini/aidp-ai-gods-eye-view", "commit_sha": "a" * 40}, "inputs": {}}
    assert source_context(context)["inputs"]["source_commit_sha"] == "a" * 40
    with pytest.raises(ValueError, match="differs"):
        source_context({**context, "inputs": {"source_commit_sha": "b" * 40}})


def test_resume_rejects_a_changed_catalog_selection_before_any_request():
    journal = InstallationJournal(Store(), {"deployment_id": "one"}, clock=lambda: 10)
    journal.record("catalog", "original-key")
    with pytest.raises(ValueError, match="differs"):
        catalog(SimpleNamespace(), journal, "other-key")


def test_native_bootstrap_reuses_only_the_exact_catalog_already_verified_in_receipt():
    journal = InstallationJournal(Store(), {"deployment_id": "one"}, clock=lambda: 10)
    journal.record("catalog", "verified-catalog-key")
    class Api:
        installation_journal = journal
        key = "verified-catalog-key"
        def request(self, *_args, **_kwargs):
            return SimpleNamespace(body={"items": [{"key": self.key, "displayName": "oci_medallion", "state": "ACTIVE"}]}, headers={})
    api = Api()
    assert native.named(api, "/catalogs", "oci_medallion")["key"] == "verified-catalog-key"
    api.key = "different-key"
    with pytest.raises(RuntimeError, match="no adoption"):
        native.named(api, "/catalogs", "oci_medallion")


def test_buckets_and_existing_workspace_fail_closed():
    inputs = {"identity_domain_id": "ocid1.domain.oc1..one", "admin_user_ocid": "ocid1.user.oc1..selected",
        "aidp_mode": "new", "medallion_bucket_names": {layer: layer for layer in ("landing", "bronze", "silver", "gold")},
        "artifacts_bucket_name": "artifacts"}
    assert validate_inputs(inputs)["aidp_mode"] == "new"
    with pytest.raises(ValueError):
        validate_inputs({**inputs, "aidp_mode": "existing"})
    with pytest.raises(ValueError):
        validate_inputs({**inputs, "artifacts_bucket_name": "gold"})


def test_envelope_is_bound_authenticated_and_single_use(tmp_path):
    import hashlib
    operator = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    fingerprint = hashlib.md5(operator.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo), usedforsecurity=False).hexdigest()
    expected = envelope.binding("deployment-1", "ocid1.user.oc1..operator", fingerprint)
    public = envelope.generate_key(tmp_path / "bootstrap/private.pem")
    payload = {"config": f"[DEFAULT]\nuser=ocid1.user.oc1..operator\nfingerprint={fingerprint}\n",
        "key": operator.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode(),
        "runtime_env": "GODS_EYE_VIEW_MODE=oci\n", "tls_certificate": "test-certificate", "tls_key": "test-key",
        "image_assets": json.dumps([{"component": component, "object_name": "releases/" + "a" * 40 + "/" + prefix + "-image-amd64.tar.gz",
            "archive_sha256": "b" * 64, "image_id": "sha256:" + "c" * 64, "image_tag": prefix + ":" + "a" * 40}
            for component, prefix in (("api", "gods-eye-view-api"), ("viewer", "gods-eye-view"), ("gateway", "gods-eye-view-gateway"))])}
    encrypted = envelope.encrypt(public, payload, expected)
    with pytest.raises(ValueError):
        envelope.consume(encrypted, tmp_path, {**expected, "deployment_id": "other"})
    assert not (tmp_path / "oci").exists()
    tampered = json.loads(encrypted)
    tampered["ciphertext"] = tampered["ciphertext"][:-4] + "AAAA"
    with pytest.raises(InvalidTag):
        envelope.consume(json.dumps(tampered).encode(), tmp_path, expected)
    envelope.consume(encrypted, tmp_path, expected)
    assert (tmp_path / "oci/config").read_text().find("/etc/gods-eye-view/oci/key.pem") >= 0
    assert not (tmp_path / "bootstrap/private.pem").exists()
    with pytest.raises(FileNotFoundError):
        envelope.consume(encrypted, tmp_path, expected)
    updated_public = envelope.generate_key(tmp_path / "bootstrap/private.pem")
    changed = envelope.encrypt(updated_public, {**payload, "tls_key": "different-key"}, expected)
    with pytest.raises(ValueError, match="separate authorized recovery"):
        envelope.consume(changed, tmp_path, expected)
    assert (tmp_path / "tls/privkey.pem").read_text() == "test-key"
    assert (tmp_path / "bootstrap/private.pem").exists()


class Store:
    def __init__(self):
        self.value, self.revision = None, 0
    def get_json(self, _key):
        return copy.deepcopy(self.value), str(self.revision) if self.revision else None
    def put_json(self, _key, value, *, expected_etag=None, create=False):
        if (create and self.value is not None) or (not create and expected_etag != str(self.revision)):
            raise ValueError("CAS conflict")
        self.value = copy.deepcopy(value)
        self.revision += 1
        return str(self.revision)


def test_journal_excludes_concurrent_runner_and_preserves_ids_on_resume():
    store = Store()
    identity = {"admin_user_ocid": "selected", "platform_id": "platform"}
    first = InstallationJournal(store, identity, clock=lambda: 10)
    first.record("workspace", "key-1")
    with pytest.raises(ValueError, match="Another"):
        InstallationJournal(store, identity, clock=lambda: 11)
    first.release("needs_attention")
    resumed = InstallationJournal(store, identity, clock=lambda: 12)
    assert resumed.state["resources"]["workspace"] == "key-1"
    with pytest.raises(ValueError, match="identity changed"):
        resumed.record("workspace", "key-2")
    resumed.release("aidp_ready")
    with pytest.raises(ValueError, match="different target"):
        InstallationJournal(store, {**identity, "admin_user_ocid": "other"}, clock=lambda: 13)


def test_native_resources_are_never_adopted_by_name_and_created_keys_are_recorded():
    journal = InstallationJournal(Store(), {"deployment_id": "one"}, clock=lambda: 10)
    class Api:
        installation_journal = journal
        resource = {"key": "untracked-key", "displayName": "selected", "state": "ACTIVE"}
        def request(self, method, path, **kwargs):
            if method == "POST":
                self.resource = {"key": "created-key", "displayName": "selected", "state": "ACTIVE"}
                return SimpleNamespace(body=self.resource, headers={})
            return SimpleNamespace(body={"items": [self.resource] if self.resource else []}, headers={})
    api = Api()
    with pytest.raises(RuntimeError, match="no adoption"):
        native.ensure(api, "/resources", "selected", {"displayName": "selected"})
    api.resource = None
    created = native.ensure(api, "/resources", "selected", {"displayName": "selected"})
    assert created["key"] == journal.state["resources"]["native:/resources:selected"] == "created-key"
    assert native.ensure(api, "/resources", "selected", None)["key"] == "created-key"
    api.resource = {**api.resource, "key": "other-key"}
    with pytest.raises(RuntimeError, match="no adoption"):
        native.ensure(api, "/resources", "selected", None)


def test_new_platform_grants_selected_admin_without_impersonating_operator():
    class Api:
        assignees = []
        calls = []
        def list_all(self, _path):
            return [{"key": "platform-admin", "displayName": "AI_DATA_PLATFORM_ADMIN"}]
        def request(self, method, path, **kwargs):
            if method == "POST":
                self.calls.append(kwargs["payload"])
                self.assignees = kwargs["payload"]["assignees"]
            return SimpleNamespace(body={"key": "platform-admin", "assignees": self.assignees}, headers={})
    api = Api()
    grant_new_platform_admin(api, "ocid1.user.oc1..selected")
    grant_new_platform_admin(api, "ocid1.user.oc1..selected")
    assert api.calls == [{"assignees": [{"type": "USER", "target": "ocid1.user.oc1..selected"}]}]


def test_hidden_compute_cannot_bypass_identity_receipt():
    journal = InstallationJournal(Store(), {"deployment_id": "one"}, clock=lambda: 10)
    api = SimpleNamespace(installation_journal=journal)
    with pytest.raises(RuntimeError, match="no adoption"):
        native.hidden_compute_detail(api, "/workspaces/ws/clusters", "selected", "untracked-key", "SUCCEEDED")


def test_unconfigured_private_handoff_fails_before_any_cloud_client_or_journal():
    with pytest.raises(ValueError):
        install({}, {}, None, None, secrets={})


@pytest.mark.parametrize("failure", ["source_ref", "missing_archive", "corrupt_archive"])
def test_invalid_private_handoff_stops_install_before_native_client(tmp_path, failure):
    from test_image_assets import local_stage_context
    context = local_stage_context(tmp_path)
    if failure == "source_ref":
        context["source"]["ref"] = "v9.9.9"
    else:
        asset = context["release_assets"]["assets"]["gods-eye-view-gateway-image-amd64.tar.gz"]
        if failure == "missing_archive":
            del asset["path"]
        else:
            path = Path(asset["path"])
            path.write_bytes(b"x" * path.stat().st_size)
    def forbidden_client(*_args, **_kwargs):
        pytest.fail("Invalid private assets must fail before native client or journal creation")
    with pytest.raises(ValueError):
        install(context, {}, None, None, secrets={}, api_factory=forbidden_client)


def test_viewer_health_requires_success_and_bounded_wait():
    class Client:
        status = 503
        def get(self, url):
            assert url in {"https://viewer.example/health", "https://viewer.example/api/gods-eye-view/session"}
            if url.endswith("/session"):
                return SimpleNamespace(status_code=401)
            return SimpleNamespace(status_code=self.status)
    client = Client()
    ticks = iter((0, 6))
    with pytest.raises(ValueError, match="not complete"):
        wait_viewer_health("https://viewer.example", "", 5, client=client, clock=lambda: next(ticks), sleep=lambda _: None)
    client.status = 200
    wait_viewer_health("https://viewer.example", "", 5, client=client, clock=lambda: 0, sleep=lambda _: None)
