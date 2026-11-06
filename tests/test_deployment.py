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
from preflight import validate_inputs, verify_administrator
from post_apply import InstallationJournal, grant_new_platform_admin
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
        "runtime_env": "GODS_EYE_VIEW_MODE=oci\n", "tls_certificate": "test-certificate", "tls_key": "test-key"}
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
