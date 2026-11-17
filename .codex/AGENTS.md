# Local Codex Policy for codex-aidp-ai-gods-eye-view

Supplement the global policy with repository-specific facts only.

## Project
- Purpose: independent God’s Eye View with integrated viewer controls; Deploy Studio owns installation.
- Repository root: `D:\dev\codex-aidp-ai-gods-eye-view`
- Languages, runtimes and deployment targets: Python 3.12 API/hooks, React controls, native pinned upstream Node 24.14.0, OCI/AIDP.

## Workflow and validation
- Preflight command: `./scripts/arch-preflight.ps1`.
- Build, types, lint and tests: `scripts/check_product.py`, frontend npm test/build, native viewer tests/build; `apps/backend/tests/validation-scope.json` explains retained source-only portal suites.
- Postflight command: `./scripts/arch-postflight.ps1` (Python venv and Terraform/provider required).
- Graphify: not configured; do not initialize during extraction.
- Sentrux: CLI baseline/gate; no custom rules. Preserve the initial empty-repository baseline.
- Requirements source: `docs/migration-assessment.md` and coordinator’s separation contract; current progress in `docs/tasks/current.md`.
- Release/deployment approval boundaries: candidate commit/push and CI authorized. Native OCI mutation, final release and Deploy Studio registration remain coordinator-owned gates.

## Sensitive areas
- Architectural boundaries and fragile paths: API/RBAC separate from CLI installation; viewer’s only public listener is TLS gateway. Native AIDP programs have explicit assembly sources and hashes.
- External systems and credential handling: never read or modify `.oci` during local checks. Operator delivery is RSA/AES-GCM bound to deployment/user/fingerprint; selected admin does not become the signer.
- Expensive or unsafe commands: no inference, paid actors, shared Docker resets, resource adoption or OCI mutation within candidate extraction.

## Evidence-backed local rules
- Windows pytest needs a fresh nonexistent `.local/pytest-*` basetemp and may require sandbox escalation because of ACLs. Use `-p no:cacheprovider`; never delete an existing run directory to force tests through.
