# Migration candidate

Source: frozen Starter Kits commit `3c82617fd298933995e954955841007253cc0985`.
Status: implementation authorized; extraction/integration in progress. No OCI mutation or final release publication.
Destination private repository: `jgangini/aidp-ai-gods-eye-view`, main.

Checks: Git main/origin configured preserving docs/.oci. Sentrux baseline saved before extraction (5 files, quality 7780); no custom rules/graph configured. Python 3.12 venv prepared with pinned dependencies; native Windows alias unavailable. Pytest needs require_escalated for Windows temporary ACLs and fresh .local/ basetemp; default attempts failed, rerun renderer 19 passed.

Extraction: 417 tracked source files with docs/extraction-provenance.json; additional explicit native transport symbols with provenance. API independent runtime/identity and source domain tests in progress under backend agent; native viewer/controls and gateway owned by viewer agent. Main owns Terraform/hooks/scripts/docs/CI/Git.

Verified so far: native viewer 119 tests + 7 bridge tests; native build and React build pass. Terraform validate and 2 mocked new/existing plan tests pass before latest IAM/bootstrap extension (must rerun). Hook/deployment tests: 153 passed, 1 failed due moved _sleep monkeypatch; test now targets native_api (must rerun). Backend agent reports focused domain 220 pass/1 preexisting skip and real RBAC suite 16 pass, additional API 184 pass; integrated postflight not yet run.

Current work: immutable VM bundle/user-data, one-use encrypted OCI-only operator delivery, Deploy Studio schema1 manifest and new/existing identity revalidation. Effective admin resolves USER/GROUP/transitive ROLE via backend implementation. New platform grants selected admin explicitly; no operator impersonation. VM images/gateway integration, artifact build/CI/push still pending. Do not mark candidate deployment ready yet.

Review limitation: original combined-stack installation.py/module.py and their tests preserved after automatic approval review rejected removal as potentially weakening tests; new main does not mount install routes. Must document/resolve archive vs product test mapping without evading rejection. Seven high upstream dependency advisories under applicability review; DOMPurify critical preconditions absent in identified Credit call, regression added. No local Docker/browser/cloud executed.

No commit or push yet. Next: complete integration, run one postflight including architecture/secret scan, commit and push private candidate main, inspect CI. Native cloud acceptance and final release remain coordinator-owned gates.
Acceptance and scope: `../migration-assessment.md`; installation through Deploy Studio, only interface is integrated viewer.
