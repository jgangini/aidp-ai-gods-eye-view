"""Load hash-verified image archives through the VM's narrowly scoped instance identity."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import tempfile


def validate_assets(assets):
    if not isinstance(assets, list) or len(assets) != 3 or {item.get("component") for item in assets if isinstance(item, dict)} != {"api", "viewer", "gateway"}:
        raise ValueError("Exactly three product image archives are required")
    for item in assets:
        if set(item) != {"component", "object_name", "archive_sha256", "image_id", "image_tag"}:
            raise ValueError("Invalid image artifact descriptor")
        if not re.fullmatch(r"releases/[a-f0-9]{40}/[a-z-]+-image-amd64[.]tar[.]gz", item["object_name"]):
            raise ValueError("Image object is outside the immutable release scope")
        if not re.fullmatch(r"[a-f0-9]{64}", item["archive_sha256"]) or not re.fullmatch(r"sha256:[a-f0-9]{64}", item["image_id"]):
            raise ValueError("Image hashes are invalid")
        prefix = {"api": "gods-eye-view-api", "viewer": "gods-eye-view", "gateway": "gods-eye-view-gateway"}[item["component"]]
        commit = item["object_name"].split("/")[1]
        if item["object_name"].split("/")[-1] != prefix + "-image-amd64.tar.gz" or item["image_tag"] != prefix + ":" + commit:
            raise ValueError("Image tag/object identity differs from its component")
    return assets


def load_images(client, namespace, bucket, assets, *, run=subprocess.run, inspect=subprocess.check_output):
    for item in validate_assets(assets):
        with tempfile.TemporaryDirectory(prefix="gods-eye-image-") as directory:
            archive = Path(directory) / "image.tar.gz"
            response = client.get_object(namespace, bucket, item["object_name"])
            digest, size = hashlib.sha256(), 0
            with archive.open("xb") as output:
                for chunk in response.data.raw.stream(1024 * 1024, decode_content=False):
                    size += len(chunk)
                    if size > 4 * 1024 ** 3:
                        raise ValueError("Image archive exceeds the size limit")
                    digest.update(chunk)
                    output.write(chunk)
            if digest.hexdigest() != item["archive_sha256"]:
                raise ValueError("Image archive SHA-256 differs from the selected release")
            run(["docker", "load", "--input", str(archive)], check=True, stdout=subprocess.DEVNULL)
            actual = inspect(["docker", "image", "inspect", item["image_tag"], "--format", "{{.Id}} {{.Os}}/{{.Architecture}}"], text=True).strip()
            if actual != item["image_id"] + " linux/amd64":
                raise ValueError("Loaded image identity/platform differs from the selected release")
