"""Exact VM Run Command public-key retrieval; extracted from frozen source."""
from native_api import ReconcileError, _sleep
BOOTSTRAP_READY = "GODS_EYE_VIEW_BOOTSTRAP_READY"
PUBLIC_KEY_SCRIPT = "attempt=0; while [ $attempt -lt 120 ]; do if [ -x /usr/local/sbin/gods-eye-view-bootstrap-public-key ]; then exec sudo /usr/local/sbin/gods-eye-view-bootstrap-public-key; fi; attempt=$((attempt + 1)); sleep 5; done; exit 1"
def parse_public_key_output(text: str) -> str:
    if text.strip() == BOOTSTRAP_READY:
        return BOOTSTRAP_READY
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    public_key = "\n".join(lines) + "\n"
    if "PRIVATE KEY" in public_key or not public_key.startswith("-----BEGIN PUBLIC KEY-----"):
        raise ReconcileError("Run Command did not return a public-only PEM")
    if not public_key.rstrip().endswith("-----END PUBLIC KEY-----"):
        raise ReconcileError("Run Command returned an incomplete public key")
    return public_key


def fetch_bootstrap_public_key(
    client: Any,
    oci_module: Any,
    compartment_id: str,
    instance_id: str,
    *,
    attempts: int = 150,
    create_attempts: int = 60,
) -> str:
    models = oci_module.compute_instance_agent.models
    details = models.CreateInstanceAgentCommandDetails(
        compartment_id=compartment_id,
        execution_time_out_in_seconds=660,
        display_name="aidp-lab-bootstrap-public-key",
        target=models.InstanceAgentCommandTarget(instance_id=instance_id),
        content=models.InstanceAgentCommandContent(
            source=models.InstanceAgentCommandSourceViaTextDetails(text=PUBLIC_KEY_SCRIPT),
            output=models.InstanceAgentCommandOutputViaTextDetails(),
        ),
    )
    command = None
    for attempt in range(create_attempts):
        try:
            command = client.create_instance_agent_command(details).data
            break
        except oci_module.exceptions.ServiceError as exc:
            if exc.status not in {403, 404, 409, 429, 500, 502, 503, 504} or attempt + 1 == create_attempts:
                raise ReconcileError(f"Compute Run Command submission failed with OCI {exc.status}") from exc
            _sleep(5)
    if command is None:
        raise ReconcileError("Compute Run Command submission did not complete")
    command_id = str(getattr(command, "id", "") or "")
    if not command_id:
        raise ReconcileError("Compute Run Command did not return a command OCID")
    terminal = {"FAILED", "TIMED_OUT", "CANCELED"}
    for _ in range(attempts):
        try:
            execution = client.get_instance_agent_command_execution(command_id, instance_id).data
        except oci_module.exceptions.ServiceError as exc:
            if exc.status == 404:
                _sleep(5)
                continue
            raise ReconcileError(f"Compute Run Command status failed with OCI {exc.status}") from exc
        state = str(getattr(execution, "lifecycle_state", "") or "").upper()
        if state == "SUCCEEDED":
            content = getattr(execution, "content", None)
            return parse_public_key_output(str(getattr(content, "text", "") or ""))
        if state in terminal:
            raise ReconcileError(f"Compute Run Command failed with state {state}")
        _sleep(5)
    raise ReconcileError("Timed out waiting for the VM bootstrap state Run Command")
