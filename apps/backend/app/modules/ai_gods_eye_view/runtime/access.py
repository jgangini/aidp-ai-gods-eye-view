"""Reauthorize sessions against live domain membership and AIDP privileges."""
from fastapi import Depends, HTTPException, Request, Response
import httpx
from oci._vendor import requests

from app.security import verify_session
from app.services.oci.contracts import IdentityPending, AidpProvisionError, AidpProvisionPending


class Authorization:
    def __init__(self, app, cookie_name):
        self.app, self.cookie_name = app, cookie_name

    async def account(self, subject):
        if not subject or not subject.startswith("viewer:"):
            raise HTTPException(401, "God's Eye View access required")
        user_id = subject.removeprefix("viewer:")
        if not user_id or "/" in user_id or ":" in user_id:
            raise HTTPException(401, "Invalid viewer session")
        try:
            account = await self.app.state.identity_factory().gods_eye_view_user(user_id)
        except (IdentityPending, httpx.HTTPError, requests.exceptions.RequestException):
            raise HTTPException(503, "Viewer membership could not be verified") from None
        if not account:
            raise HTTPException(401, "Viewer membership is no longer active")
        return account

    async def is_admin(self, subject):
        account = await self.account(subject)
        settings = self.app.state.settings
        if not settings.identity_domain_id or not settings.admin_user_ocid or account["ocid"] != settings.admin_user_ocid:
            return False
        identity = self.app.state.identity_factory()
        try:
            return await identity.has_aidp_admin_role(account["id"], self.app.state.gods_eye_view_aidp_factory())
        except (IdentityPending, AidpProvisionError, AidpProvisionPending, httpx.HTTPError, requests.exceptions.RequestException):
            raise HTTPException(503, "Administrator privileges could not be verified") from None

    async def require_viewer(self, request: Request):
        subject = verify_session(request.cookies.get(self.cookie_name, ""), self.app.state.session_key)
        await self.account(subject)
        return subject

    async def require_admin(self, request: Request):
        subject = await self.require_viewer(request)
        if not await self.is_admin(subject):
            raise HTTPException(403, "Administrator access required")
        return subject


def mount_access(app, require_admin, cookie_name):
    authorization = app.state.authorization

    @app.get("/api/gods-eye-view/session")
    async def session(response: Response, subject=Depends(authorization.require_viewer)):
        role = "admin" if await authorization.is_admin(subject) else "reader"
        response.headers["X-Gods-Eye-View-User"] = subject
        response.headers["X-Gods-Eye-View-Role"] = role
        response.headers["Cache-Control"] = "no-store"
        return {"username": subject, "role": role}

    @app.get("/api/admin/session")
    async def administrator_session(response: Response, subject=Depends(require_admin)):
        response.headers["X-Gods-Eye-View-User"] = subject
        response.headers["X-Gods-Eye-View-Role"] = "admin"
        response.headers["Cache-Control"] = "no-store"
        return {"username": subject, "role": "admin"}

    return authorization.require_viewer
