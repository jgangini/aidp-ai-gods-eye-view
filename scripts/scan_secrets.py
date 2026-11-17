"""Check repository candidates without reading ignored OCI/runtime files or printing matches."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    "private_key_material": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----\s+[A-Za-z0-9+/=\r\n]{80,}-----END"),
    "github_token": re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})"),
    "aws_access_key": re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}"),
}


if __name__ == "__main__":
    names = subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT).decode().split("\0")
    findings = []
    for name in sorted(set(names) - {""}):
        path = ROOT / name
        if not path.is_file():
            continue
        if any(part in {".oci", ".local", ".venv", ".git", ".upstream", "node_modules"} for part in path.relative_to(ROOT).parts):
            raise SystemExit("Private/generated path unexpectedly selected by Git")
        for rule, pattern in RULES.items():
            if pattern.search(path.read_bytes()):
                findings.append((name, rule))
    if findings:
        for name, rule in findings:
            print(f"FAIL {rule}: {name}")
        raise SystemExit(1)
    print(f"Secret pattern scan passed: {len(set(names) - {''})} nonignored candidate files. No secret contents emitted.")
