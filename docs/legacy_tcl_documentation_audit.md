# Legacy TCL Documentation Audit

Audit date: 2026-05-12

## Current Truth Source

- `docs/protocol_truth/legacy_2743138_mode_profiles.md` is the active fact entry point for legacy device `2743138`.
- `docs/capture_analysis/legacy_2743138_mode_capture_summary.json` and `docs/capture_analysis/legacy_2743138_mode_capture_report.md` are generated from:
  - `newly_captured/tcl_1778556941.jsonl`
  - `newly_captured/tcl_1778557400.jsonl`

## Classification

Current / keep:
- `README.md`: current user-facing installation and troubleshooting entry point. Updated to link to the protocol truth registry.
- `tools/README.md`: current operator tooling entry point. Updated to describe profile bundles, legacy Fan `baseMode=0`, and unsupported Auto/AI.
- `docs/protocol_truth/legacy_2743138_mode_profiles.md`: active protocol truth registry.
- `docs/capture_analysis/legacy_2743138_mode_capture_report.md`: generated capture report.
- `docs/legacy_tcl_mode_fix_baseline.md`: baseline notes for this fix.
- `docs/legacy_tcl_mode_fix_completion_summary.md`: completion summary.

Historical / keep with context:
- `CODEX_LEGACY_TCL_AC_PROTOCOL_PROFILE_PLAN.md`: implementation plan. It intentionally contains old assumptions as things not to trust and current requirements to supersede them.
- `docs/superpowers/plans/2026-05-12-ha-integration-testing.md`: earlier implementation plan. It is historical context and should not override the protocol truth registry.

Updated:
- `findings.md`: old `baseMode=7/8` finding was rewritten as superseded by newer capture evidence.
- `progress.md`: old grouped matrix note was rewritten as superseded by newer capture evidence.

Generated inventory:
- `docs/legacy_tcl_markdown_inventory.txt`
- `docs/legacy_tcl_doc_suspect_claims.txt`

## Remaining Allowed Mentions

Mentions of `baseMode=7` or `baseMode=8` are allowed only as unsupported, superseded, historical, or do-not-assume statements. Supported legacy profiles for `2743138` must not emit either value.
