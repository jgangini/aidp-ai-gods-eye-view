"""Signed AIDP transport and workspace primitives extracted from frozen Starter Kits.
Source commit 3c82617fd298933995e954955841007253cc0985; catalog/kit/Governance orchestration excluded.
"""
from __future__ import annotations
import configparser
import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import quote
from oci._vendor import requests
API_VERSION = "20240831"
RESOURCE_WAIT_ATTEMPTS = 120
_post_apply_deadline = 0.0
class ReconcileError(RuntimeError):
    pass


class ApiRequestError(ReconcileError):
    def __init__(self, method: str, path: str, status_code: int, request_id: str) -> None:
        super().__init__(f"AIDP {method} {path} failed with {status_code}; opc-request-id={request_id}")
        self.status_code = status_code


def _sleep(seconds: float) -> None:
    # ponytail: the hook is a single process; one process-wide deadline keeps every retry below Deploy Studio's cap.
    if _post_apply_deadline and time.monotonic() + seconds >= _post_apply_deadline:
        raise ReconcileError("Post-apply reconciliation reached its safe execution deadline")
    time.sleep(seconds)


@dataclass(slots=True)
class ApiResponse:
    status_code: int
    body: Any
    headers: dict[str, str]


class AidpApi:
    def __init__(
        self,
        region: str,
        platform_id: str,
        signer: Any,
        deployment_id: str,
        *,
        api_version: str = API_VERSION,
        resource_segment: str = "dataLakes",
    ) -> None:
        self.base = (
            f"https://datalake.{region}.oci.oraclecloud.com/{api_version}/"
            f"{resource_segment}/{platform_id}"
        )
        self.signer = signer
        self.deployment_id = deployment_id
        self.session = requests.Session()

    def _send(
        self,
        method: str,
        path: str,
        request_headers: dict[str, str],
        payload: dict[str, Any] | None,
        data: bytes | None,
        params: dict[str, Any] | None,
    ) -> Any:
        for attempt in range(5):
            try:
                response = self.session.request(
                    method,
                    f"{self.base}{path}",
                    auth=self.signer,
                    headers=request_headers,
                    params=params,
                    json=payload if data is None else None,
                    data=data,
                    timeout=(10, 60),
                )
            except requests.exceptions.RequestException as exc:
                if attempt == 4:
                    raise ReconcileError(f"AIDP {method} {path} failed after network retries") from exc
                _sleep(min(2**attempt, 15))
                continue
            if response.status_code not in {429, 500, 502, 503, 504} or attempt == 4:
                return response
            retry_after = response.headers.get("retry-after")
            delay = min(30, int(retry_after)) if retry_after and retry_after.isdigit() else min(2**attempt, 15)
            _sleep(delay)
        raise ReconcileError(f"AIDP {method} {path} exhausted retries")

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiResponse:
        request_headers = {"Accept": "application/json", **(headers or {})}
        if payload is not None:
            request_headers["Content-Type"] = "application/json"
        if method.upper() == "POST":
            content = data if data is not None else json.dumps(
                payload or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
            payload_hash = hashlib.sha256(content).hexdigest()
            object_type = str(request_headers.get("type") or path.strip("/").split("/", 1)[0] or "root")
            request_headers.setdefault("opc-retry-token", str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{self.deployment_id}:{method.upper()}:{path}:{object_type}:{payload_hash}"
                    + (f":{request_headers['path']}" if request_headers.get("path") else ""),
                )
            ))
        response = self._send(method, path, request_headers, payload, data, params)
        body: Any = None
        if response.content:
            try:
                body = response.json()
            except ValueError:
                body = response.content
        if response.status_code >= 400:
            raise ApiRequestError(method, path, response.status_code, response.headers.get("opc-request-id", "unavailable"))
        return ApiResponse(response.status_code, body, {key.lower(): value for key, value in response.headers.items()})

    def list_all(self, path: str, *, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page: str | None = None
        while True:
            query = dict(params or {})
            if page:
                query["page"] = page
            response = self.request("GET", path, params=query)
            body = response.body
            if isinstance(body, list):
                items.extend(body)
            elif isinstance(body, dict):
                items.extend(body.get("items") or body.get("Items") or [])
            page = response.headers.get("opc-next-page")
            if not page:
                return items


def exact_one(items: list[dict[str, Any]], name: str, kind: str) -> dict[str, Any] | None:
    matches = [item for item in items if item.get("displayName") == name]
    if len(matches) > 1:
        raise ReconcileError(f"Ambiguous {kind}: multiple resources named {name}")
    return matches[0] if matches else None


def assert_fields(resource: dict[str, Any], expected: dict[str, Any], kind: str) -> None:
    if not isinstance(resource, dict):
        raise ReconcileError(f"AIDP returned no {kind} details")
    mismatches = [key for key, value in expected.items() if resource.get(key) != value]
    if mismatches:
        raise ReconcileError(f"Existing {kind} has incompatible fields: {', '.join(mismatches)}")


def is_active_or_raise(resource: dict[str, Any], kind: str) -> bool:
    state = str(resource.get("lifecycleState") or resource.get("state") or "").upper()
    if state == "ACTIVE" or (kind == "shared compute" and state == "STOPPED"):
        return True
    if state in {"FAILED", "DELETING", "DELETED", "DELETE_FAILED", "CANCELED", "CANCELLED"} or state.endswith(
        "FAILED"
    ):
        raise ReconcileError(f"{kind} {resource.get('displayName', 'unknown')} entered terminal state {state}")
    return False


def role_has_member(
    api: AidpApi,
    role_key: str,
    principal_type: str,
    principal_id: str,
) -> bool:
    body = api.request("GET", f"/roles/{role_key}").body
    assignees = (body.get("assignees") or []) if isinstance(body, dict) else []
    return any(
        isinstance(item, dict)
        and str(item.get("type", "")).upper() == principal_type.upper()
        and item.get("target") == principal_id
        for item in assignees
    )


def assert_operator_platform_admin(
    api: AidpApi,
    operator_user_ocid: str,
    *,
    attempts: int = RESOURCE_WAIT_ATTEMPTS,
    principal_label: str = "deployment operator",
) -> None:
    last_not_ready: ApiRequestError | None = None
    for attempt in range(attempts):
        try:
            role = exact_one(
                api.list_all("/roles", params={"displayName": "AI_DATA_PLATFORM_ADMIN"}),
                "AI_DATA_PLATFORM_ADMIN",
                "role",
            )
            last_not_ready = None
        except ApiRequestError as exc:
            if exc.status_code != 404:
                raise
            # ponytail: ACTIVE can precede Workbench RBAC visibility; this bounded wait
            # still remains under the hook's process-wide safety deadline.
            last_not_ready = exc
            role = None
        if role and role_has_member(api, str(role.get("key") or ""), "USER", operator_user_ocid):
            return
        if attempt + 1 < attempts:
            _sleep(5)
    if last_not_ready:
        raise ReconcileError(
            f"AIDP Workbench did not authorize the {principal_label} after the "
            f"readiness window; last request: {last_not_ready}"
        ) from last_not_ready
    raise ReconcileError(f"OCI {principal_label} is not an AI_DATA_PLATFORM_ADMIN member")


def load_oci_config(config_path: str, key_path: str) -> dict[str, Any]:
    import oci
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    parser = configparser.ConfigParser(interpolation=None, strict=True)
    try:
        loaded = parser.read(config_path, encoding="utf-8")
    except (OSError, configparser.Error) as exc:
        raise ReconcileError("OCI config could not be parsed") from exc
    if not loaded or not parser.defaults():
        raise ReconcileError("OCI config is missing the DEFAULT profile")
    config = dict(parser["DEFAULT"])
    if config.get("pass_phrase"):
        raise ReconcileError("OCI API private key must be an unencrypted RSA PEM")
    config["key_file"] = key_path
    required = ("tenancy", "user", "fingerprint")
    missing = [name for name in required if not config.get(name)]
    if missing:
        raise ReconcileError(f"OCI config is missing required fields: {', '.join(missing)}")
    try:
        private_key = serialization.load_pem_private_key(Path(key_path).read_bytes(), password=None)
    except (OSError, ValueError, TypeError) as exc:
        raise ReconcileError("OCI API private key must be an unencrypted RSA PEM") from exc
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise ReconcileError("OCI API private key must be an unencrypted RSA PEM")
    actual_fingerprint = hashlib.md5(
        private_key.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
        usedforsecurity=False,
    ).hexdigest()
    configured_fingerprint = str(config["fingerprint"]).replace(":", "").lower()
    if configured_fingerprint != actual_fingerprint:
        raise ReconcileError("OCI API private key does not match the configured fingerprint")
    try:
        oci.config.validate_config(config)
    except Exception as exc:
        raise ReconcileError("OCI config could not be validated with the supplied private key") from exc
    return config


def render_runtime_oci_config(config: dict[str, Any]) -> str:
    parser = configparser.ConfigParser(interpolation=None)
    parser["DEFAULT"] = {
        name: str(config[name])
        for name in ("tenancy", "user", "fingerprint", "region")
    }
    parser["DEFAULT"]["key_file"] = "/etc/gods-eye-view/oci/key.pem"
    rendered = StringIO()
    parser.write(rendered, space_around_delimiters=False)
    return rendered.getvalue()


def build_signer(config: dict[str, Any]) -> Any:
    import oci

    return oci.signer.Signer(
        tenancy=config["tenancy"],
        user=config["user"],
        fingerprint=config["fingerprint"],
        private_key_file_location=config["key_file"],
        pass_phrase=config.get("pass_phrase"),
    )


def workspace_object(api: AidpApi, workspace_key: str, path: str) -> ApiResponse | None:
    try:
        return api.request(
            "GET",
            f"/workspaces/{workspace_key}/objects/{quote(path, safe='')}",
            headers={"Accept": "*/*"},
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return None
        raise


def workspace_object_key(response: ApiResponse | None, path: str) -> str:
    if response is None:
        return ""
    body = response.body if isinstance(response.body, dict) else {}
    headers = {str(name).casefold(): value for name, value in response.headers.items()}
    key = headers.get("object-key") or body.get("key") or body.get("objectKey")
    if key:
        return str(key)
    object_path = (
        headers.get("folder")
        or headers.get("path")
        or body.get("path")
    )
    if object_path and str(object_path) != path:
        raise ReconcileError(f"AIDP workspace object {path} returned a mismatched path")
    if not object_path:
        raise ReconcileError(f"AIDP workspace object {path} has no object key")
    return str(object_path)


def ensure_workspace_folder(api: AidpApi, workspace_key: str, path: str) -> tuple[str, bool]:
    current = workspace_object(api, workspace_key, path)
    if current is not None:
        return workspace_object_key(current, path), False
    try:
        api.request(
            "POST",
            f"/workspaces/{workspace_key}/objects",
            data=b"",
            headers={
                "Accept": "*/*",
                "Content-Type": "application/octet-stream",
                "path": path,
                "type": "FOLDER",
                "is-overwrite": "false",
            },
        )
    except ApiRequestError as exc:
        if exc.status_code != 409:
            raise
    current = workspace_object(api, workspace_key, path)
    if current is None:
        raise ReconcileError(f"AIDP workspace folder {path} was not published")
    return workspace_object_key(current, path), True

