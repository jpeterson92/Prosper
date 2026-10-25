# ADR-0012: Adopt proportional controls for the advisory product

Date: October 25, 2026. Status: **Accepted** by the owner's request to prioritize all remediation from the [simplification proposal](../../tasks/ADVISORY_SIMPLIFICATION_PROPOSAL.md) and align future tasks with that perspective. Decision register: D046.

**Amended by [D047/ADR-0013](0013-adopt-unreleased-clean-break-development.md):** no backward compatibility with unreleased Prosper implementations is required. The original bridge/migration/old-reader preservation requirements are superseded; retained current-format source/transaction/recovery requirements remain.

## Decision

The first advisory release follows `import current snapshot -> inspect loss/risk -> compare suggestions -> save/export manual worksheet -> refresh holdings before the next session`. Prosper provides estimates and explanations; it does not maintain authoritative broker/tax books or execution state.

Use Float64 for derived analytics and a small decimal/string boundary for supplied quantities/basis and final discrete checks. Use calculation-specific tested tolerances rather than exact rational weights, universal significant-digit/quantum rules or universal epsilons. Preserve source files and material facts; do not propagate original numeric spellings through every calculation. Distinguish numerical error from investor economic limits.

Retain enough source/input/settings/output context to explain a saved analysis. Consolidate authoritative storage and current-format backup; use explicit current schema checks instead of exact source-code identity. Keep normal transactions, stale-result protection and useful checksums. Retire general intermediate proof/registry/retention machinery when its retained current user needs have replacements; D047 removes any old-data migration/export prerequisite.

Defer approval reservations, order/submission tracking, fill reconciliation, basis maintenance, account reconstruction, forward monitoring and background validation scheduling from the first release. Manual/targeted refresh, compatible historical reuse, dated restrictions and relevant household activity remain useful inputs. Removing execution management also removes any claim to know available broker shares/cash after external trades; require a refreshed snapshot before new post-trade suggestions.

Keep source/identity/unit/date validation, explicit unknowns, duplicate detection, independent final suggestion checks, privacy, local security, safe paths, transactional writes and recovery of user work. Missing inputs block affected results, not unrelated diagnostics. Numerical tolerance cannot authorize overselling or a substantive economic-limit breach.

The accepted equity scope, benchmark value normalization, selected-cash/final-cash distinctions, whole-share suggestions, zero-positive-gain policy, deterministic financial logic and D041/D042 risk methodology remain. Independent tax/model review and real-use/release authority remain claim-specific prerequisites; unrelated synthetic development can proceed. No real-data/account/trading/publication authority is granted here.

Future infrastructure must address a named user outcome or material failure. Prefer standard libraries, first-class Polars tables, simple bounded code and realistic tests. Keep concise current documentation; retire routine authored-tree hashing and mandatory title/model-sizing ceremony through the remediation plan. Normal affected/full-check cadence remains.

## Precedence and transition

D046 amends D008/D020 numerical encoding, D025 evidence/time/lifecycle, D040 first-release scheduling and retained-data obligations, D045 exact representation (not its retained-equity denominator or exclusions), and cross-cutting architecture/validation/workflow requirements. Historical decisions and verification remain accurate for their original artifacts. D046 governs future work wherever older requirements conflict; it does not retrospectively qualify changed code.

[T019](../../tasks/T019-advisory-remediation.md) precedes all remaining feature work. Its first task aligns detailed contracts and the backlog; later tasks implement and test the changes. Under D047, obsolete formats/readers and their compatibility-only checks may be removed; no bridge is required. Reject unsupported state clearly and use a documented scoped fresh development runtime where needed. Preserve concurrent owner work and integrate useful Polars code into T019 rather than restart or finish superseded scope blindly.

This adoption/planning invocation changes documentation only. A future explicit implementation or next-step invocation authorizes one fitting local synthetic task under agent policy. No runtime simplification, installation, data deletion, independent acceptance or release is claimed by this ADR.
