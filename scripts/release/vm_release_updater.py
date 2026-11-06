"""Current product release identity shared by the image packager."""
from __future__ import annotations
import re

REPOSITORY = "https://github.com/jgangini/aidp-ai-gods-eye-view.git"
SEMVER_TAG = re.compile(r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
def semantic_version(tag: str) -> tuple[int, int, int] | None:
    match = SEMVER_TAG.fullmatch(tag)
    return tuple(map(int, match.groups())) if match else None

