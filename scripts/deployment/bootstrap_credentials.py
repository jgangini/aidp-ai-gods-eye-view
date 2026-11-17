"""One-use operator delivery bound to this deployment and VM RSA key."""
from __future__ import annotations
import argparse
import base64
import configparser
import hashlib
import ipaddress
import json
import os
import re
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def binding(deployment_id, operator_user_ocid, fingerprint):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", deployment_id):
        raise ValueError("Invalid deployment identity")
    if not operator_user_ocid.startswith("ocid1.user.") or not re.fullmatch(r"[0-9a-f]{32}", fingerprint.replace(":", "").lower()):
        raise ValueError("Invalid operator identity")
    return {"deployment_id": deployment_id, "operator_user_ocid": operator_user_ocid,
        "fingerprint": fingerprint.replace(":", "").lower()}


def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    temporary = path.with_suffix(path.suffix + ".pending")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as target:
            target.write(content)
            target.flush()
            os.fsync(target.fileno())
        temporary.replace(path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def generate_key(path):
    if path.exists() or path.with_name("public.pem").exists():
        raise ValueError("Bootstrap key already exists; preserve operation identity")
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    atomic(path, key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    atomic(path.with_name("public.pem"), public)
    return public


def encrypt(public, payload, expected):
    key = serialization.load_pem_public_key(public)
    if not isinstance(key, rsa.RSAPublicKey) or key.key_size < 3072:
        raise ValueError("Invalid bootstrap public key")
    aad = json.dumps(expected, sort_keys=True).encode()
    secret, nonce = AESGCM.generate_key(bit_length=256), os.urandom(12)
    wrapped = key.encrypt(secret, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=aad))
    ciphertext = AESGCM(secret).encrypt(nonce, json.dumps(payload, sort_keys=True).encode(), aad)
    return json.dumps({"schema_version": 1, "binding": expected,
        "wrapped_key": base64.b64encode(wrapped).decode(), "nonce": base64.b64encode(nonce).decode(),
        "ciphertext": base64.b64encode(ciphertext).decode()}).encode()


def _viewer_ip(host):
    try:
        if not isinstance(host, str) or host != host.strip() or "%" in host:
            raise ValueError()
        address = ipaddress.ip_address(host)
        if address.is_unspecified or address.is_multicast:
            raise ValueError()
        return address
    except ValueError:
        raise ValueError("PUBLIC_HOST must identify the assigned viewer IP address") from None


def _runtime_public_host(runtime_env):
    hosts = [line.split("=", 1)[1].strip() for line in runtime_env.splitlines()
        if "=" in line and line.split("=", 1)[0].strip() == "PUBLIC_HOST"]
    if len(hosts) != 1:
        raise ValueError("Runtime configuration requires exactly one PUBLIC_HOST")
    _viewer_ip(hosts[0])
    return hosts[0]


def _validate_viewer_tls(certificate_pem, private_pem, address):
    try:
        certificate = x509.load_pem_x509_certificate(certificate_pem)
        if certificate_pem.strip() != certificate.public_bytes(serialization.Encoding.PEM).strip():
            raise ValueError()
        key = serialization.load_pem_private_key(private_pem, password=None)
        if (not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 3072
                or certificate.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
                != key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)):
            raise ValueError()
        san = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        eku = certificate.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        constraints = certificate.extensions.get_extension_for_class(x509.BasicConstraints).value
        now = datetime.now(timezone.utc)
        if (len(san) != 1 or san.get_values_for_type(x509.IPAddress) != [address]
                or list(eku) != [ExtendedKeyUsageOID.SERVER_AUTH] or constraints.ca or constraints.path_length is not None
                or certificate.subject != certificate.issuer
                or not certificate.not_valid_before_utc <= now < certificate.not_valid_after_utc
                or not isinstance(certificate.signature_hash_algorithm, (hashes.SHA256, hashes.SHA384, hashes.SHA512))):
            raise ValueError()
        certificate.verify_directly_issued_by(certificate)
        return certificate
    except (ValueError, TypeError, InvalidSignature, UnsupportedAlgorithm, x509.ExtensionNotFound):
        raise ValueError("Existing viewer TLS identity is invalid, mismatched or expired; explicit recovery is required") from None


def ensure_viewer_tls(root, host):
    """Create a VM-local IP certificate once; return only its public PEM and DER pin."""
    root, address = Path(root), _viewer_ip(host)
    certificate_path, private_path = root / "tls/fullchain.pem", root / "tls/privkey.pem"
    if (root / "tls").is_symlink():
        raise ValueError("Indirect viewer TLS directory requires explicit recovery")
    present = [path.exists() or path.is_symlink() for path in (certificate_path, private_path)]
    if any(present):
        if not all(present) or any(path.is_symlink() or not path.is_file() for path in (certificate_path, private_path)):
            raise ValueError("Partial or indirect viewer TLS identity requires explicit recovery")
        if os.name != "nt" and any(stat.S_IMODE(path.stat().st_mode) != 0o600 for path in (certificate_path, private_path)):
            raise ValueError("Viewer TLS file permissions require explicit recovery")
        certificate_pem = certificate_path.read_bytes()
        certificate = _validate_viewer_tls(certificate_pem, private_path.read_bytes(), address)
    else:
        key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        now = datetime.now(timezone.utc)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, str(address))])
        certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(address)]), critical=False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=True,
                data_encipherment=False, key_agreement=False, key_cert_sign=False, crl_sign=False,
                encipher_only=None, decipher_only=None), critical=True).sign(key, hashes.SHA256()))
        certificate_pem = certificate.public_bytes(serialization.Encoding.PEM)
        private_pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        atomic(private_path, private_pem)
        atomic(certificate_path, certificate_pem)
        _validate_viewer_tls(certificate_path.read_bytes(), private_path.read_bytes(), address)
    return {"certificate_pem": certificate_pem.decode("ascii"),
        "fingerprint_sha256": certificate.fingerprint(hashes.SHA256()).hex()}


def consume(envelope, root, expected, *, finalize=True):
    document = json.loads(envelope)
    if set(document) != {"schema_version", "binding", "wrapped_key", "nonce", "ciphertext"} or type(document["schema_version"]) is not int or document["schema_version"] != 1 or document["binding"] != expected:
        raise ValueError("Bootstrap envelope identity mismatch")
    receipt = root / "bootstrap/receipt.json"
    if receipt.exists() and json.loads(receipt.read_text(encoding="utf-8")) != expected:
        raise ValueError("Operator rotation requires a separate authorized recovery operation")
    private = root / "bootstrap/private.pem"
    key = serialization.load_pem_private_key(private.read_bytes(), password=None)
    aad = json.dumps(expected, sort_keys=True).encode()
    secret = key.decrypt(base64.b64decode(document["wrapped_key"], validate=True), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=aad))
    payload = json.loads(AESGCM(secret).decrypt(base64.b64decode(document["nonce"], validate=True), base64.b64decode(document["ciphertext"], validate=True), aad))
    allowed = {"config", "key", "runtime_env", "image_assets"}
    if not isinstance(payload, dict) or set(payload) != allowed or any(not isinstance(value, str) or not value for value in payload.values()):
        raise ValueError("Invalid bootstrap payload")
    from image_assets_vm import validate_assets
    assets = validate_assets(json.loads(payload["image_assets"]))
    config = configparser.ConfigParser(interpolation=None, strict=True)
    config.read_string(payload["config"])
    operator = serialization.load_pem_private_key(payload["key"].encode(), password=None)
    if not isinstance(operator, rsa.RSAPrivateKey) or operator.key_size < 2048:
        raise ValueError("Operator signing key must be RSA with at least 2048 bits")
    fingerprint = hashlib.md5(operator.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo), usedforsecurity=False).hexdigest()
    if config["DEFAULT"].get("user") != expected["operator_user_ocid"] or fingerprint != expected["fingerprint"] or config["DEFAULT"].get("fingerprint", "").replace(":", "").lower() != fingerprint:
        raise ValueError("Operator key or profile differs from authorized signer")
    config["DEFAULT"]["key_file"] = "/etc/gods-eye-view/oci/key.pem"
    from io import StringIO
    rendered = StringIO()
    config.write(rendered)
    host = _runtime_public_host(payload["runtime_env"])
    if receipt.exists():
        for path, desired in (("oci/key.pem", payload["key"]), ("oci/config", rendered.getvalue())):
            if (root / path).read_text(encoding="utf-8") != desired:
                raise ValueError("Credential or TLS rotation requires a separate authorized recovery operation")
    ensure_viewer_tls(root, host)
    for path, content in (("oci/key.pem", payload["key"]), ("oci/config", rendered.getvalue()),
        ("runtime.env", payload["runtime_env"])):
        atomic(root / path, content.encode())
    atomic(root / "bootstrap/image-assets.json", json.dumps(assets, sort_keys=True).encode())
    # Read back before consuming the recipient key; a failed installation remains retryable.
    if (root / "oci/key.pem").read_text() != payload["key"]:
        raise ValueError("Installed operator key verification failed")
    if finalize:
        complete(root, expected)


def complete(root, expected):
    atomic(root / "bootstrap/receipt.json", json.dumps(expected, sort_keys=True).encode())
    (root / "bootstrap/private.pem").unlink()
    (root / "bootstrap/public.pem").unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate-key", type=Path)
    parser.add_argument("--consume", type=Path)
    parser.add_argument("--root", type=Path, default=Path("/etc/gods-eye-view"))
    parser.add_argument("--deployment-id")
    parser.add_argument("--operator-user-ocid")
    parser.add_argument("--fingerprint")
    args = parser.parse_args()
    if bool(args.generate_key) == bool(args.consume):
        parser.error("Select exactly one operation")
    if args.generate_key:
        generate_key(args.generate_key)
    else:
        expected = binding(args.deployment_id, args.operator_user_ocid, args.fingerprint)
        consume(args.consume.read_bytes(), args.root, expected)
        args.consume.unlink()


if __name__ == "__main__":
    main()
