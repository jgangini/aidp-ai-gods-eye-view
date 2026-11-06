"""Deliver the authorized operator and TLS configuration in a single encrypted object."""
import json
import hashlib
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/deployment"))
from bootstrap_credentials import binding, encrypt
from native_api import render_runtime_oci_config
from vm_public_key import fetch_bootstrap_public_key, BOOTSTRAP_READY


def run_command(client, oci_module, outputs, command, token):
    models = oci_module.compute_instance_agent.models
    result = client.create_instance_agent_command(models.CreateInstanceAgentCommandDetails(
        compartment_id=outputs["compartment_ocid"], execution_time_out_in_seconds=900,
        target=models.InstanceAgentCommandTarget(instance_id=outputs["instance_id"]),
        content=models.InstanceAgentCommandContent(source=models.InstanceAgentCommandSourceViaTextDetails(text=command),
            output=models.InstanceAgentCommandOutputViaTextDetails())), opc_retry_token=hashlib.sha256(token.encode()).hexdigest()).data
    for _ in range(180):
        try:
            execution = client.get_instance_agent_command_execution(result.id, outputs["instance_id"]).data
        except oci_module.exceptions.ServiceError as exc:
            if exc.status != 404:
                raise
            time.sleep(5)
            continue
        if execution.lifecycle_state == "SUCCEEDED":
            return
        if execution.lifecycle_state in {"FAILED", "TIMED_OUT", "CANCELED"}:
            raise ValueError("VM runtime operation failed; preserve prior release receipt")
        time.sleep(5)
    raise ValueError("VM runtime operation outcome unknown; reconcile before another command")


def runtime_environment(context, assets):
    inputs, outputs = context["inputs"], context["terraform_outputs"]
    values = {"ADMIN_USER_OCID": inputs["admin_user_ocid"], "IDENTITY_DOMAIN_ID": inputs["identity_domain_id"],
        "IDENTITY_DOMAIN_URL": outputs["identity_domain_url"], "IDENTITY_GODS_EYE_VIEW_GROUP_ID": outputs["gods_eye_view_group_id"],
        "IDENTITY_VIEWER_APP_NAME": outputs["viewer_oidc_app_name"], "VIEWER_OIDC_REDIRECT_URI": outputs["public_origin"] + "/api/auth/oci/callback",
        "AIDP_PLATFORM_ID": outputs["ai_data_platform_id"], "AIDP_REGION": context["region"],
        "AIDP_WORKSPACE_KEY": outputs["workspace_key"], "COMPARTMENT_ID": outputs["compartment_ocid"],
        "OBJECTSTORAGE_NAMESPACE": outputs["objectstorage_namespace"], "BUCKET_NAME": outputs["medallion_bucket_names"]["landing"],
        "GODS_EYE_CONTROL_BUCKET": outputs["medallion_bucket_names"]["gold"], "ARTIFACTS_BUCKET_NAME": outputs["artifacts_bucket_name"],
        "LAB_MARKER": context["deployment_id"], "GODS_EYE_VIEW_ENABLED": "true", "GODS_EYE_VIEW_MODE": "oci", "COOKIE_SECURE": "true",
        "PUBLIC_HOST": urlsplit(outputs["public_origin"]).hostname}
    from image_assets_vm import validate_assets
    for asset in validate_assets(assets):
        values[asset["component"].upper() + "_IMAGE"] = asset["image_id"]
    if any(not isinstance(v, str) or not v or any(c in v for c in "\r\n\x00") for v in values.values()):
        raise ValueError("Invalid runtime binding")
    return "".join(f"{key}={value}\n" for key, value in values.items())


def deliver(context, config, signer, storage, secrets):
    import oci
    outputs = context["terraform_outputs"]
    from image_assets import stage_handoff
    assets = stage_handoff(context, storage)
    expected = binding(context["deployment_id"], config["user"], config["fingerprint"])
    client = oci.compute_instance_agent.ComputeInstanceAgentClient(config, signer=signer)
    public = fetch_bootstrap_public_key(client, oci,
        outputs["compartment_ocid"], outputs["instance_id"])
    if public == BOOTSTRAP_READY:
        # Updates use a fresh recipient key; the authorized operator binding stays fixed.
        run_command(client, oci, outputs, "sudo /bin/bash /opt/gods-eye-view/docker/bootstrap.sh prepare",
            context["deployment_id"] + "-prepare-" + context["inputs"]["source_commit_sha"][:12])
        public = fetch_bootstrap_public_key(client, oci, outputs["compartment_ocid"], outputs["instance_id"])
        if public == BOOTSTRAP_READY:
            raise ValueError("VM did not prepare a fresh bootstrap recipient")
    for key in ("tls_certificate", "tls_key"):
        if not secrets.get(key):
            raise ValueError("TLS certificate and key required in protected post-apply inputs")
    # Private key and TLS material remain out of Terraform variables, user-data and result files.
    payload = {"config": render_runtime_oci_config(config), "key": Path(config["key_file"]).read_text(encoding="utf-8"),
        "runtime_env": runtime_environment(context, assets), "tls_certificate": secrets["tls_certificate"], "tls_key": secrets["tls_key"],
        "image_assets": json.dumps(assets, sort_keys=True)}
    encrypted = encrypt(public.encode(), payload, expected)
    object_name = f".bootstrap/gods-eye-view/{context['deployment_id']}/operator.json"
    try:
        storage.put_object(outputs["objectstorage_namespace"], outputs["artifacts_bucket_name"], object_name,
            encrypted, content_type="application/json", if_none_match="*")
    except oci.exceptions.ServiceError as exc:
        if exc.status != 412:
            raise
        previous = storage.get_object(outputs["objectstorage_namespace"], outputs["artifacts_bucket_name"], object_name)
        if json.loads(previous.data.content).get("binding") != expected:
            raise ValueError("Existing bootstrap object belongs to another operator or deployment") from None
    # First boot already has a receiver; later updates start it explicitly.
    if context.get("operation_type") in {"update", "redeploy"}:
        run_command(client, oci, outputs,
            "sudo /opt/gods-eye-bootstrap/bin/python /opt/gods-eye-view/receive.py && sudo /bin/bash /opt/gods-eye-view/docker/bootstrap.sh start",
            context["deployment_id"] + "-activate-" + context["inputs"]["source_commit_sha"][:12])
    return True
