"""Image verification helpers; release activation belongs to the product Compose bootstrap."""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
REPOSITORY = "https://github.com/jgangini/aidp-ai-gods-eye-view.git"
SEMVER_TAG = re.compile(r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
def semantic_version(tag: str) -> tuple[int, int, int] | None:
    match = SEMVER_TAG.fullmatch(tag)
    return tuple(map(int, match.groups())) if match else None


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    os.replace(temporary, path)


def _run(arguments: list[str], *, capture: bool = False) -> str:
    result = subprocess.run(
        arguments,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else ""


def _download(
    url: str,
    destination: Path,
    expected_sha256: str,
    maximum_bytes: int,
) -> None:
    if SHA256.fullmatch(expected_sha256) is None:
        raise RuntimeError("invalid_asset_digest")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": "oci-aidp-starter-kits-updater",
        },
    )
    digest = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(request, timeout=30) as response, destination.open(
        "xb"
    ) as output:
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > maximum_bytes:
                raise RuntimeError("release_asset_too_large")
            digest.update(chunk)
            output.write(chunk)
    destination.chmod(0o600)
    if digest.hexdigest() != expected_sha256:
        raise RuntimeError("release_asset_digest_mismatch")


def _container_exists(name: str) -> bool:
    return subprocess.run(
        ["docker", "container", "inspect", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def _remove_container(name: str) -> None:
    if _container_exists(name):
        subprocess.run(
            ["docker", "rm", "-f", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def _healthy(url: str, attempts: int = 60) -> bool:
    for _ in range(attempts):
        result = subprocess.run(
            [
                "curl",
                "--silent",
                "--insecure",
                "--output",
                "/dev/null",
                "--write-out",
                "%{http_code}",
                url,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0 and result.stdout.strip() == "200":
            return True
        time.sleep(5)
    return False


@contextmanager
def _singleton_lock(path: Path) -> Iterator[None]:
    import fcntl

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("update_already_running") from None
        yield

