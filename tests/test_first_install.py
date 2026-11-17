import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace as Item

import pytest
from oci.response import Response

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "terraform/hooks"))
sys.path.insert(0, str(ROOT / "scripts/deployment"))
from first_install import compartment_scope, vm_inputs
from vm_delivery import certificate_binding, verify_host_state, HostBootstrapMismatch
from build_vm_bundle import build


class Compute:
    image = Item(id="ocid1.image.oc1..platform", compartment_id=None,
        operating_system="Oracle Linux", operating_system_version="9", lifecycle_state="AVAILABLE")
    def __init__(self):
        self.list_calls = 0
    def list_images(self, scope, **kwargs):
        self.list_calls += 1
        assert scope == "ocid1.compartment.oc1..selected" and kwargs["shape"] == "VM.Standard.E5.Flex"
        return Response(200, {}, [self.image], None)
    def get_image(self, image_id):
        assert image_id == self.image.id
        return Item(data=self.image)
    def list_shapes(self, scope, **kwargs):
        assert kwargs["image_id"] == self.image.id
        return Response(200, {}, [Item(shape="VM.Standard.E5.Flex")], None)


def context():
    return {"inputs": {"source_commit_sha": "a" * 40},
        "compartment": {"id": "ocid1.compartment.oc1..selected", "name": "selected"},
        "terraform_outputs": {"compartment_ocid": "ocid1.compartment.oc1..selected"}}


def identity(*names):
    return Item(list_availability_domains=lambda tenancy, **_kw: Response(200, {}, [Item(name=n) for n in names], None))


@pytest.mark.parametrize("mode,selection,expected", [
    ("new", "aidp-gods-eye-view", "ocid1.tenancy.oc1..operator"),
    ("existing", "ocid1.compartment.oc1..selected", "ocid1.compartment.oc1..selected"),
])
def test_vm_discovery_uses_the_actual_string_preflight_contract(mode, selection, expected):
    calls = []
    compute = Compute()
    original_images, original_shapes = compute.list_images, compute.list_shapes
    def images(scope, **kw):
        calls.append(scope)
        return original_images("ocid1.compartment.oc1..selected", **kw)
    def shapes(scope, **kw):
        calls.append(scope)
        return original_shapes("ocid1.compartment.oc1..selected", **kw)
    compute.list_images, compute.list_shapes = images, shapes
    c = {"schema_version": 1, "deployment_id": "deployment-1", "project_id": "aidp-ai-gods-eye-view",
        "source": {"repository": "https://github.com/jgangini/aidp-ai-gods-eye-view", "ref": "v1.0.3", "commit_sha": "a" * 40},
        "region": "us-chicago-1", "compartment": selection, "compartment_mode": mode,
        "inputs": {"source_commit_sha": "a" * 40}}
    result = vm_inputs(c, {"tenancy": "ocid1.tenancy.oc1..operator"}, compute, identity("AD-1"))
    assert result["image_ocid"] == compute.image.id
    assert calls == [expected, expected]


def test_resolved_postapply_compartment_matches_terraform_outputs():
    c = {"compartment": {"id": "ocid1.compartment.oc1..selected", "name": "selected"},
        "terraform_outputs": {"compartment_ocid": "ocid1.compartment.oc1..selected"}}
    assert compartment_scope(c, {"tenancy": "ocid1.tenancy.oc1..operator"}) == c["compartment"]["id"]
    c["terraform_outputs"]["compartment_ocid"] = "ocid1.compartment.oc1..other"
    with pytest.raises(ValueError, match="differ"):
        compartment_scope(c, {})


@pytest.mark.parametrize("context", [
    {"compartment": "missing-mode"},
    {"compartment": "display-name", "compartment_mode": "existing"},
    {"compartment": "", "compartment_mode": "existing"},
    {"compartment": {"name": "missing-id"}},
    {"compartment": None, "compartment_mode": "new"},
    {"compartment": "name", "compartment_mode": "unknown"},
])
def test_invalid_runner_compartment_never_falls_back_to_tenancy(context):
    with pytest.raises(ValueError):
        vm_inputs(context, {"tenancy": "ocid1.tenancy.oc1..operator"}, object(), object())


def test_first_install_resolves_native_image_domain_and_bundle_without_user_artifact_inputs():
    compute = Compute()
    result = vm_inputs(context(), {"tenancy": "tenancy"}, compute, identity("AD-2", "AD-1"))
    assert result["image_ocid"] == compute.image.id and result["availability_domain"] == "AD-1"
    assert result["vm_bundle_sha256"] == hashlib.sha256(build(ROOT)).hexdigest()
    assert result["vm_bundle_object"] == f"releases/{'a' * 40}/vm-bootstrap-{result['vm_bundle_sha256']}.zip"
    assert compute.list_calls == 1


def test_resume_keeps_the_recorded_image_and_domain_instead_of_resampling():
    c, compute = context(), Compute()
    c["inputs"].update(image_ocid=compute.image.id, availability_domain="AD-2")
    result = vm_inputs(c, {"tenancy": "tenancy"}, compute, identity("AD-1", "AD-2"))
    assert result["availability_domain"] == "AD-2" and compute.list_calls == 0


def test_automatic_domain_selection_uses_the_next_compatible_domain():
    compute = Compute()
    compute.list_shapes = lambda *_args, **kw: Response(200, {}, [Item(shape="VM.Standard.E5.Flex")] if kw["availability_domain"] == "AD-2" else [], None)
    result = vm_inputs(context(), {"tenancy": "tenancy"}, compute, identity("AD-1", "AD-2"))
    assert result["availability_domain"] == "AD-2"


def test_image_and_shape_discovery_follow_sdk_pagination():
    compute = Compute()
    image_pages, shape_pages = [], []
    def images(*_args, **kw):
        image_pages.append(kw.get("page"))
        if kw.get("page") is None:
            return Response(200, {"opc-next-page": "public-page"}, [Item(compartment_id="custom")], None)
        return Response(200, {}, [compute.image], None)
    def shapes(*_args, **kw):
        shape_pages.append(kw.get("page"))
        return Response(200, {"opc-next-page": "compatible"}, [], None) if kw.get("page") is None else Response(200, {}, [Item(shape="VM.Standard.E5.Flex")], None)
    compute.list_images, compute.list_shapes = images, shapes
    result = vm_inputs(context(), {"tenancy": "tenancy"}, compute, identity("AD-1"))
    assert result["image_ocid"] == compute.image.id
    assert image_pages == [None, "public-page"] and shape_pages == [None, "compatible"]


def test_host_protocol_and_bundle_must_match_before_an_update():
    assert verify_host_state("GODS_EYE_VIEW_HOST_V2 " + "a" * 64, "a" * 64) == "a" * 64
    for text in ("GODS_EYE_VIEW_HOST_RECOVERY_REQUIRED", "GODS_EYE_VIEW_HOST_V2 " + "b" * 64):
        with pytest.raises(HostBootstrapMismatch, match="explicit host recovery"):
            verify_host_state(text, "a" * 64)


@pytest.mark.parametrize("failure", ["images", "os", "domain", "shape"])
def test_first_install_fails_closed_when_no_compatible_target_exists(failure):
    c, compute, domains = context(), Compute(), identity("AD-1")
    if failure == "images": compute.list_images = lambda *_args, **_kw: Response(200, {}, [], None)
    if failure == "os": compute.image = Item(**{**vars(compute.image), "operating_system_version": "10"})
    if failure == "domain": c["inputs"]["availability_domain"] = "unknown"
    if failure == "shape": compute.list_shapes = lambda *_args, **_kw: Response(200, {}, [], None)
    with pytest.raises(ValueError):
        vm_inputs(c, {"tenancy": "tenancy"}, compute, domains)


def test_first_boot_form_has_no_origin_certificate_or_derived_artifact_requirements():
    m = json.loads((ROOT / "terraform/deploy-studio.json").read_text(encoding="utf-8"))
    names = {field["name"] for field in m["form"]["fields"]}
    assert not {"public_origin", "tls_certificate", "tls_key", "image_ocid", "availability_domain", "vm_bundle_object", "vm_bundle_sha256"} & names
    assert {"image_ocid", "availability_domain", "vm_bundle_object", "vm_bundle_sha256"} <= set(m["preflight"]["output_inputs"])
    assert m["post_apply"]["secret_inputs"] == []


def test_runner_binds_public_certificate_to_the_ip_and_returns_no_private_key(tmp_path):
    from bootstrap_credentials import ensure_viewer_tls
    tls = ensure_viewer_tls(tmp_path, "127.0.0.1")
    result = certificate_binding(tls["certificate_pem"], "https://127.0.0.1")
    assert result == tls and len(result["fingerprint_sha256"]) == 64
    from post_apply import viewer_ssl_context
    trust = viewer_ssl_context(tls["certificate_pem"])
    assert trust.check_hostname and trust.cert_store_stats() == {"x509": 1, "crl": 0, "x509_ca": 0}
    for text, origin in ((tls["certificate_pem"], "https://127.0.0.2"),
            (tls["certificate_pem"], "http://127.0.0.1"),
            ((tmp_path / "tls/privkey.pem").read_text(), "https://127.0.0.1")):
        with pytest.raises(ValueError, match="allocated HTTPS IP"):
            certificate_binding(text, origin)


@pytest.mark.parametrize("resume_key_exists,old_receipt", [(True, False), (False, False), (True, True)])
def test_delivery_starts_one_receiver_on_resume_and_checks_active_images(tmp_path, monkeypatch, resume_key_exists, old_receipt):
    import oci
    import image_assets
    import vm_delivery as vm
    from bootstrap_credentials import ensure_viewer_tls
    tls = ensure_viewer_tls(tmp_path / "vm", "127.0.0.1")
    assets = [{"component": component, "object_name": f"releases/{'a' * 40}/{prefix}-image-amd64.tar.gz",
        "archive_sha256": "d" * 64, "image_id": "sha256:" + letter * 64, "image_tag": prefix + ":" + "a" * 40}
        for component, prefix, letter in (("api", "gods-eye-view-api", "a"), ("viewer", "gods-eye-view", "b"), ("gateway", "gods-eye-view-gateway", "c"))]
    c = {"deployment_id": "deployment-1", "region": "us-chicago-1", "inputs": {"source_commit_sha": "a" * 40,
        "vm_bundle_sha256": "b" * 64, "admin_user_ocid": "ocid1.user.oc1..selected", "identity_domain_id": "domain"},
        "terraform_outputs": {"compartment_ocid": "compartment", "instance_id": "instance", "identity_domain_url": "https://idcs.example",
            "gods_eye_view_group_id": "readers", "viewer_oidc_app_name": "viewer", "public_origin": "https://127.0.0.1",
            "ai_data_platform_id": "platform", "workspace_key": "workspace", "objectstorage_namespace": "namespace",
            "artifacts_bucket_name": "artifacts", "medallion_bucket_names": {"landing": "landing", "gold": "gold"}}}
    key = tmp_path / "operator.pem"
    key.write_text("test-key-material")
    config = {"user": "ocid1.user.oc1..operator", "fingerprint": "1" * 32, "tenancy": "tenancy", "region": c["region"], "key_file": str(key)}
    commands, payloads, stored = [], [], []
    monkeypatch.setattr(oci.compute_instance_agent, "ComputeInstanceAgentClient", lambda *_args, **_kw: Item())
    monkeypatch.setattr(image_assets, "stage_handoff", lambda *_args: assets)
    keys = iter(("test-public-key",) if resume_key_exists else (vm.BOOTSTRAP_READY, "test-public-key"))
    monkeypatch.setattr(vm, "fetch_bootstrap_public_key", lambda *_args: next(keys))
    monkeypatch.setattr(vm, "run_command", lambda _client, _oci, _out, command, _token: commands.append(command))
    monkeypatch.setattr(vm, "encrypt", lambda public, payload, expected: payloads.append(payload) or b"encrypted-test-envelope")
    def public_output(*_args, script, parser):
        if script == vm.HOST_STATE_SCRIPT:
            text = "GODS_EYE_VIEW_HOST_V2 " + vm.host_revision("b" * 64)
        elif script == vm.TLS_CERTIFICATE_SCRIPT:
            text = tls["certificate_pem"]
        else:
            text = "\n".join(item["component"].upper() + "_IMAGE=" + ("sha256:" + "f" * 64 if old_receipt else item["image_id"]) for item in assets)
        return parser(text)
    monkeypatch.setattr(vm, "fetch_vm_public_output", public_output)
    storage = Item(put_object=lambda *_args, **_kw: stored.append(True))
    if old_receipt:
        with pytest.raises(ValueError, match="Active VM receipt"):
            vm.deliver(c, config, None, storage)
    else:
        assert vm.deliver(c, config, None, storage) == tls
    assert "sudo /usr/bin/systemctl start gods-eye-view-receiver.service" in commands
    assert len(payloads) == 1 and set(payloads[0]) == {"config", "key", "runtime_env", "image_assets"}
    assert bool([command for command in commands if command.endswith(" prepare")]) == (not resume_key_exists)


@pytest.mark.parametrize("wrong_binding", [False, True])
def test_completed_receiver_is_idempotent_and_checks_its_operator_binding(tmp_path, monkeypatch, wrong_binding):
    import time
    import bootstrap_credentials as credentials
    expected = credentials.binding("deployment-1", "ocid1.user.oc1..operator", "1" * 32)
    receipt = tmp_path / "bootstrap/receipt.json"
    receipt.parent.mkdir()
    receipt.write_text(json.dumps({**expected, "deployment_id": "other"} if wrong_binding else expected))
    class Missing(Exception): status = 404
    def missing(*_args): raise Missing()
    fake = Item(object_storage=Item(ObjectStorageClient=lambda *_args, **_kw: Item(get_object=missing)),
        auth=Item(signers=Item(InstancePrincipalsSecurityTokenSigner=lambda: None)), exceptions=Item(ServiceError=Missing))
    monkeypatch.setitem(sys.modules, "oci", fake)
    monkeypatch.setattr(time, "sleep", lambda _: pytest.fail("Completed delivery must not wait for the consumed object"))
    template = (ROOT / "terraform/templatefile/user_data.sh").read_text(encoding="utf-8")
    source = template.split("cat > /opt/gods-eye-view/receive.py <<'PY'\n", 1)[1].split("\nPY", 1)[0]
    for name, value in {"deployment_id": "deployment-1", "operator_user_ocid": expected["operator_user_ocid"],
            "operator_fingerprint": "1" * 32, "namespace": "namespace", "bucket": "bucket"}.items():
        source = source.replace("${" + name + "}", value)
    source = source.replace("/etc/gods-eye-view", tmp_path.as_posix())
    if wrong_binding:
        with pytest.raises(SystemExit, match="another operator"):
            exec(compile(source, "generated-receiver.py", "exec"), {})
    else:
        exec(compile(source, "generated-receiver.py", "exec"), {})


def test_public_certificate_helper_never_prints_appended_private_material(tmp_path):
    import shlex
    import shutil
    import subprocess
    from bootstrap_credentials import ensure_viewer_tls
    executable = shutil.which("openssl")
    if not executable and Path("C:/Program Files/Git/usr/bin/openssl.exe").is_file():
        executable = "C:/Program Files/Git/usr/bin/openssl.exe"
    if not executable:
        pytest.skip("Requires the existing OpenSSL executable used by the VM")
    tls = ensure_viewer_tls(tmp_path, "127.0.0.1")
    certificate = tmp_path / "tls/fullchain.pem"
    certificate.write_bytes(certificate.read_bytes() + (tmp_path / "tls/privkey.pem").read_bytes())
    template = (ROOT / "terraform/templatefile/user_data.sh").read_text(encoding="utf-8")
    command = next(line for line in template.splitlines() if line.startswith("openssl x509 "))
    args = shlex.split(command)
    args[0], args[args.index("-in") + 1] = executable, str(certificate)
    output = subprocess.check_output(args, text=True)
    assert output == tls["certificate_pem"] and "PRIVATE KEY" not in output
