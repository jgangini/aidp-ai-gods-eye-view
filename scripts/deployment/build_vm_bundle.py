"""Build the nonsecret immutable VM bootstrap archive from an explicit file list."""
from pathlib import Path
import argparse
import hashlib
import io
import zipfile

ROOT = Path(__file__).resolve().parents[2]
FILES = ("docker/bootstrap.sh", "docker/compose.yml", "scripts/deployment/bootstrap_credentials.py")


def build(root=ROOT):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (root / name).read_bytes())
    return output.getvalue()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    content = build()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(content)
    print(hashlib.sha256(content).hexdigest())
