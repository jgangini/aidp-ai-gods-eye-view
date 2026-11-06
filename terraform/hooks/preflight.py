"""Deploy Studio preflight: validate exact identities without provisioning anything."""
from __future__ import annotations

import json
import asyncio
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

from native_api import AidpApi, assert_operator_platform_admin, build_signer, load_oci_config
from first_install import vm_inputs

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/backend"))
from app.config import Settings
from app.services.oci.identity import IdentityClient
from app.services.oci.aidp import AidpClient


def source_context(context):
    source = context.get("source", {})
    commit = source.get("commit_sha", "")
    if source.get("repository") != "https://github.com/jgangini/aidp-ai-gods-eye-view" or not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Runner source identity is invalid")
    inputs = context.get("inputs", {})
    if inputs.get("source_commit_sha", commit) != commit:
        raise ValueError("Terraform source SHA differs from the runner's immutable source")
    return {**context, "inputs": {**inputs, "source_commit_sha": commit}}


class RoleClient(AidpClient):
    """Use the runner's authorized signer with the runtime's effective-role resolver."""
    def __init__(self, api):
        self.api = api

    def _list(self, path, *, params=None, phase=None):
        return self.api.list_all(path, params=params)

    def _request(self, method, path, *, phase=None, **kwargs):
        return self.api.request(method, path, **kwargs).body


async def effective_admin(settings, signer, user_id, api):
    from oci._vendor import requests
    identity = IdentityClient(settings, client=requests.Session())
    identity.signer = signer
    try:
        return await identity.has_aidp_admin_role(user_id, RoleClient(api))
    finally:
        await identity.close()


def validate_inputs(inputs):
    for name, kind in (("admin_user_ocid", "user"), ("identity_domain_id", "domain")):
        if not re.fullmatch(r"ocid1\." + kind + r"\.[A-Za-z0-9_.-]+", str(inputs.get(name, ""))):
            raise ValueError(f"Invalid {name}")
    if inputs.get("aidp_mode") not in {"new", "existing"}:
        raise ValueError("aidp_mode must be new or existing")
    if inputs["aidp_mode"] == "existing":
        if not str(inputs.get("existing_ai_data_platform_ocid", "")).startswith("ocid1.aidataplatform."):
            raise ValueError("An exact existing AIDP OCID is required")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", str(inputs.get("existing_workspace_key", ""))):
            raise ValueError("An exact existing workspace key is required")
    buckets = inputs.get("medallion_bucket_names")
    if buckets is None:
        buckets = {layer: inputs.get(layer + "_bucket_name", "") for layer in ("landing", "bronze", "silver", "gold")}
    if isinstance(buckets, str):
        buckets = json.loads(buckets)
    if set(buckets) != {"landing", "bronze", "silver", "gold"}:
        raise ValueError("Four medallion bucket selections are required")
    names = [*buckets.values(), inputs.get("artifacts_bucket_name", "")]
    if len(set(names)) != 5 or any(not isinstance(v, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", v) for v in names):
        raise ValueError("Five distinct valid bucket selections are required")
    return {**inputs, "medallion_bucket_names": buckets}


def verify_administrator(inputs, domain, user):
    """SCIM user is fetched from this exact domain, never inferred from display name."""
    if domain.get("id") != inputs["identity_domain_id"] or domain.get("lifecycle_state") != "ACTIVE":
        raise ValueError("Selected Identity Domain is unavailable")
    if user.get("active") is not True or user.get("ocid") != inputs["admin_user_ocid"]:
        raise ValueError("Selected administrator is inactive or belongs to another domain")


def probe(context, config, *, domain_client=None, api_factory=AidpApi):
    import oci
    from oci._vendor import requests

    values = validate_inputs(context.get("inputs", {}))
    region = context["region"]
    config = {**config, "region": region}
    signer = build_signer(config)
    identity = domain_client or oci.identity.IdentityClient(config, signer=signer)
    resolved_vm = vm_inputs(context, config, oci.core.ComputeClient(config, signer=signer), identity)
    subscriptions = identity.list_region_subscriptions(config["tenancy"]).data
    home = [item.region_name for item in subscriptions if item.is_home_region]
    if len(home) != 1 or not any(item.region_name == region and item.status == "READY" for item in subscriptions):
        raise ValueError("Deployment or home region is unavailable")
    domain = identity.get_domain(values["identity_domain_id"]).data
    endpoint = str(domain.url).rstrip("/")
    if not re.fullmatch(r"https://[a-zA-Z0-9.-]+\.oraclecloud\.com", endpoint):
        raise ValueError("Invalid Identity Domain endpoint")
    # The stable OCI user ID is matched exactly within the selected domain.
    response = requests.get(endpoint + "/admin/v1/Users", auth=signer, timeout=30,
        params={"filter": 'ocid eq "' + values["admin_user_ocid"] + '"', "count": 2})
    response.raise_for_status()
    users = response.json()
    if users.get("totalResults") != 1 or len(users.get("Resources", [])) != 1:
        raise ValueError("Administrator identity is absent or ambiguous in this domain")
    api = None
    if values["aidp_mode"] == "existing":
        api = api_factory(region, values["existing_ai_data_platform_ocid"], signer, context["deployment_id"])
        try:
            assert_operator_platform_admin(api, config["user"], attempts=1)
            workspace = api.request("GET", "/workspaces/" + quote(values["existing_workspace_key"], safe="")).body
            if workspace.get("key") != values["existing_workspace_key"] or workspace.get("lifecycleState", workspace.get("state")) != "ACTIVE":
                raise ValueError("Selected workspace is unavailable")
            verify_administrator(values, {"id": domain.id, "lifecycle_state": domain.lifecycle_state}, users["Resources"][0])
            settings = Settings(identity_domain_id=domain.id, identity_domain_url=endpoint,
                admin_user_ocid=values["admin_user_ocid"], aidp_region=region,
                aidp_platform_id=values["existing_ai_data_platform_ocid"])
            if not asyncio.run(effective_admin(settings, signer, users["Resources"][0]["id"], api)):
                raise ValueError("Selected administrator lacks effective platform permissions")
        finally:
            api.session.close()
    else:
        verify_administrator(values, {"id": domain.id, "lifecycle_state": domain.lifecycle_state}, users["Resources"][0])
    return {"inputs": {**resolved_vm, "medallion_bucket_names": json.dumps(values["medallion_bucket_names"], sort_keys=True),
        "identity_domain_url": endpoint, "home_region": home[0], "operator_user_ocid": config["user"],
        "operator_fingerprint": config["fingerprint"]}, "events": [{"name": "Administrator authorization",
        "status": "passed", "message": "Domain identity verified; effective AIDP roles " + ("verified" if api else "require post-bootstrap verification")} ]}


def main():
    result_path = Path(os.environ["DEPLOY_STUDIO_RESULT"])
    try:
        context = source_context(json.loads(Path(os.environ["DEPLOY_STUDIO_CONTEXT"]).read_text(encoding="utf-8")))
        config = load_oci_config(os.environ["DEPLOY_STUDIO_OCI_CONFIG"], os.environ["DEPLOY_STUDIO_OCI_KEY"])
        sys.path.insert(0, str(ROOT / "scripts/deployment"))
        from image_assets import inspect_handoff
        inspect_handoff(context)
        result = probe(context, config)
        result["events"].append({"name": "Private release metadata", "status": "passed",
            "message": "Immutable source, access and image manifests verified; archive bytes are checked before VM delivery"})
        code = 0
    except Exception:
        # HTTP bodies/config may carry sensitive information; keep the runner event bounded.
        result = {"inputs": {}, "events": [{"name": "Administrator authorization", "status": "failed",
            "message": "Private release handoff, identity, workspace or effective permissions could not be verified"}]}
        code = 1
    result_path.write_text(json.dumps(result) + "\n", encoding="utf-8")
    result_path.chmod(0o600)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
