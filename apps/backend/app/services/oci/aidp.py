"""Signed AIDP transport and resource comparison for God’s Eye View."""
from __future__ import annotations
import asyncio
import hashlib
import json
import re
import threading
import uuid
from typing import Any
from urllib.parse import quote
from oci._vendor import requests
from app.config import Settings
from .contracts import AidpProvisionPending, AidpProvisionError, AidpRequestError, AidpProvisionConflict
API_VERSION = "20260430"

class AidpClient:
    def __init__(self, settings: Settings, *, config=None, signer=None, object_storage=None, session=None) -> None:
        self.settings = settings
        self.base = (
            f"https://datalake.{settings.aidp_region}.oci.oraclecloud.com/{API_VERSION}/"
            f"aiDataPlatforms/{settings.aidp_platform_id}"
        )
        import oci

        self._oci = oci
        config = config if config is not None else oci.config.from_file(settings.oci_config_file, "DEFAULT")
        self._oci_config = config
        self.signer = signer or oci.signer.Signer(
            tenancy=config["tenancy"],
            user=config["user"],
            fingerprint=config["fingerprint"],
            private_key_file_location=config["key_file"],
            pass_phrase=config.get("pass_phrase"),
        )
        self.object_storage = object_storage or oci.object_storage.ObjectStorageClient(config, signer=self.signer)
        self.session = session or requests.Session()
        self._session_lock = threading.Lock()

    async def close(self) -> None:
        self.session.close()

    @staticmethod
    def _request_headers(
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        data: bytes | None,
        headers: dict[str, str] | None,
        retry_scope: str,
    ) -> dict[str, str]:
        request_headers = {"Accept": "application/json", **(headers or {})}
        if payload is not None:
            request_headers["Content-Type"] = "application/json"
        if method.upper() != "POST":
            return request_headers
        content = (
            data
            if data is not None
            else json.dumps(payload or {}, sort_keys=True).encode("utf-8")
        )
        identity_headers = {
            key.casefold(): str(value)
            for key, value in request_headers.items()
            if key.casefold() != "opc-retry-token"
        }
        retry_identity = json.dumps(
            {
                "method": method.upper(),
                "path": path,
                "scope": retry_scope,
                "headers": identity_headers,
                "content_sha256": hashlib.sha256(content).hexdigest(),
            },
            sort_keys=True,
        )
        request_headers["opc-retry-token"] = str(
            uuid.uuid5(uuid.NAMESPACE_URL, retry_identity)
        )
        return request_headers

    @staticmethod
    def _response_body(response: Any) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.content

    @staticmethod
    def _safe_diagnostic_fragment(value: Any, *, limit: int = 240) -> str:
        if not isinstance(value, str):
            return ""
        fragment = " ".join(value.split())
        fragment = re.sub(r"https?://\S+", "[url]", fragment, flags=re.IGNORECASE)
        fragment = re.sub(r"\bocid1\.[A-Za-z0-9._-]+", "[ocid]", fragment)
        fragment = re.sub(
            r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
            "[email]",
            fragment,
            flags=re.IGNORECASE,
        )
        fragment = re.sub(
            r"(?i)\b(authorization|credential|password|secret|token)\s*[:=]\s*\S+",
            r"\1=[redacted]",
            fragment,
        )
        return fragment[:limit]

    @classmethod
    def _request_error_message(
        cls,
        method: str,
        path: str,
        phase: str,
        request_headers: dict[str, str],
        response: Any,
    ) -> str:
        endpoint = re.sub(r"(/workspaces/)[^/]+", r"\1{workspace}", path)
        endpoint = cls._safe_diagnostic_fragment(endpoint, limit=180)
        target = cls._safe_diagnostic_fragment(request_headers.get("path"), limit=180)
        body = cls._response_body(response)
        code = cls._safe_diagnostic_fragment(
            body.get("code") if isinstance(body, dict) else None, limit=80
        )
        message = cls._safe_diagnostic_fragment(
            body.get("message") if isinstance(body, dict) else None
        )
        context = f"{method.upper()} {endpoint} during {phase}"
        if target:
            context += f" for {target}"
        oracle_detail = ""
        if code or message:
            oracle_detail = f" Oracle {code or 'error'}: {message or 'No message provided.'}"
        return (
            f"AIDP rejected {context} ({response.status_code}).{oracle_detail} "
            "Check the AIDP policy and request contract, then retry."
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        allow_not_found: bool = False,
        include_headers: bool = False,
        phase: str = "content",
        retry_scope: str = "",
        legacy: bool = False,
    ) -> Any:
        request_headers = self._request_headers(
            method, path, payload, data, headers, retry_scope
        )
        try:
            with self._session_lock:
                response = self.session.request(
                    method,
                    f"{self.base.replace('/20260430/aiDataPlatforms/', '/20240831/dataLakes/', 1) if legacy else self.base}{path}",
                    auth=self.signer,
                    json=payload,
                    data=data,
                    headers=request_headers,
                    params=params,
                    timeout=(10, 60),
                )
        except requests.exceptions.RequestException as exc:
            raise AidpProvisionPending(
                "AIDP is still accepting the requested material. Retry shortly.", phase
            ) from exc
        if response.status_code in {408, 409, 429, 500, 502, 503, 504}:
            raise AidpProvisionPending("AIDP is still reconciling the requested material. Retry shortly.", phase)
        if response.status_code == 404 and allow_not_found:
            return (None, response.headers) if include_headers else None
        if response.status_code >= 400:
            raise AidpRequestError(
                self._request_error_message(
                    method, path, phase, request_headers, response
                ), method=method, path=path, phase=phase,
                status_code=response.status_code,
                request_id=str(response.headers.get("opc-request-id") or ""),
            )
        result = self._response_body(response)
        return (result, response.headers) if include_headers else result

    @staticmethod
    def _page_items(body: Any) -> list[dict[str, Any]]:
        if isinstance(body, list):
            values = body
        elif isinstance(body, dict) and ("items" in body or "Items" in body):
            values = body.get("items") if "items" in body else body.get("Items")
        else:
            raise AidpProvisionError("AIDP returned an invalid paginated response.")
        if not isinstance(values, list) or not all(isinstance(item, dict) for item in values):
            raise AidpProvisionError("AIDP returned invalid list items.")
        return values

    def _list(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
        phase: str = "content",
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page: str | None = None
        seen_pages: set[str] = set()
        for _ in range(1000):
            query = {"limit": "100", **(params or {})}
            if page:
                query["page"] = page
            body, response_headers = self._request(
                "GET", path, params=query, include_headers=True, phase=phase
            )
            items.extend(self._page_items(body))
            page = response_headers.get("opc-next-page") or response_headers.get("Opc-Next-Page")
            if not page:
                return items
            if page in seen_pages:
                raise AidpProvisionError("AIDP returned a repeated pagination token.")
            seen_pages.add(page)
        raise AidpProvisionError("AIDP pagination exceeded the safety limit.")

    @classmethod
    def _notebook_matches(cls, actual: Any, expected: Any) -> bool:
        if isinstance(expected, dict):
            return isinstance(actual, dict) and all(
                key in actual and cls._notebook_matches(actual[key], value)
                for key, value in expected.items()
            )
        if isinstance(expected, list):
            if isinstance(actual, str) and all(
                isinstance(item, str) for item in expected
            ):
                return "".join(expected) == actual
            return (
                isinstance(actual, list)
                and len(actual) == len(expected)
                and all(
                    cls._notebook_matches(actual_item, expected_item)
                    for actual_item, expected_item in zip(actual, expected, strict=True)
                )
            )
        return actual == expected

    @staticmethod
    def _resource_name(resource: dict[str, Any]) -> str:
        return str(resource.get("displayName") or resource.get("name") or "")

    @staticmethod
    def _job_task_matches(
        actual: Any,
        expected: dict[str, Any],
        compute_key: str,
    ) -> bool:
        source_fields = {
            "NOTEBOOK_TASK": ("notebookPath", "parameters"),
            "PYTHON_TASK": ("filePath", "source", "commandLineArguments"),
        }.get(expected.get("type"))
        return bool(
            isinstance(actual, dict)
            and source_fields is not None
            and all(actual.get(field) == expected[field] for field in ("type", "taskKey", *source_fields))
            and isinstance(actual.get("dependsOn"), list)
            and [
                dependency.get("taskKey")
                if isinstance(dependency, dict)
                else None
                for dependency in actual["dependsOn"]
            ]
            == [dependency["taskKey"] for dependency in expected["dependsOn"]]
            and actual.get("runIf") == "ALL_SUCCESS"
            and (actual.get("cluster") or {}).get("clusterKey") == compute_key
        )

    @classmethod
    def _job_tasks_match(
        cls,
        actual_tasks: Any,
        expected_tasks: list[dict[str, Any]],
        compute_key: str,
    ) -> bool:
        if not isinstance(actual_tasks, list) or len(actual_tasks) != len(expected_tasks):
            return False
        return all(
            cls._job_task_matches(actual, expected, compute_key)
            for actual, expected in zip(actual_tasks, expected_tasks, strict=True)
        )

    def _role(self, name: str) -> dict[str, Any]:
        matches = [item for item in self._list("/roles", params={"displayName": name}, phase="permissions") if self._resource_name(item) == name]
        if len(matches) != 1 or not matches[0].get("key"):
            raise AidpProvisionPending(f"The AIDP role {name} is not ready yet.", "permissions")
        return matches[0]

    def _role_principal_ocids(self, name: str) -> tuple[set[str], set[str]]:
        role = self._role(name)
        pending = [str(role["key"])]
        visited: set[str] = set()
        users: set[str] = set()
        groups: set[str] = set()
        while pending:
            role_key = pending.pop()
            if role_key in visited:
                continue
            if len(visited) >= 100:
                raise AidpProvisionError("The AIDP administrator role hierarchy is too deep.")
            visited.add(role_key)
            details = self._request(
                "GET",
                f"/roles/{quote(role_key, safe='')}",
                phase="permissions",
            )
            assignees = details.get("assignees") if isinstance(details, dict) else None
            if not isinstance(assignees, list):
                raise AidpProvisionError("AIDP returned invalid administrator role assignees.")
            for item in assignees:
                if not isinstance(item, dict):
                    raise AidpProvisionError("AIDP returned an invalid administrator role assignee.")
                principal_type = str(item.get("type") or "").upper()
                target = str(item.get("target") or "")
                if principal_type == "USER" and target.startswith("ocid1.user."):
                    users.add(target)
                elif principal_type == "GROUP" and target.startswith("ocid1.group."):
                    groups.add(target)
                elif principal_type == "ROLE" and target:
                    pending.append(target)
                else:
                    raise AidpProvisionError("AIDP returned an unsupported administrator role assignee.")
        return users, groups

    def _role_user_ocids(self, name: str) -> set[str]:
        return self._role_principal_ocids(name)[0]

    async def platform_admin_user_ocids(self) -> set[str]:
        return await asyncio.to_thread(self._role_user_ocids, "AI_DATA_PLATFORM_ADMIN")

    async def platform_admin_principals(self) -> tuple[set[str], set[str]]:
        return await asyncio.to_thread(
            self._role_principal_ocids, "AI_DATA_PLATFORM_ADMIN"
        )

    async def is_platform_admin(self, user_ocid: str) -> bool:
        return user_ocid in await self.platform_admin_user_ocids()
