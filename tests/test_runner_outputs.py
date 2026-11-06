"""Exercise hooks with the manifest-filtered Terraform state supplied by Deploy Studio."""
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "terraform/hooks"))
sys.path.insert(0, str(ROOT / "scripts/deployment"))
sys.path.insert(0, str(ROOT / "apps/backend"))
import gods_eye_view_bootstrap as native
from first_install import compartment_scope
from post_apply import resolve_workspace
from vm_delivery import runtime_environment


TERRAFORM_OUTPUTS = {
    "ai_data_platform_id", "existing_workspace_key", "default_workspace_name",
    "objectstorage_namespace", "medallion_bucket_names", "artifacts_bucket_name",
    "compartment_ocid", "instance_id", "admin_user_ocid", "identity_domain_id",
    "identity_domain_url", "gods_eye_view_group_id", "viewer_oidc_app_name",
    "public_origin", "agent_model_id",
}
HOOK_OUTPUTS = {
    "workspace_key", "application_url", "gods_eye_view_native_status",
    "gods_eye_view_snapshot_version", "viewer_certificate_sha256", "viewer_certificate_pem",
}


def manifest():
    return json.loads((ROOT / "terraform/deploy-studio.json").read_text(encoding="utf-8"))


def project_state(state, names):
    # Model CTN declared_state_outputs for a JSON Terraform state, not the full state.
    return {name: item["value"] for name in names
        if isinstance(item := state["outputs"].get(name), dict)
        and item.get("sensitive") is not True and "value" in item}


@pytest.fixture
def state():
    values = {
        "ai_data_platform_id": "ocid1.aidataplatform.oc1.iad.selected",
        "existing_workspace_key": "selected-workspace",
        "default_workspace_name": "viewer-workspace",
        "objectstorage_namespace": "selected_namespace",
        "medallion_bucket_names": {layer: "selected-" + layer for layer in ("landing", "bronze", "silver", "gold")},
        "artifacts_bucket_name": "selected-artifacts",
        "compartment_ocid": "ocid1.compartment.oc1..selected",
        "instance_id": "ocid1.instance.oc1.iad.selected",
        "admin_user_ocid": "ocid1.user.oc1..administrator",
        "identity_domain_id": "ocid1.domain.oc1..selected",
        "identity_domain_url": "https://selected.identity.oraclecloud.com",
        "gods_eye_view_group_id": "readers-group-id",
        "viewer_oidc_app_name": "viewer-oidc-application",
        "public_origin": "https://192.0.2.25",
        "agent_model_id": "selected-agent-model",
    }
    assert set(values) == TERRAFORM_OUTPUTS
    outputs = {name: {"value": value, "sensitive": False} for name, value in values.items()}
    outputs["undeclared_internal_value"] = {"value": "must-stay-in-state", "sensitive": False}
    outputs["viewer_certificate_pem"] = {"value": "sensitive-fixture-must-be-excluded", "sensitive": True}
    return {"version": 4, "outputs": outputs}


@pytest.fixture
def context(state):
    return {
        "schema_version": 1, "deployment_id": "deployment-output-regression",
        "project_id": "aidp-ai-gods-eye-view", "region": "us-ashburn-1",
        "source": {"repository": "https://github.com/jgangini/aidp-ai-gods-eye-view",
            "ref": "v1.0.3", "commit_sha": "a" * 40},
        "compartment": {"id": "ocid1.compartment.oc1..selected", "name": "viewer"},
        "terraform_outputs": project_state(state, manifest()["outputs"]),
        "inputs": {"aidp_mode": "new", "admin_user_ocid": "ocid1.user.oc1..administrator",
            "identity_domain_id": "ocid1.domain.oc1..selected", "release_tag": "v1.0.3",
            "source_commit_sha": "a" * 40},
    }


class WorkspaceApi:
    def __init__(self, region="us-ashburn-1", platform="selected", signer=None, deployment="selected", **kwargs):
        self.base = "https://workbench.example.invalid/selected"
        self.calls = []

    def request(self, method, path):
        assert (method, path) == ("GET", "/workspaces/selected-workspace")
        self.calls.append((method, path))
        return SimpleNamespace(body={"key": "selected-workspace", "lifecycleState": "ACTIVE"})

    def list_all(self, path):
        assert path == "/workspaces"
        self.calls.append(("GET", path))
        return [{"key": "unrelated-workspace", "displayName": "other", "state": "ACTIVE"},
            {"key": "selected-workspace", "displayName": "viewer-workspace", "state": "ACTIVE"}]


def assets():
    return [{"component": component, "object_name": "releases/" + "a" * 40 + "/" + prefix + "-image-amd64.tar.gz",
        "archive_sha256": "b" * 64, "image_id": "sha256:" + digit * 64,
        "image_tag": prefix + ":" + "a" * 40}
        for component, prefix, digit in (("api", "gods-eye-view-api", "1"),
            ("viewer", "gods-eye-view", "2"), ("gateway", "gods-eye-view-gateway", "3"))]


def test_manifest_declares_only_safe_terraform_and_post_apply_outputs():
    names = manifest()["outputs"]
    assert len(names) == len(set(names))
    assert set(names) == TERRAFORM_OUTPUTS | HOOK_OUTPUTS
    source = (ROOT / "terraform/l_outputs.tf").read_text(encoding="utf-8")
    assert set(re.findall(r'output\s+"([a-z_]+)"\s*\{', source)) == TERRAFORM_OUTPUTS
    assert not re.search(r"\bsensitive\s*=\s*true\b", source)
    tree = ast.parse((ROOT / "terraform/hooks/post_apply.py").read_text(encoding="utf-8"))
    published = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            for key, value in zip(node.value.keys, node.value.values):
                if isinstance(key, ast.Constant) and key.value == "outputs" and isinstance(value, ast.Dict):
                    published.append({item.value for item in value.keys if isinstance(item, ast.Constant)})
    assert published == [HOOK_OUTPUTS]


@pytest.mark.parametrize("mode", ["new", "existing"])
def test_projected_outputs_resolve_workspace_and_bind_vm_environment(context, mode):
    context["inputs"]["aidp_mode"] = mode
    outputs = context["terraform_outputs"]
    assert set(outputs) == TERRAFORM_OUTPUTS
    assert compartment_scope(context, {"tenancy": "ocid1.tenancy.oc1..operator"}) == outputs["compartment_ocid"]
    api = WorkspaceApi()
    outputs["workspace_key"] = resolve_workspace(api, context, outputs)
    assert outputs["workspace_key"] == "selected-workspace"
    assert api.calls == [("GET", "/workspaces/selected-workspace" if mode == "existing" else "/workspaces")]
    actual = dict(line.split("=", 1) for line in runtime_environment(context, assets()).splitlines())
    assert actual == {
        "ADMIN_USER_OCID": "ocid1.user.oc1..administrator", "IDENTITY_DOMAIN_ID": "ocid1.domain.oc1..selected",
        "IDENTITY_DOMAIN_URL": "https://selected.identity.oraclecloud.com",
        "IDENTITY_GODS_EYE_VIEW_GROUP_ID": "readers-group-id", "IDENTITY_VIEWER_APP_NAME": "viewer-oidc-application",
        "VIEWER_OIDC_REDIRECT_URI": "https://192.0.2.25/api/auth/oci/callback",
        "AIDP_PLATFORM_ID": "ocid1.aidataplatform.oc1.iad.selected", "AIDP_REGION": "us-ashburn-1",
        "AIDP_WORKSPACE_KEY": "selected-workspace", "COMPARTMENT_ID": "ocid1.compartment.oc1..selected",
        "OBJECTSTORAGE_NAMESPACE": "selected_namespace", "BUCKET_NAME": "selected-landing",
        "GODS_EYE_CONTROL_BUCKET": "selected-gold", "ARTIFACTS_BUCKET_NAME": "selected-artifacts",
        "LAB_MARKER": "deployment-output-regression", "GODS_EYE_VIEW_ENABLED": "true",
        "GODS_EYE_VIEW_MODE": "oci", "COOKIE_SECURE": "true", "PUBLIC_HOST": "192.0.2.25",
        "API_IMAGE": "sha256:" + "1" * 64, "VIEWER_IMAGE": "sha256:" + "2" * 64,
        "GATEWAY_IMAGE": "sha256:" + "3" * 64,
    }


def test_projected_outputs_construct_native_runtime_before_any_external_mutation(context, monkeypatch):
    class RuntimeCaptured(Exception):
        pass

    captured = {}
    def capture(api, agent_api, storage, runtime, workspace):
        captured.update(runtime)
        assert workspace == "selected-workspace"
        raise RuntimeCaptured()

    monkeypatch.setattr(native, "runtime_archive", lambda: b"test-runtime")
    monkeypatch.setattr(native, "identity_hash", lambda config: "c" * 64)
    monkeypatch.setattr(native, "initialize_controls", capture)
    # No storage methods exist: this check deliberately ends before native installation.
    with pytest.raises(RuntimeCaptured):
        native.bootstrap_gods_eye_view(WorkspaceApi(), context, context["terraform_outputs"], {}, object(), object(),
            {"workspace_key": "selected-workspace", "catalog_name": "oci_medallion"},
            deadline=float("inf"), ensure_folder=None)
    assert captured["namespace"] == "selected_namespace"
    assert captured["bucket"] == "selected-gold"
    assert captured["landing_bucket"] == "selected-landing"
    assert captured["compartment_id"] == "ocid1.compartment.oc1..selected"
    assert captured["model_id"] == "selected-agent-model"
    assert captured["catalog"] == "oci_medallion"


def test_actual_cloudtechnext_manifest_parser_and_output_projection(state):
    """Run the external consumer when its checkout is available; portable checks above need no CTN."""
    configured = os.environ.get("CLOUDTECHNEXT_SOURCE_ROOT")
    ctn_root = Path(configured) if configured else ROOT.parent / "codex-cloudtechnext"
    backend = ctn_root / "app/backend"
    if not (backend / "app/services/deployment_source.py").is_file():
        if configured:
            pytest.fail("Configured CloudTechNext source checkout is unavailable")
        pytest.skip("Optional real CTN consumer check requires CLOUDTECHNEXT_SOURCE_ROOT")
    program = '''
import ast, copy, io, json, sys, zipfile
from pathlib import Path, PurePosixPath
from typing import Any
sys.path.insert(0, sys.argv[1])
from app.services.deployment_source import _read_manifest
payload = json.load(sys.stdin)
buffer = io.BytesIO()
with zipfile.ZipFile(buffer, "w") as archive:
    archive.writestr("terraform/deploy-studio.json", json.dumps(payload["manifest"]))
buffer.seek(0)
with zipfile.ZipFile(buffer) as archive:
    info = archive.getinfo("terraform/deploy-studio.json")
    model, _ = _read_manifest(archive, [(info, PurePosixPath(info.filename))])
assert model.schema_version == 2 and model.form.groups[0].id == "credentials"
for version in (1, 2):
    invalid = copy.deepcopy(payload["manifest"])
    invalid["schema_version"] = version
    del invalid["form"]["groups"]
    legacy = io.BytesIO()
    with zipfile.ZipFile(legacy, "w") as archive:
        archive.writestr("terraform/deploy-studio.json", json.dumps(invalid))
    legacy.seek(0)
    with zipfile.ZipFile(legacy) as archive:
        info = archive.getinfo("terraform/deploy-studio.json")
        try:
            _read_manifest(archive, [(info, PurePosixPath(info.filename))])
        except ValueError:
            pass
        else:
            raise AssertionError("Runner accepted a manifest without the schema 2 layout")
# Load the actual pure projection without initializing CTN's database/services.
path = Path(sys.argv[1]) / "app/services/oci_artifacts.py"
tree = ast.parse(path.read_text(encoding="utf-8"))
function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "declared_state_outputs")
scope = {"Any": Any, "json": json}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), scope)
projected = scope["declared_state_outputs"](payload["state"], model.outputs)
print(json.dumps({"names": model.outputs, "projected": projected}))
'''
    result = subprocess.run([sys.executable, "-c", program, str(backend)],
        input=json.dumps({"manifest": manifest(), "state": state}), capture_output=True,
        text=True, check=True, timeout=60, cwd=ROOT)
    actual = json.loads(result.stdout)
    assert actual["names"] == manifest()["outputs"]
    assert actual["projected"] == project_state(state, actual["names"])
    assert set(actual["projected"]) == TERRAFORM_OUTPUTS
