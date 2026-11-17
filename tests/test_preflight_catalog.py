import json
from pathlib import Path
import sys
from types import SimpleNamespace as Item

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "terraform/hooks"))
from preflight import CatalogSelectionError, installation_identity, recorded_catalog_key, verify_catalog_selection


class Api:
    value = {"key": "catalog-key", "displayName": "oci_medallion", "catalogType": "INTERNAL"}
    def __init__(self):
        self.calls = []
    def request(self, method, path):
        assert method == "GET"
        self.calls.append((method, path))
        return Item(body=self.value)
    def list_all(self, path):
        assert path == "/catalogs"
        self.calls.append(("GET", path))
        return [self.value] if self.value else []


def test_existing_unowned_medallion_requires_an_exact_key_before_apply():
    api = Api()
    with pytest.raises(CatalogSelectionError, match="existing_catalog_key"):
        verify_catalog_selection(api, "")
    assert api.calls == [("GET", "/catalogs")]
    assert verify_catalog_selection(api, "catalog-key") == api.value


def test_resume_uses_its_exact_recorded_catalog_and_rejects_selection_changes():
    api = Api()
    assert verify_catalog_selection(api, "", "catalog-key") == api.value
    api.calls.clear()
    with pytest.raises(CatalogSelectionError, match="differs"):
        verify_catalog_selection(api, "other-key", "catalog-key")
    assert api.calls == []


@pytest.mark.parametrize("field,value", [("key", "other-key"), ("displayName", "different"), ("catalogType", "EXTERNAL")])
def test_catalog_identity_and_type_are_revalidated(field, value):
    api = Api()
    api.value = {**api.value, field: value}
    with pytest.raises(CatalogSelectionError, match="INTERNAL identity"):
        verify_catalog_selection(api, "catalog-key")


def test_empty_existing_platform_can_create_its_own_catalog_later():
    api = Api()
    api.value = None
    assert verify_catalog_selection(api, "") is None
    assert api.calls == [("GET", "/catalogs")]


def receipt_context():
    return {"deployment_id": "deployment-1", "inputs": {"existing_ai_data_platform_ocid": "platform",
        "admin_user_ocid": "admin", "identity_domain_id": "domain", "artifacts_bucket_name": "artifacts"}}


class Storage:
    def __init__(self, receipt=None, status=None):
        self.receipt, self.status, self.calls = receipt, status, []
    def get_namespace(self, **kw):
        self.calls.append(("get_namespace", kw))
        return Item(data="namespace")
    def get_object(self, namespace, bucket, key):
        self.calls.append((namespace, bucket, key))
        if self.status:
            error = RuntimeError("Object read failed")
            error.status = self.status
            raise error
        return Item(data=Item(content=json.dumps(self.receipt).encode()), headers={"etag": "read-etag"})


def test_preflight_reads_the_owned_receipt_without_claiming_a_lease_or_writing():
    context, config = receipt_context(), {"tenancy": "tenancy", "user": "operator"}
    expected = installation_identity(context, config, "platform")
    store = Storage({"identity": expected, "resources": {"catalog": "catalog-key"}, "lease_until": 99999999})
    assert recorded_catalog_key(context, config, store) == "catalog-key"
    assert store.calls[-1] == ("namespace", "artifacts", ".control/gods_eye_view/install/operation.json")


@pytest.mark.parametrize("field", ["deployment_id", "platform_id", "admin_user_ocid", "identity_domain_id", "operator_user_ocid"])
def test_another_installation_receipt_never_authorizes_catalog_reuse(field):
    context, config = receipt_context(), {"tenancy": "tenancy", "user": "operator"}
    identity = installation_identity(context, config, "platform")
    store = Storage({"identity": {**identity, field: "different"}, "resources": {"catalog": "catalog-key"}})
    with pytest.raises(ValueError, match="different target"):
        recorded_catalog_key(context, config, store)


def test_missing_receipt_is_allowed_but_forbidden_storage_access_is_not():
    context, config = receipt_context(), {"tenancy": "tenancy", "user": "operator"}
    assert recorded_catalog_key(context, config, Storage(status=404)) == ""
    with pytest.raises(RuntimeError, match="Object read failed"):
        recorded_catalog_key(context, config, Storage(status=403))
