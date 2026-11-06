"""One-use operator delivery bound to this deployment and VM RSA key."""
from __future__ import annotations
import argparse
import base64
import configparser
import hashlib
import json
import os
import re
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


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


def consume(envelope, root, expected, *, finalize=True):
    document = json.loads(envelope)
    if set(document) != {"schema_version", "binding", "wrapped_key", "nonce", "ciphertext"} or document["schema_version"] != 1 or document["binding"] != expected:
        raise ValueError("Bootstrap envelope identity mismatch")
    receipt = root / "bootstrap/receipt.json"
    if receipt.exists() and json.loads(receipt.read_text(encoding="utf-8")) != expected:
        raise ValueError("Operator rotation requires a separate authorized recovery operation")
    private = root / "bootstrap/private.pem"
    key = serialization.load_pem_private_key(private.read_bytes(), password=None)
    aad = json.dumps(expected, sort_keys=True).encode()
    secret = key.decrypt(base64.b64decode(document["wrapped_key"], validate=True), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=aad))
    payload = json.loads(AESGCM(secret).decrypt(base64.b64decode(document["nonce"], validate=True), base64.b64decode(document["ciphertext"], validate=True), aad))
    allowed = {"config", "key", "runtime_env", "tls_certificate", "tls_key", "image_assets"}
    if set(payload) != allowed or any(not isinstance(value, str) or not value for value in payload.values()):
        raise ValueError("Invalid bootstrap payload")
    from image_assets_vm import validate_assets
    assets = validate_assets(json.loads(payload["image_assets"]))
    config = configparser.ConfigParser(interpolation=None, strict=True)
    config.read_string(payload["config"])
    operator = serialization.load_pem_private_key(payload["key"].encode(), password=None)
    fingerprint = hashlib.md5(operator.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo), usedforsecurity=False).hexdigest()
    if config["DEFAULT"].get("user") != expected["operator_user_ocid"] or fingerprint != expected["fingerprint"] or config["DEFAULT"].get("fingerprint", "").replace(":", "").lower() != fingerprint:
        raise ValueError("Operator key or profile differs from authorized signer")
    config["DEFAULT"]["key_file"] = "/etc/gods-eye-view/oci/key.pem"
    from io import StringIO
    rendered = StringIO()
    config.write(rendered)
    if receipt.exists():
        for path, desired in (("oci/key.pem", payload["key"]), ("oci/config", rendered.getvalue()),
                ("tls/fullchain.pem", payload["tls_certificate"]), ("tls/privkey.pem", payload["tls_key"])):
            if (root / path).read_text(encoding="utf-8") != desired:
                raise ValueError("Credential or TLS rotation requires a separate authorized recovery operation")
    for path, content in (("oci/key.pem", payload["key"]), ("oci/config", rendered.getvalue()),
        ("runtime.env", payload["runtime_env"]), ("tls/fullchain.pem", payload["tls_certificate"]), ("tls/privkey.pem", payload["tls_key"])):
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
