"""Runtime bindings for the independently deployed viewer."""
from __future__ import annotations
import json
import os
import threading
from dataclasses import dataclass, fields
from pathlib import Path
from pydantic import ValidationError
from app.api.viewer_identity import DEFAULT_IDENTITY, ViewerIdentity

@dataclass(frozen=True, slots=True)
class Settings:
    identity_domain_id: str = ""
    identity_domain_url: str = ""
    admin_user_ocid: str = ""
    gods_eye_view_group_id: str = ""
    viewer_oidc_app_name: str = ""
    viewer_oidc_redirect_uri: str = ""
    aidp_platform_id: str = ""
    aidp_workspace_name: str = ""
    aidp_workspace_key: str = ""
    aidp_region: str = ""
    compartment_id: str = ""
    agent_model_id: str = ""
    oci_config_file: str = "/etc/gods-eye-view/oci/config"
    objectstorage_namespace: str = ""
    bucket_name: str = ""
    gods_eye_control_bucket: str = ""
    artifacts_bucket_name: str = "oci_artifacts"
    aidp_settings_file: str = "/var/lib/gods-eye-view/settings.json"
    lab_marker: str = "gods-eye-view"
    session_secret_file: str = "/var/lib/gods-eye-view/session.key"
    cookie_secure: bool = True
    gods_eye_view_mode: str = "oci"
    gods_eye_view_enabled: bool = False
    gods_eye_oci_text_model: str = "xai.grok-4.6"
    gods_eye_oci_voice_model: str = "google.gemini-2.5-flash-lite"
    gods_eye_oci_voice: str = "ara"

    def __post_init__(self):
        if self.gods_eye_view_mode not in {"local", "oci"}:
            raise ValueError("GODS_EYE_VIEW_MODE must be local or oci")

    @property
    def gods_eye_view_local_mode(self):
        return self.gods_eye_view_mode == "local"

    @property
    def local_development_mode(self):
        return self.gods_eye_view_local_mode

    @property
    def managed_viewer_app_name(self):
        return self.viewer_oidc_app_name

    @classmethod
    def from_env(cls):
        names = {"gods_eye_view_group_id": "IDENTITY_GODS_EYE_VIEW_GROUP_ID", "viewer_oidc_app_name": "IDENTITY_VIEWER_APP_NAME"}
        values = {}
        for field in fields(cls):
            value = os.getenv(names.get(field.name, field.name.upper()))
            if value is not None:
                values[field.name] = value.lower() in {"true", "1", "yes"} if type(field.default) is bool else value.strip()
        if "gods_eye_oci_voice" in values:
            values["gods_eye_oci_voice"] = values["gods_eye_oci_voice"].lower()
        return cls(**values)

class SettingsStore:
    """Only labels are editable; deployment bindings remain immutable."""
    def __init__(self, settings):
        self.path = Path(settings.aidp_settings_file)
        self.lock = threading.Lock()

    def get_viewer_identity(self):
        if not self.path.exists():
            return dict(DEFAULT_IDENTITY)
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
            identity = ViewerIdentity.model_validate(stored.get("viewer_identity", {"name": "", "description": ""})).model_dump()
        except (OSError, ValueError, AttributeError, ValidationError):
            return dict(DEFAULT_IDENTITY)
        return {key: value or DEFAULT_IDENTITY[key] for key, value in identity.items()}

    def update_viewer_identity(self, identity):
        identity = ViewerIdentity.model_validate(identity).model_dump()
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            pending = self.path.with_suffix(".pending")
            pending.write_text(json.dumps({"viewer_identity": identity}), encoding="utf-8")
            pending.replace(self.path)
        return self.get_viewer_identity()
