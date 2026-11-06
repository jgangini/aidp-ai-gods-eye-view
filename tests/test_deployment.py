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
from post_apply import verify_bucket_outputs
import gods_eye_view_bootstrap as native
from types import SimpleNamespace
from test_bucket_selection import selections


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
    buckets = selections(("new",) * 5)
    context = {"source": {"repository": "https://github.com/jgangini/aidp-ai-gods-eye-view", "commit_sha": "a" * 40, "ref": "v2.1.0"}, "inputs": buckets}
    assert source_context(context)["inputs"]["source_commit_sha"] == "a" * 40
    assert source_context(context)["inputs"]["release_tag"] == "v2.1.0"
    assert source_context(context)["inputs"]["name"] == "aidp-gods-eye-view"
    assert source_context({**context, "inputs": {**buckets, "name": "existing-prefix"}})["inputs"]["name"] == "existing-prefix"
    with pytest.raises(ValueError, match="differs"):
        source_context({**context, "inputs": {"source_commit_sha": "b" * 40}})
    with pytest.raises(ValueError, match="Release tag"):
        source_context({**context, "inputs": {"release_tag": "v2.0.0"}})
    with pytest.raises(ValueError, match="stable source"):
        source_context({**context, "source": {**context["source"], "ref": "main"}})


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
        "aidp_mode": "new", **selections(("new",) * 5)}
    assert validate_inputs(inputs)["aidp_mode"] == "new"
    with pytest.raises(ValueError):
        validate_inputs({**inputs, "aidp_mode": "existing"})
    with pytest.raises(ValueError):
        validate_inputs({**inputs, "artifacts_bucket_name": "selected-gold"})


def test_envelope_is_bound_authenticated_and_single_use(tmp_path):
    import hashlib
    operator = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    fingerprint = hashlib.md5(operator.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo), usedforsecurity=False).hexdigest()
    expected = envelope.binding("deployment-1", "ocid1.user.oc1..operator", fingerprint)
    public = envelope.generate_key(tmp_path / "bootstrap/private.pem")
    payload = {"config": f"[DEFAULT]\nuser=ocid1.user.oc1..operator\nfingerprint={fingerprint}\n",
        "key": operator.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode(),
        "runtime_env": "GODS_EYE_VIEW_MODE=oci\nPUBLIC_HOST=127.0.0.1\n",
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
    tls_key = (tmp_path / "tls/privkey.pem").read_bytes()
    tls_certificate = (tmp_path / "tls/fullchain.pem").read_bytes()
    assert not (tmp_path / "bootstrap/private.pem").exists()
    with pytest.raises(FileNotFoundError):
        envelope.consume(encrypted, tmp_path, expected)
    updated_public = envelope.generate_key(tmp_path / "bootstrap/private.pem")
    changed = envelope.encrypt(updated_public, {**payload, "runtime_env": "GODS_EYE_VIEW_MODE=oci\nPUBLIC_HOST=127.0.0.2\n"}, expected)
    with pytest.raises(ValueError, match="recovery"):
        envelope.consume(changed, tmp_path, expected)
    assert (tmp_path / "tls/privkey.pem").read_bytes() == tls_key
    assert (tmp_path / "tls/fullchain.pem").read_bytes() == tls_certificate
    assert (tmp_path / "runtime.env").read_text() == payload["runtime_env"]
    assert (tmp_path / "bootstrap/private.pem").exists()


def _auto_tls_envelope(tmp_path):
    import hashlib
    operator = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    fingerprint = hashlib.md5(operator.public_key().public_bytes(serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo), usedforsecurity=False).hexdigest()
    expected = envelope.binding("automatic-tls-test", "ocid1.user.oc1..operator", fingerprint)
    public = envelope.generate_key(tmp_path / "bootstrap/private.pem")
    payload = {"config": f"[DEFAULT]\nuser=ocid1.user.oc1..operator\nfingerprint={fingerprint}\n",
        "key": operator.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()).decode(),
        "runtime_env": "GODS_EYE_VIEW_MODE=oci\nPUBLIC_HOST=127.0.0.1\n",
        "image_assets": json.dumps([{"component":component,
            "object_name":"releases/" + "a" * 40 + "/" + prefix + "-image-amd64.tar.gz",
            "archive_sha256":"b" * 64,"image_id":"sha256:" + "c" * 64,"image_tag":prefix + ":" + "a" * 40}
            for component,prefix in (("api","gods-eye-view-api"),("viewer","gods-eye-view"),("gateway","gods-eye-view-gateway"))])}
    return public,payload,expected


@pytest.mark.parametrize("host", ["127.0.0.1", "2001:db8::123"])
def test_automatic_viewer_tls_is_ip_bound_non_ca_server_certificate_and_retained(tmp_path, host):
    import hashlib
    import ipaddress
    from datetime import datetime, timedelta, timezone
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.x509.oid import ExtendedKeyUsageOID
    before = datetime.now(timezone.utc)
    result = envelope.ensure_viewer_tls(tmp_path,host)
    certificate_path, key_path = tmp_path / "tls/fullchain.pem", tmp_path / "tls/privkey.pem"
    certificate = x509.load_pem_x509_certificate(result["certificate_pem"].encode())
    private_bytes = key_path.read_bytes()
    key = serialization.load_pem_private_key(private_bytes,password=None)
    assert isinstance(key,rsa.RSAPrivateKey) and key.key_size >= 3072
    assert certificate.public_key().public_numbers() == key.public_key().public_numbers()
    assert certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress) == [ipaddress.ip_address(host)]
    assert list(certificate.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value) == [ExtendedKeyUsageOID.SERVER_AUTH]
    constraints = certificate.extensions.get_extension_for_class(x509.BasicConstraints)
    assert constraints.critical and not constraints.value.ca and constraints.value.path_length is None
    assert before - timedelta(minutes=6) < certificate.not_valid_before_utc <= before
    assert before + timedelta(days=364) < certificate.not_valid_after_utc <= datetime.now(timezone.utc) + timedelta(days=365)
    assert result["fingerprint_sha256"] == hashlib.sha256(certificate.public_bytes(serialization.Encoding.DER)).hexdigest()
    certificate.verify_directly_issued_by(certificate)
    stat_before = certificate_path.stat().st_mtime_ns,key_path.stat().st_mtime_ns
    assert envelope.ensure_viewer_tls(tmp_path,host) == result
    assert key_path.read_bytes() == private_bytes
    assert (certificate_path.stat().st_mtime_ns,key_path.stat().st_mtime_ns) == stat_before
    assert set(result) == {"certificate_pem","fingerprint_sha256"}
    assert "PRIVATE KEY" not in json.dumps(result)


def test_generated_viewer_tls_uses_private_atomic_files(tmp_path, monkeypatch):
    import os
    import stat
    modes = []
    original = envelope.os.open
    def opened(path,flags,mode=0o777,*args,**kwargs):
        if str(path).endswith(".pending"):
            modes.append(mode)
        return original(path,flags,mode,*args,**kwargs)
    monkeypatch.setattr(envelope.os,"open",opened)
    envelope.ensure_viewer_tls(tmp_path,"127.0.0.1")
    assert modes == [0o600,0o600]
    if os.name != "nt":
        for name in ("fullchain.pem","privkey.pem"):
            assert stat.S_IMODE((tmp_path / "tls" / name).stat().st_mode) == 0o600


@pytest.mark.parametrize("host", ["example.com", "https://127.0.0.1", "127.0.0.1:443", "", " 127.0.0.1",
    "0.0.0.0", "::", "224.0.0.1", "fe80::1%eth0", None])
def test_bad_viewer_tls_host_creates_no_files(tmp_path, host):
    with pytest.raises(ValueError,match="PUBLIC_HOST"):
        envelope.ensure_viewer_tls(tmp_path,host)
    assert not (tmp_path / "tls").exists()


@pytest.mark.parametrize("kind", ["partial", "wrong-key", "wrong-host", "expired", "extra-private-material"])
def test_existing_tls_partial_mismatch_and_expiry_require_recovery_without_rotation(tmp_path, kind):
    from datetime import datetime, timedelta, timezone
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    envelope.ensure_viewer_tls(tmp_path,"127.0.0.1")
    certificate_path,key_path = tmp_path / "tls/fullchain.pem", tmp_path / "tls/privkey.pem"
    host = "127.0.0.1"
    if kind == "partial":
        certificate_path.unlink()
    elif kind == "wrong-key":
        other = rsa.generate_private_key(public_exponent=65537,key_size=3072)
        key_path.write_bytes(other.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    elif kind == "wrong-host":
        host = "127.0.0.2"
    elif kind == "extra-private-material":
        certificate_path.write_bytes(certificate_path.read_bytes()+key_path.read_bytes())
    else:
        original = x509.load_pem_x509_certificate(certificate_path.read_bytes())
        key = serialization.load_pem_private_key(key_path.read_bytes(),password=None)
        now = datetime.now(timezone.utc)
        builder = (x509.CertificateBuilder().subject_name(original.subject).issuer_name(original.issuer)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now-timedelta(days=2)).not_valid_after(now-timedelta(days=1)))
        for extension in original.extensions:
            builder = builder.add_extension(extension.value,extension.critical)
        certificate_path.write_bytes(builder.sign(key,hashes.SHA256()).public_bytes(serialization.Encoding.PEM))
    before = {path.name:path.read_bytes() for path in (certificate_path,key_path) if path.exists()}
    with pytest.raises(ValueError,match="recovery"):
        envelope.ensure_viewer_tls(tmp_path,host)
    assert {path.name:path.read_bytes() for path in (certificate_path,key_path) if path.exists()} == before


@pytest.mark.parametrize("change", ["operator", "profile", "assets", "extra", "external-tls-fields", "unknown-field", "missing-host", "duplicate-host", "invalid-host"])
def test_invalid_automatic_tls_payload_never_overwrites_credentials_or_environment(tmp_path, change):
    public,payload,expected = _auto_tls_envelope(tmp_path)
    (tmp_path / "runtime.env").write_text("existing environment")
    if change == "operator":
        key = rsa.generate_private_key(public_exponent=65537,key_size=2048)
        payload["key"] = key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode()
    elif change == "profile": payload["config"] = payload["config"].replace("..operator","..other")
    elif change == "assets": payload["image_assets"] = "[]"
    elif change == "extra": payload["tls_key"] = "unexpected key"
    elif change == "external-tls-fields": payload.update(tls_certificate="external certificate",tls_key="external key")
    elif change == "unknown-field": payload["unrecognized_field"] = "not accepted"
    elif change == "missing-host": payload["runtime_env"] = "GODS_EYE_VIEW_MODE=oci\n"
    elif change == "duplicate-host": payload["runtime_env"] += "PUBLIC_HOST=127.0.0.2\n"
    else: payload["runtime_env"] = "PUBLIC_HOST=external.example\n"
    with pytest.raises(ValueError):
        envelope.consume(envelope.encrypt(public,payload,expected),tmp_path,expected)
    assert (tmp_path / "runtime.env").read_text() == "existing environment"
    assert not (tmp_path / "oci").exists() and not (tmp_path / "tls").exists()
    assert (tmp_path / "bootstrap/private.pem").exists()


def test_automatic_tls_consume_resume_keeps_key_and_rejects_host_or_signer_rotation(tmp_path):
    public,payload,expected = _auto_tls_envelope(tmp_path)
    envelope.consume(envelope.encrypt(public,payload,expected),tmp_path,expected)
    cert = (tmp_path / "tls/fullchain.pem").read_bytes()
    private = (tmp_path / "tls/privkey.pem").read_bytes()
    public = envelope.generate_key(tmp_path / "bootstrap/private.pem")
    updated = {**payload,"runtime_env":payload["runtime_env"]+"UPDATED_SETTING=yes\n"}
    envelope.consume(envelope.encrypt(public,updated,expected),tmp_path,expected,finalize=False)
    assert (tmp_path / "tls/fullchain.pem").read_bytes() == cert and (tmp_path / "tls/privkey.pem").read_bytes() == private
    with pytest.raises(ValueError,match="recovery"):
        envelope.consume(envelope.encrypt(public,{**updated,"runtime_env":"PUBLIC_HOST=127.0.0.2\n"},expected),tmp_path,expected)
    assert (tmp_path / "runtime.env").read_text() == updated["runtime_env"]
    different = {**expected,"operator_user_ocid":"ocid1.user.oc1..different"}
    with pytest.raises(ValueError,match="Operator rotation"):
        envelope.consume(envelope.encrypt(public,updated,different),tmp_path,different)
    assert (tmp_path / "tls/privkey.pem").read_bytes() == private


def test_pinned_local_ssl_trust_accepts_the_generated_non_ca_leaf(tmp_path):
    import hashlib
    import socket
    import ssl
    import threading
    result = envelope.ensure_viewer_tls(tmp_path,"127.0.0.1")
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(tmp_path / "tls/fullchain.pem",tmp_path / "tls/privkey.pem")
    listener = socket.socket()
    listener.bind(("127.0.0.1",0))
    listener.listen(1)
    listener.settimeout(5)
    address = listener.getsockname()
    errors = []
    def serve():
        try:
            connection,_ = listener.accept()
            connection.settimeout(5)
            with server_context.wrap_socket(connection,server_side=True) as channel:
                assert channel.recv(1) == b"x"
                channel.sendall(b"y")
        except Exception as error:
            errors.append(error)
    thread = threading.Thread(target=serve,daemon=True)
    thread.start()
    try:
        context = ssl.create_default_context(cadata=result["certificate_pem"])
        with socket.create_connection(address,timeout=5) as raw:
            with context.wrap_socket(raw,server_hostname="127.0.0.1") as channel:
                assert hashlib.sha256(channel.getpeercert(binary_form=True)).hexdigest() == result["fingerprint_sha256"]
                channel.sendall(b"x")
                assert channel.recv(1) == b"y"
    finally:
        listener.close()
        thread.join(timeout=6)
    assert not thread.is_alive() and errors == []


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


@pytest.mark.parametrize("field", ["artifacts_bucket_name", "medallion_bucket_names", "bucket_modes"])
def test_bucket_binding_mismatch_stops_before_native_client_or_journal(monkeypatch, field):
    import image_assets
    from preflight import bucket_inputs
    inputs = selections(("new",) * 5)
    selected = bucket_inputs(inputs)
    outputs = {"artifacts_bucket_name": selected["artifacts_bucket_name"],
        "medallion_bucket_names": json.loads(selected["medallion_bucket_names"]),
        "bucket_modes": json.loads(selected["bucket_modes"])}
    context = {"inputs": inputs, "terraform_outputs": outputs}
    verify_bucket_outputs(context)
    outputs[field] = "different" if field == "artifacts_bucket_name" else {"landing": "different"}
    monkeypatch.setattr(image_assets, "inspect_handoff", lambda *_args, **_kw: [])
    def forbidden_client(*_args, **_kw):
        pytest.fail("Mismatched bucket bindings must fail before native client or journal creation")
    with pytest.raises(ValueError, match="pinned Terraform outputs"):
        install(context, {}, None, object(), api_factory=forbidden_client)


def test_bucket_client_is_bound_to_selected_region_and_cannot_follow_redirects(monkeypatch):
    import oci
    from oci._vendor import requests
    from preflight import regional_storage
    session, calls = requests.Session(), []
    def client(config, **kwargs):
        calls.append((config, kwargs))
        return SimpleNamespace(base_client=SimpleNamespace(session=session))
    monkeypatch.setattr(oci.object_storage, "ObjectStorageClient", client)
    original = {"region": "us-phoenix-1", "tenancy": "selected-tenancy"}
    signer = object()
    regional_storage(original, signer, "us-ashburn-1")
    assert original["region"] == "us-phoenix-1"
    assert calls == [({**original, "region": "us-ashburn-1"}, {"signer": signer})]
    response = requests.Response()
    response.status_code, response.url, response._content = 301, "https://objectstorage.us-ashburn-1.oraclecloud.com/n/ns/b/selected", b""
    response.headers["Location"] = "https://objectstorage.us-phoenix-1.oraclecloud.com/n/ns/b/selected"
    prepared = session.prepare_request(requests.Request("GET", response.url))
    with pytest.raises(requests.exceptions.TooManyRedirects):
        list(session.resolve_redirects(response, prepared))
    session.close()


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
