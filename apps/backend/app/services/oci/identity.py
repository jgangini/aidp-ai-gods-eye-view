"""Read-only OCI Identity Domains account and membership verification."""
from __future__ import annotations
import asyncio
import json
import threading
from typing import Any
from urllib.parse import quote
import httpx
from oci._vendor import requests
from app.config import Settings
from .contracts import IdentityPending

class IdentityClient:
    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
        self.settings = settings
        self.client = client or requests.Session()
        self._async_test_client = isinstance(client, httpx.AsyncClient)
        self._session_lock = threading.Lock()
        self.signer: Any | None = None
        if client is None:
            import oci

            config = oci.config.from_file(settings.oci_config_file, "DEFAULT")
            self.signer = oci.signer.Signer(
                tenancy=config["tenancy"],
                user=config["user"],
                fingerprint=config["fingerprint"],
                private_key_file_location=config["key_file"],
                pass_phrase=config.get("pass_phrase"),
            )

    async def close(self) -> None:
        if self._async_test_client:
            await self.client.aclose()
            return
        await asyncio.to_thread(self.client.close)

    def _request_sync(self, method: str, path: str, **kwargs: Any) -> Any:
        extra_headers = kwargs.pop("headers", {})
        request_kwargs = {
            **kwargs,
            "headers": {"Accept": "application/json", **extra_headers},
            "timeout": 30,
        }
        if self.signer is not None:
            request_kwargs["auth"] = self.signer
        with self._session_lock:
            return self.client.request(
                method,
                f"{self.settings.identity_domain_url}{path}",
                **request_kwargs,
            )

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        if self._async_test_client:
            extra_headers = kwargs.pop("headers", {})
            return await self.client.request(
                method,
                f"{self.settings.identity_domain_url}{path}",
                headers={"Accept": "application/json", **extra_headers},
                **kwargs,
            )
        return await asyncio.to_thread(self._request_sync, method, path, **kwargs)

    async def _is_member(self, group_id: str, user_id: str) -> bool:
        response = await self._request(
            "GET",
            "/admin/v1/Users",
            params={
                "filter": f"id eq {_scim_literal(user_id)} and groups.value eq {_scim_literal(group_id)}",
                "count": 1,
            },
        )
        response.raise_for_status()
        return bool(response.json().get("Resources", []))

    async def _users_matching(self, filter_expression: str) -> list[dict[str, Any]]:
        users: list[dict[str, Any]] = []
        start_index = 1
        while True:
            response = await self._request(
                "GET",
                "/admin/v1/Users",
                params={
                    "filter": filter_expression,
                    "startIndex": start_index,
                    "count": 100,
                    "attributes": "id,ocid,userName,displayName,name,emails,active,externalId",
                },
            )
            response.raise_for_status()
            body = response.json()
            page = body.get("Resources", [])
            users.extend(page)
            start_index += len(page)
            if not page or start_index > int(body.get("totalResults", len(users))):
                return users

    async def _discover_gods_eye_view_group(self) -> str | None:
        if not self.settings.managed_viewer_app_name:
            return None
        response = await self._request("GET", "/admin/v1/Groups", params={
            "filter": f"externalId eq {_scim_literal(self.settings.lab_marker + ':gods_eye_view')}",
            "count": 2, "attributes": "id,externalId"})
        response.raise_for_status()
        body = response.json()
        groups = body.get("Resources", [])
        if body.get("totalResults") == 0 and groups == []:
            return None
        if body.get("totalResults") != 1 or len(groups) != 1:
            raise IdentityPending("God's Eye View reader group is unavailable or ambiguous")
        group_id = groups[0].get("id", "")
        if (not isinstance(group_id, str) or not group_id or "/" in group_id
                or groups[0].get("externalId") != f"{self.settings.lab_marker}:gods_eye_view"):
            raise IdentityPending("God's Eye View reader group does not belong to this deployment")
        return group_id

    async def _gods_eye_view_group(self) -> str | None:
        group_id = self.settings.gods_eye_view_group_id.strip() or await self._discover_gods_eye_view_group()
        if not group_id:
            return None
        response = await self._request("GET", f"/admin/v1/Groups/{group_id}",
                                       params={"attributes": "id,externalId"})
        if response.status_code == 404:
            return None
        response.raise_for_status()
        group = response.json()
        if (group.get("id") != group_id
                or group.get("externalId") != f"{self.settings.lab_marker}:gods_eye_view"):
            raise IdentityPending("God's Eye View reader group does not belong to this deployment")
        return group_id

    async def get_gods_eye_view_account(self, user_id: str) -> dict[str, Any] | None:
        response = await self._request("GET", f"/admin/v1/Users/{quote(user_id, safe='')}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        user = response.json()
        resolved_id, user_ocid = _user_coordinates(user)
        if resolved_id != user_id:
            raise IdentityPending("Identity Domains returned a different user")
        account = _platform_role_user(user, user_ocid, self.settings.lab_marker)
        account["active"] = user.get("active") is True
        return account

    async def gods_eye_view_user(self, user_id: str) -> dict[str, Any] | None:
        account = await self.get_gods_eye_view_account(user_id)
        if not account or not account["active"] or account["status"] != "active":
            return None
        group_id = await self._gods_eye_view_group()
        if not group_id or not await self._is_member(group_id, user_id):
            return None
        return {**account, "gods_eye_view_access": True, "mode": "OCI"}

    async def has_aidp_admin_role(self, user_id, aidp_client):
        account = await self.get_gods_eye_view_account(user_id)
        if not account or not account["active"]:
            return False
        users, groups = await aidp_client.platform_admin_principals()
        if account["ocid"] in users:
            return True
        for group_ocid in groups:
            response = await self._request("GET", "/admin/v1/Groups", params={
                "filter": f"ocid eq {_scim_literal(group_ocid)}", "attributes": "id,ocid", "count": 2})
            response.raise_for_status()
            body = response.json()
            matches = body.get("Resources", [])
            if body.get("totalResults") != 1 or len(matches) != 1 or matches[0].get("ocid") != group_ocid:
                raise IdentityPending("Administrator group could not be verified")
            if await self._is_member(matches[0]["id"], user_id):
                return True
        return False


def _scim_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _user_coordinates(user: dict[str, Any]) -> tuple[str, str]:
    user_id = str(user.get("id") or "")
    user_ocid = str(user.get("ocid") or "")
    if not user_id:
        raise IdentityPending("Identity Domains has not published the user identifier yet")
    if not user_ocid.startswith("ocid1.user."):
        raise IdentityPending("Identity Domains has not published the OCI user OCID yet")
    return user_id, user_ocid


def _platform_role_user(
    user: dict[str, Any], user_ocid: str, lab_marker: str
) -> dict[str, Any]:
    return {
        "id": str(user["id"]),
        "ocid": user_ocid,
        "name": user.get("displayName") or user.get("name", {}).get("formatted") or "",
        "email": user.get("userName", ""),
        "status": "active",
        "active": bool(user.get("active", False)),
        "managed": user.get("externalId") == lab_marker,
    }

