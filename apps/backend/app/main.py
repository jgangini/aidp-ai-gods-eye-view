"""Composition root for the viewer API; installation belongs to Deploy Studio."""
from contextlib import asynccontextmanager, suppress
import asyncio
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import Settings, SettingsStore
from app.security import RateLimiter, load_or_create_session_key
from app.api.viewer_auth import mount_viewer_login
from app.api.viewer_identity import mount_identity
from app.modules.ai_gods_eye_view.runtime.access import Authorization, mount_access
from app.modules.ai_gods_eye_view.runtime.api import mount_gods_eye_view, run_local_gods_eye_view
from app.services.oci.identity import IdentityClient
from app.services.oci.aidp import AidpClient

COOKIE_NAME = "__Host-gods_eye_view"
LOCAL_COOKIE_NAME = "gods_eye_view"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        producer = asyncio.create_task(run_local_gods_eye_view(app)) if settings.gods_eye_view_enabled else None
        try:
            yield
        finally:
            if producer:
                producer.cancel()
                with suppress(asyncio.CancelledError):
                    await producer
            for name in ("identity_client", "aidp_client"):
                client = getattr(app.state, name, None)
                if client:
                    await client.close()

    app = FastAPI(title="God's Eye View", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.settings_store = SettingsStore(settings)
    app.state.session_key = load_or_create_session_key(settings.session_secret_file)
    app.state.login_limiter = RateLimiter(5, 60)
    app.state.identity_client = None
    app.state.aidp_client = None

    def identity_factory():
        if app.state.identity_client is None:
            app.state.identity_client = IdentityClient(settings)
        return app.state.identity_client

    def aidp_factory():
        if app.state.aidp_client is None:
            app.state.aidp_client = AidpClient(settings)
        return app.state.aidp_client

    app.state.identity_factory = identity_factory
    app.state.aidp_factory = aidp_factory
    app.state.gods_eye_view_aidp_factory = aidp_factory
    cookie_name = COOKIE_NAME if settings.cookie_secure else LOCAL_COOKIE_NAME
    authorization = Authorization(app, cookie_name)
    app.state.authorization = authorization
    require_admin = authorization.require_admin
    require_viewer = mount_access(app, require_admin, cookie_name)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request, error):
        # Validation failures must not echo credential-bearing request bodies.
        return JSONResponse({"detail": [
            {"loc": list(item["loc"]), "type": item["type"], "msg": item["msg"]}
            for item in error.errors()
        ]}, status_code=422)

    @app.middleware("http")
    async def same_origin(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "Same-origin request required"}, status_code=403)
            origin = request.headers.get("origin")
            if origin:
                try:
                    value = urlsplit(origin)
                    if value.scheme != request.url.scheme or value.netloc != request.url.netloc or value.path or value.query or value.fragment:
                        return JSONResponse({"detail": "Same-origin request required"}, status_code=403)
                except ValueError:
                    return JSONResponse({"detail": "Invalid origin"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    mount_viewer_login(app, cookie_name, lambda request: request.client.host if request.client else "unknown")
    mount_identity(app, require_admin, require_viewer)
    mount_gods_eye_view(app, require_admin, require_viewer)

    @app.get("/health")
    async def health():
        return {"status": "ok", "product": "gods_eye_view"}

    @app.get("/")
    async def entry():
        return RedirectResponse("/gods-eye-view/")

    @app.get("/auth/denied")
    async def denied():
        return JSONResponse({"detail": "OCI sign-in failed or viewer membership is not enabled"}, status_code=403)

    return app
