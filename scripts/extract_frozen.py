"""One-time, allowlisted extraction; never reads ignored files or runtime state."""
import hashlib
import json
import subprocess
from pathlib import Path

SOURCE = Path('D:/dev/codex-oci-ai-data-platform-workbench-starter-kits')
COMMIT = '3c82617fd298933995e954955841007253cc0985'
ROOT = Path(__file__).resolve().parents[1]
PREFIXES = (
    'apps/backend/app/modules/ai_gods_eye_view/',
    'apps/backend/tests/modules/ai_gods_eye_view/',
    'modules/ai-gods-eye-view/',
    'scripts/modules/ai_gods_eye_view/',
)
FILES = (
    'apps/backend/app/__init__.py', 'apps/backend/app/security.py',
    'apps/backend/app/config.py', 'apps/backend/app/api/__init__.py',
    'apps/backend/app/api/viewer_auth.py', 'apps/backend/app/api/viewer_identity.py',
    'apps/backend/app/packages/__init__.py', 'apps/backend/app/packages/catalog.py',
    'apps/backend/app/packages/catalog.json', 'apps/backend/app/packages/aidp.py',
    'apps/backend/app/services/__init__.py', 'apps/backend/app/services/oci/__init__.py',
    'apps/backend/app/services/oci/contracts.py', 'apps/backend/app/services/oci/identity.py',
    'apps/backend/app/services/oci/credential_bootstrap.py',
    'apps/backend/requirements.txt', 'apps/backend/requirements-dev.txt',
    'apps/backend/tests/__init__.py', 'apps/backend/tests/modules/__init__.py',
    'terraform/hooks/gods_eye_sources.py', 'terraform/hooks/gods_eye_agent_source.py',
    'terraform/hooks/gods_eye_view_bootstrap.py',
    'terraform/tests/test_gods_eye_sources.py', 'terraform/tests/test_gods_eye_agent_source.py',
    'terraform/tests/test_gods_eye_view_bootstrap.py',
    'scripts/release/gods_eye_view_release_update.py', 'scripts/release/load_release_image.py',
    'scripts/release/vm_release_updater.py',
)


def git(*args):
    return subprocess.check_output(['git', '-C', str(SOURCE), *args])


if __name__ == '__main__':
    paths = git('ls-tree', '-r', '--name-only', COMMIT).decode().splitlines()
    selected = sorted(p for p in paths if p in FILES or p.startswith(PREFIXES))
    records = []
    for name in selected:
        target = ROOT / name
        if target.exists():
            raise RuntimeError(f'Refusing to overwrite {name}')
        content = git('show', f'{COMMIT}:{name}')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        records.append({'path': name, 'source_sha256': hashlib.sha256(content).hexdigest()})
    (ROOT / 'docs/extraction-provenance.json').write_text(json.dumps({
        'source_repository': 'https://github.com/jgangini/oci-ai-data-platform-workbench-starter-kits',
        'source_commit': COMMIT, 'files': records,
    }, indent=2) + '\n', encoding='utf-8')
    print(f'Extracted {len(records)} tracked files; private/local files excluded')
