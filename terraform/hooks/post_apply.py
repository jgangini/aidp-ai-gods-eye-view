"""Independent Deploy Studio entrypoint for the God’s Eye View AIDP installation."""
from __future__ import annotations
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import quote
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/backend"))
from native_api import AidpApi, ApiRequestError, ensure_workspace_folder, build_signer, load_oci_config
from preflight import effective_admin, probe
from gods_eye_view_bootstrap import bootstrap_gods_eye_view, operation
from app.config import Settings
from app.modules.ai_gods_eye_view.runtime.control_store import ObjectControlStore


class InstallationJournal:
    """CAS lease and exact installation bindings exclude concurrent runners."""
    def __init__(self, store, identity, *, clock=time.time):
        self.store, self.identity, self.clock = store, identity, clock
        self.owner = uuid4().hex
        self.state, self.etag = store.get_json("operation.json")
        if self.state and self.state.get("identity") != identity:
            raise ValueError("Installation receipt belongs to a different target or administrator")
        self.state = self.state or {"schema_version": 1, "identity": identity, "resources": {}}
        if self.state.get("lease_until", 0) > clock():
            raise ValueError("Another installation runner owns this operation")
        self.save(owner=self.owner, lease_until=clock() + 3500, status="running")

    def save(self, **values):
        state = {**self.state, **values}
        self.etag = self.store.put_json("operation.json", state, expected_etag=self.etag, create=self.etag is None)
        self.state = state

    def record(self, name, key):
        resources = self.state["resources"]
        if name in resources and resources[name] != key:
            raise ValueError("Managed resource identity changed")
        self.save(resources={**resources, name: key})

    def release(self, status):
        self.save(status=status, owner="", lease_until=0)


def grant_new_platform_admin(api, user_ocid):
    roles = [role for role in api.list_all("/roles") if role.get("displayName") == "AI_DATA_PLATFORM_ADMIN"]
    if len(roles) != 1 or not roles[0].get("key"):
        raise ValueError("Native platform administrator role is not ready")
    role = api.request("GET", "/roles/" + quote(roles[0]["key"], safe="")).body
    if not any(item.get("type") == "USER" and item.get("target") == user_ocid for item in role.get("assignees", [])):
        operation(api, api.request("POST", "/roles/" + quote(role["key"], safe="") + "/actions/addMember",
            payload={"assignees": [{"type": "USER", "target": user_ocid}]}))
    checked = api.request("GET", "/roles/" + quote(role["key"], safe="")).body
    if not any(item.get("type") == "USER" and item.get("target") == user_ocid for item in checked.get("assignees", [])):
        raise ValueError("New platform administrator assignment did not round-trip")


def resolve_workspace(api, context, outputs):
    key = outputs.get("existing_workspace_key")
    if context["inputs"]["aidp_mode"] == "existing":
        workspace = api.request("GET", "/workspaces/" + quote(key, safe="")).body
        if workspace.get("key") != key:
            raise ValueError("Existing workspace identity differs")
    else:
        matches = [item for item in api.list_all("/workspaces") if item.get("displayName") == outputs["default_workspace_name"]]
        if len(matches) != 1 or not matches[0].get("key"):
            raise ValueError("New platform default workspace is not ready or ambiguous")
        workspace = matches[0]
    if workspace.get("lifecycleState", workspace.get("state")) != "ACTIVE":
        raise ValueError("Workspace is not active")
    return str(workspace["key"])


def catalog(api, journal, external_key=""):
    key = journal.state["resources"].get("catalog")
    if not key and external_key:
        value = api.request("GET", "/catalogs/" + quote(external_key, safe="")).body
        if value.get("key") != external_key or value.get("displayName") != "oci_medallion" or value.get("catalogType") != "INTERNAL":
            raise ValueError("Selected external catalog differs from its exact identity")
        journal.record("catalog", external_key)
        journal.save(catalog_ownership="external")
        key = external_key
    if key:
        value = api.request("GET", "/catalogs/" + quote(key, safe="")).body
    else:
        if any(item.get("displayName") == "oci_medallion" for item in api.list_all("/catalogs")):
            raise ValueError("Catalog exists without this installation's exact receipt; refusing adoption")
        response = api.request("POST", "/catalogs", payload={"displayName": "oci_medallion",
            "description": "God's Eye View managed Gold catalog", "catalogType": "INTERNAL"})
        operation(api, response)
        value = response.body
        if not isinstance(value, dict) or not value.get("key"):
            raise ValueError("Catalog create returned no identity; reconcile its request before Resume")
        journal.record("catalog", value["key"])
        value = api.request("GET", "/catalogs/" + quote(value["key"], safe="")).body
    if value.get("displayName") != "oci_medallion" or value.get("catalogType") != "INTERNAL":
        raise ValueError("Managed catalog differs from receipt")
    return value


def grant_administrator_reader(context, signer):
    from oci._vendor import requests
    from app.services.oci.identity import IdentityClient
    outputs, inputs = context["terraform_outputs"], context["inputs"]
    settings = Settings(identity_domain_id=inputs["identity_domain_id"], identity_domain_url=outputs["identity_domain_url"],
        admin_user_ocid=inputs["admin_user_ocid"], gods_eye_view_group_id=outputs["gods_eye_view_group_id"],
        lab_marker=context["deployment_id"])
    async def grant():
        client = IdentityClient(settings, client=requests.Session())
        client.signer = signer
        try:
            response = await client._request("GET", "/admin/v1/Users", params={"filter": 'ocid eq "' + inputs["admin_user_ocid"] + '"', "count": 2})
            response.raise_for_status()
            body = response.json()
            if body.get("totalResults") != 1 or len(body.get("Resources", [])) != 1:
                raise ValueError("Selected administrator account is ambiguous")
            user = body["Resources"][0]
            if user.get("active") is not True or user.get("ocid") != inputs["admin_user_ocid"]:
                raise ValueError("Selected administrator is no longer active")
            group = await client._gods_eye_view_group()
            if not group:
                raise ValueError("Product reader group identity differs")
            if not await client._is_member(group, user["id"]):
                patched = await client._request("PATCH", "/admin/v1/Groups/" + quote(group, safe=""),
                    headers={"Content-Type": "application/scim+json"}, json={
                    "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                    "Operations": [{"op": "add", "path": "members", "value": [{"value": user["id"]}]}]})
                patched.raise_for_status()
            if not await client._is_member(group, user["id"]):
                raise ValueError("Administrator viewer access did not round-trip")
        finally:
            await client.close()
    asyncio.run(grant())


def install(context, config, signer, storage, *, secrets=None, api_factory=AidpApi, bootstrap=bootstrap_gods_eye_view):
    outputs = context["terraform_outputs"]
    inputs = context["inputs"]
    api = api_factory(context["region"], outputs["ai_data_platform_id"], signer, context["deployment_id"])
    store = ObjectControlStore(storage, outputs["objectstorage_namespace"], outputs["artifacts_bucket_name"],
        prefix=".control/gods_eye_view/install/")
    identity = {"product": "gods_eye_view", "deployment_id": context["deployment_id"],
        "platform_id": outputs["ai_data_platform_id"], "admin_user_ocid": inputs["admin_user_ocid"],
        "identity_domain_id": inputs["identity_domain_id"], "operator_user_ocid": config["user"]}
    journal = InstallationJournal(store, identity)
    api.installation_journal = journal
    try:
        # Publish only the reviewed local bootstrap bytes, before the VM's public-key probe.
        sys.path.insert(0, str(ROOT / "scripts/deployment"))
        from build_vm_bundle import build
        bundle = build(ROOT)
        if hashlib.sha256(bundle).hexdigest() != inputs["vm_bundle_sha256"]:
            raise ValueError("VM bundle bytes differ from the pinned deployment artifact")
        try:
            storage.put_object(outputs["objectstorage_namespace"], outputs["artifacts_bucket_name"], inputs["vm_bundle_object"], bundle,
                content_type="application/zip", if_none_match="*")
        except Exception as exc:
            if getattr(exc, "status", None) != 412:
                raise
            existing = storage.get_object(outputs["objectstorage_namespace"], outputs["artifacts_bucket_name"], inputs["vm_bundle_object"])
            if hashlib.sha256(existing.data.content).hexdigest() != inputs["vm_bundle_sha256"]:
                raise ValueError("Immutable bundle object conflicts with the selected source") from None
        # Domain/user revalidation is repeated on every install/resume, before resource work.
        if inputs["aidp_mode"] == "new":
            probe(context, config)
            grant_new_platform_admin(api, inputs["admin_user_ocid"])
        verified_context = {**context, "inputs": {**inputs, "aidp_mode": "existing",
            "existing_ai_data_platform_ocid": outputs["ai_data_platform_id"],
            "existing_workspace_key": resolve_workspace(api, context, outputs)}}
        probe(verified_context, config)
        workspace = verified_context["inputs"]["existing_workspace_key"]
        journal.record("workspace", workspace)
        managed_catalog = catalog(api, journal, inputs.get("existing_catalog_key", ""))
        grant_administrator_reader(context, signer)
        outputs["workspace_key"] = workspace
        from vm_delivery import deliver
        deliver(context, config, signer, storage, secrets or {})
        result = bootstrap(api, context, outputs, config, signer, storage,
            {"workspace_key": workspace, "catalog_key": managed_catalog["key"], "catalog_name": "oci_medallion"},
            deadline=time.monotonic() + 3200, ensure_folder=ensure_workspace_folder)
        journal.save(source_commit_sha=inputs["source_commit_sha"], native=result)
        journal.release("aidp_ready")
        return {"schema_version": 1, "status": "aidp_ready", "native": result,
            "message": "AIDP task/publication checks passed; VM bootstrap and conversation acceptance are separate gates"}
    except Exception:
        journal.release("needs_attention")
        raise
    finally:
        api.session.close()


def main():
    target = Path(os.environ["DEPLOY_STUDIO_OUTPUT"])
    try:
        import oci
        context = json.loads(Path(os.environ["DEPLOY_STUDIO_CONTEXT"]).read_text(encoding="utf-8"))
        config = load_oci_config(os.environ["DEPLOY_STUDIO_OCI_CONFIG"], os.environ["DEPLOY_STUDIO_OCI_KEY"])
        signer = build_signer(config)
        secrets = json.loads(Path(os.environ["DEPLOY_STUDIO_SECRETS"]).read_text(encoding="utf-8"))["inputs"]
        result = install(context, config, signer, oci.object_storage.ObjectStorageClient(config, signer=signer), secrets=secrets)
        code = 0
    except Exception:
        result = {"schema_version": 1, "status": "needs_attention", "message": "Installation stopped; preserve the durable operation receipt and reconcile before Resume"}
        code = 1
    target.write_text(json.dumps(result) + "\n", encoding="utf-8")
    target.chmod(0o600)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
