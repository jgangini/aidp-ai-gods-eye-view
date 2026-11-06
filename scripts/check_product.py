"""One explicit product validation route; retained portal evidence is reported separately."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def product_suites():
    scope = json.loads((ROOT / "apps/backend/tests/validation-scope.json").read_text(encoding="utf-8"))
    root = ROOT / scope["test_root"]
    suites = sorted({name for names in scope["categories"].values() for name in names})
    retained = set(scope["retained_source_suites_outside_current_product_contract"])
    actual = {p.name for p in root.glob("test_*.py")}
    if actual != set(suites) | retained or set(suites) & retained:
        raise ValueError("Every transferred test must have an explicit product or retained-source disposition")
    print(f"Product suites: {len(suites)}. Retained original-portal suites: {sorted(retained)}", flush=True)
    return [str(root / name) for name in suites]


def run(*args, cwd=ROOT):
    subprocess.run(args, cwd=cwd, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-only", action="store_true")
    args = parser.parse_args()
    temp_root = ROOT / ".local"
    temp_root.mkdir(exist_ok=True)
    # pytest owns a new nonexistent directory and never clears a previous run.
    import uuid
    base = temp_root / ("pytest-product-" + uuid.uuid4().hex)
    run(sys.executable, "-m", "pytest", *product_suites(), "tests", "terraform/tests", "-q", "-ra",
        "-p", "no:cacheprovider", "--basetemp", str(base))
    run(sys.executable, "scripts/modules/ai_gods_eye_view/render_gods_eye_view_runtime.py", "--check")
    if not args.backend_only:
        run("terraform", "-chdir=terraform", "fmt", "-check", "-recursive")
        run("terraform", "-chdir=terraform", "validate", "-no-color")
        run("terraform", "-chdir=terraform", "test", "-no-color")
