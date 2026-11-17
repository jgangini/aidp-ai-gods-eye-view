# God’s Eye View

Read `.codex/AGENTS.md`. Requirements: `docs/migration-assessment.md`, reconciled with the coordinator's separation contract. This product owns the viewer and its integrated controls; installation is CLI/hooks through Deploy Studio. No Starter Kits portal.

Run `scripts/arch-preflight.ps1` before source changes and `scripts/arch-postflight.ps1` after. One owner maintains the Sentrux baseline; no graph is configured. Keep `.oci` and runtime state untouched and ignored. Native OCI operations and release publication are not authorized in the extraction phase. Never use a sibling repository at runtime/build time.

Upstream is commit/hash pinned. Preserve Gold publication, CAS controls, runtime identity, streaming checkpoints and image rollback. Readers cannot administer. Use native viewer build, not retained standalone page. Do not initialize Arko over this nonempty checkout; adapt feature maps explicitly.
