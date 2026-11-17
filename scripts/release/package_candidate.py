#!/usr/bin/env python3
"""Package an already-built local image without building, pulling or publishing it."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from vm_release_updater import REPOSITORY, SHA, SHA256, semantic_version


COMPONENTS = {"api": "gods-eye-view-api", "viewer": "gods-eye-view", "gateway": "gods-eye-view-gateway"}
CHUNK_SIZE = 1024 * 1024


def _inspect(image, run):
    result = run(["docker", "image", "inspect", image, "--format", "{{.Id}} {{.Os}}/{{.Architecture}}"],
                 check=True, capture_output=True, text=True)
    fields = result.stdout.split()
    if (len(fields) != 2 or not fields[0].startswith("sha256:")
            or not SHA256.fullmatch(fields[0][7:]) or fields[1] != "linux/amd64"):
        raise ValueError("The local image must have a SHA-256 identity and linux/amd64 platform")
    return fields[0]


def package_candidate(component, image, commit, release, output, *, run=subprocess.run, popen=subprocess.Popen):
    if component not in COMPONENTS:
        raise ValueError("Unsupported image component")
    if not isinstance(commit, str) or not SHA.fullmatch(commit):
        raise ValueError("A full lowercase commit SHA is required")
    if not isinstance(release, str) or (release != "candidate" and not semantic_version(release)):
        raise ValueError("Release must be candidate or a stable vMAJOR.MINOR.PATCH tag")
    if not isinstance(image, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/:@-]{0,511}", image):
        raise ValueError("A local image reference is required")
    name = COMPONENTS[component]
    output = Path(output)
    archive_name, manifest_name = name + "-image-amd64.tar.gz", name + "-release.json"
    archive_path, manifest_path = output / archive_name, output / manifest_name
    if archive_path.exists() or manifest_path.exists():
        raise FileExistsError("Candidate artifacts already exist; select a new output directory")
    image_id = _inspect(image, run)
    canonical = f"{name}:{commit}"
    run(["docker", "image", "tag", image_id, canonical], check=True)
    if _inspect(canonical, run) != image_id:
        raise ValueError("Canonical image tag does not match the selected image")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{name}-", dir=output) as directory:
        temporary = Path(directory)
        archive = temporary / archive_name
        command = ["docker", "save", canonical]
        with tempfile.TemporaryFile() as errors:
            process = popen(command, stdout=subprocess.PIPE, stderr=errors)
            try:
                with process.stdout as source, archive.open("xb") as target:
                    with gzip.GzipFile(filename="", mode="wb", compresslevel=6, fileobj=target, mtime=0) as compressed:
                        shutil.copyfileobj(source, compressed, length=CHUNK_SIZE)
                status = process.wait()
                if status:
                    raise subprocess.CalledProcessError(status, command)
            except BaseException:
                if process.poll() is None:
                    process.kill()
                process.wait()
                raise
        if _inspect(canonical, run) != image_id:
            raise ValueError("Image tag changed while its archive was being saved")
        with archive.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        manifest = {"schema_version": 1, "updater_protocol": 1,
            "repository": REPOSITORY.removesuffix(".git"), "release": release, "commit_sha": commit,
            "image": {"asset_name": archive_name, "sha256": digest, "platform": "linux/amd64",
                      "image_tag": canonical, "image_id": image_id}}
        pending = temporary / manifest_name
        pending.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        archive.rename(archive_path)
        pending.rename(manifest_path)
    return manifest_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", choices=COMPONENTS, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(package_candidate(args.component, args.image, args.commit, args.release, args.output))


if __name__ == "__main__":
    main()
