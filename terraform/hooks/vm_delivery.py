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
from vm_public_key import fetch_bootstrap_public_key, fetch_vm_public_output, BOOTSTRAP_READY

TLS_CERTIFICATE_SCRIPT = "attempt=0; while [ $attempt -lt 120 ]; do if sudo /usr/local/sbin/gods-eye-view-tls-certificate 2>/dev/null; then exit 0; fi; attempt=$((attempt + 1)); sleep 5; done; exit 1"
HOST_STATE_SCRIPT = "attempt=0; while [ $attempt -lt 120 ]; do if [ -x /usr/local/sbin/gods-eye-view-host-state ] && sudo /usr/local/sbin/gods-eye-view-host-state 2>/dev/null; then exit 0; fi; if [ ! -x /usr/local/sbin/gods-eye-view-host-state ] && [ -x /usr/local/sbin/gods-eye-view-bootstrap-public-key ] && [ \"$(sudo /usr/local/sbin/gods-eye-view-bootstrap-public-key 2>/dev/null)\" = GODS_EYE_VIEW_BOOTSTRAP_READY ]; then echo GODS_EYE_VIEW_HOST_RECOVERY_REQUIRED; exit 0; fi; attempt=$((attempt + 1)); sleep 5; done; echo GODS_EYE_VIEW_HOST_RECOVERY_REQUIRED"


class HostBootstrapMismatch(ValueError):
    pass


def host_revision(bundle_digest):
    template = hashlib.sha256((ROOT / "terraform/templatefile/user_data.sh").read_bytes()).hexdigest()
    return hashlib.sha256((bundle_digest + ":" + template).encode()).hexdigest()


def verify_host_state(text, expected_digest):
    if not re.fullmatch(r"[a-f0-9]{64}", expected_digest) or text.strip() != "GODS_EYE_VIEW_HOST_V2 " + expected_digest:
        raise HostBootstrapMismatch("Host bootstrap differs from this release; explicit host recovery is required before Update")
    return expected_digest


def verify_active_images(text, assets):
    expected = {item["component"].upper() + "_IMAGE=" + item["image_id"] for item in assets}
    lines = text.strip().splitlines()
    if len(lines) != 3 or set(lines) != expected:
        raise ValueError("Active VM receipt differs from the requested images; preserve the previous release")
    return True


def certificate_binding(text, origin):
    """Bind the public certificate received through authenticated OCI to the VM IP."""
    import ipaddress
    from datetime import datetime, timezone
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    try:
        parsed = urlsplit(origin)
        host = ipaddress.ip_address(parsed.hostname)
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or parsed.port is not None:
            raise ValueError()
        if len(text) > 8192 or "PRIVATE KEY" in text or text.count("-----BEGIN CERTIFICATE-----") != 1:
            raise ValueError()
        cert = x509.load_pem_x509_certificate(text.encode())
        if text.strip() != cert.public_bytes(serialization.Encoding.PEM).decode().strip():
            raise ValueError()
        key = cert.public_key()
        now = datetime.now(timezone.utc)
        if (not isinstance(key, rsa.RSAPublicKey) or key.key_size < 3072
                or cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress) != [host]
                or not cert.not_valid_before_utc <= now < cert.not_valid_after_utc):
            raise ValueError()
        return {"certificate_pem": cert.public_bytes(serialization.Encoding.PEM).decode(),
            "fingerprint_sha256": cert.fingerprint(hashes.SHA256()).hex()}
    except (TypeError, ValueError, x509.ExtensionNotFound):
        raise ValueError("VM certificate does not match the allocated HTTPS IP") from None


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


def deliver(context, config, signer, storage):
    import oci
    outputs = context["terraform_outputs"]
    expected = binding(context["deployment_id"], config["user"], config["fingerprint"])
    client = oci.compute_instance_agent.ComputeInstanceAgentClient(config, signer=signer)
    fetch_vm_public_output(client, oci, outputs["compartment_ocid"], outputs["instance_id"],
        script=HOST_STATE_SCRIPT, parser=lambda text: verify_host_state(text, host_revision(context["inputs"]["vm_bundle_sha256"])))
    from image_assets import stage_handoff
    assets = stage_handoff(context, storage)
    public = fetch_bootstrap_public_key(client, oci,
        outputs["compartment_ocid"], outputs["instance_id"])
    updating = public == BOOTSTRAP_READY
    if updating:
        # Updates use a fresh recipient key; the authorized operator binding stays fixed.
        run_command(client, oci, outputs, "sudo /bin/bash /opt/gods-eye-view/docker/bootstrap.sh prepare",
            context["deployment_id"] + "-prepare-" + context["inputs"]["source_commit_sha"][:12])
        public = fetch_bootstrap_public_key(client, oci, outputs["compartment_ocid"], outputs["instance_id"])
        if public == BOOTSTRAP_READY:
            raise ValueError("VM did not prepare a fresh bootstrap recipient")
    # The VM generates its TLS private key locally; only the operator envelope leaves the runner.
    payload = {"config": render_runtime_oci_config(config), "key": Path(config["key_file"]).read_text(encoding="utf-8"),
        "runtime_env": runtime_environment(context, assets), "image_assets": json.dumps(assets, sort_keys=True)}
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
    # systemd joins the first-boot job or starts a single receiver on Update/Resume.
    run_command(client, oci, outputs, "sudo /usr/bin/systemctl start gods-eye-view-receiver.service",
        context["deployment_id"] + "-activate-" + context["inputs"]["source_commit_sha"][:12])
    fetch_vm_public_output(client, oci, outputs["compartment_ocid"], outputs["instance_id"],
        script="sudo /usr/local/sbin/gods-eye-view-active-images", parser=lambda text: verify_active_images(text, assets))
    certificate = fetch_vm_public_output(client, oci, outputs["compartment_ocid"], outputs["instance_id"],
        script=TLS_CERTIFICATE_SCRIPT, parser=lambda text: certificate_binding(text, outputs["public_origin"]))
    return certificate
