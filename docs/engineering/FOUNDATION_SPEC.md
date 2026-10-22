# Synthetic foundation specification and first implementation brief

Date: October 22, 2026. Status: **adopted written G0 contract; parent decomposed into bounded child briefs**. [ADR-0002](../architecture/decisions/0002-adopt-critical-review-actions.md) records approval of the review actions. This document completes the foundation planning package; it is not a database schema, installed environment or tested application. The first direct `/next` assessment produced the [T003/T004 child plan](../tasks/T003-T004-foundation-plan.md) under the [sizing/decomposition protocol](NEXT_STEP.md) and stopped without implementation. This combined parent is not a one-run execution unit; a later invocation can execute one reassessed ready child. STATUS owns the next-candidate pointer.

## First-slice outcome and exclusions

After a later implementation instruction, the first slice will let a developer/test investor load one synthetic canonical checkpoint bundle, preview records, inspect lots/positions/cash and reconciliation/coverage reasons in a minimal React UI, and commit or reject the import through typed FastAPI services backed by SQLite. Reimporting the same evidence must not add holdings or duplicate events. Establish Windows x64 development/setup evidence and reproducible checks.

No tax recommendation, optimizer, broker adapter, live price access, actual brokerage order file, AI, Tauri installer, hypothetical-to-actual trade mutation or full historical basis engine belongs in this slice. Reference optimization cases remain written expectations for later slices. Other adopted components enter only when needed by their slice.

## Setup prerequisite when decomposing this parent

The first next-step assessment must budget the combined foundation as a parent outcome rather than assume setup, persistence, importer, API and UI fit one run. Its child plan should explicitly include a small reproducible development/bootstrap task before substantial application work. Scope local Git initialization/checkpointing in that later task if permissions allow; no remote creation or publication is implied. Until a real Git identity exists, retain file hashes and an explicit no-Git statement.

Qualify the Python/uv environment, compatible exact dependency versions, strict checker, source/test layout and actually exercised lint/type/test commands for the first Python slice. Use project-local `.venv`, normal caches and ignored synthetic runtime/test/evidence directories under [ADR-0003](../architecture/decisions/0003-adopt-standard-local-development.md). Keep private investor data outside the repository. Add frontend, API-client generation, browser checks, numerical packages and packaging only when their child task needs them. Do not install the entire eventual stack to claim setup complete. A clean local repeat of the declared setup/checks is evidence; an invented command list or successful dependency installation alone is not. A Windows GitHub Actions workflow is prepared alongside local repeatability checks; the initial uploaded developer baseline passed its hosted run, as recorded in [STATUS](../STATUS.md). Later local changes require their own exact-revision hosted evidence.

This prerequisite is planning guidance for the later bounded task, not authorization to initialize Git, install dependencies or implement it during a review or decomposition run.

## Exact-value contract

The following bounds define the first canonical schema's engineering capability. A later broker qualification may require an explicit schema revision; never round an unsupported source value to make it fit.

| Concern | Contract |
| --- | --- |
| Book money, price and share quantity | Decimal strings in JSON and SQLite TEXT; no REAL/float storage or binary-float parse round trip for authoritative values |
| Canonical representation | Base-10 fixed-point string, optional leading minus only where the field permits it, no grouping/currency symbols/exponent/NaN/infinity; canonical zero is `0`; remove redundant trailing fractional zeros while preserving original text/quantum in source metadata |
| Initial bounds | At most 28 significant digits and at most 12 fractional digits per supported exact field; reject excess precision/range, do not truncate; source adapters must qualify these bounds |
| Domain signs | Holdings/lots/prices nonnegative, prices strictly positive where needed; quantities strictly positive for activity; side/type expresses direction; cash movements/P&L may be signed; negative holdings/borrowed cash are unsupported in this scope |
| Arithmetic | Decimal working precision 80 for the admitted operands/intermediates; check bounds and nonfinite results explicitly; comparisons use unrounded book values, with declared allocation/tolerance rules |
| Display | USD normally displayed to cents, quantities/prices with sufficient visible precision; display rounding never changes stored values |
| Source basis/quantum | Preserve total adjusted basis, source precision/rounding unit and adjustment/holding evidence; per-share basis is derived unless independently supplied and reconciled |
| Diagnostic partial-lot allocation | For a supported synthetic pro-rata split, allocate remaining total basis times sold quantity / remaining quantity, round half-even at the source basis quantum, and preserve the exact remainder; final full disposal takes all remaining basis |
| Production lot allocation | Must match qualified broker/reviewed tax-accounting semantics. The synthetic diagnostic rule is not a universal broker convention; mismatch/unknown quantum blocks affected financial use rather than rewriting authoritative basis |
| Numerical arrays | Explicit float64 conversion only for derived risk/solver inputs, with finite/range/ordering checks. Float-derived results do not write exact book records back |

A source value `0.1000000000001` exceeds the first schema's fractional bound and is rejected, not changed to `0.1`. A basis of `1.00` split into three sequential one-share disposals under the synthetic rule allocates `0.33`, `0.34`, `0.33`; the total remains `1.00`. Broker-confirmed tax allocations can differ and require separate reconciliation.

Canonical hashes must include schema and semantics versions and deterministic field/record ordering; retain original input-byte hashes separately. Equivalent normalized values do not erase source formatting or merge distinct events. A hash is identity evidence, not an authenticity guarantee.

## Canonical bundle transport and semantics

Version `synthetic-checkpoint-v1` is a written contract for a single UTF-8 JSON object containing metadata and typed record arrays. Exact values are strings, dates are ISO dates, timestamps include offsets and original source timezone. Require schema version, fictional-data flag, bundle/source IDs, account/profile identity, source cutoff convention and coverage. Unknown values use explicit null plus a reason; missing is not zero. Reject unknown schema versions, duplicate keys/IDs, unexpected fields, invalid dates/precision and inconsistent references with located error messages. Apply parsing-size limits and no network/file execution.

The implementation may materialize this example as a fixture only after authorization. For this slice, each bundle is an **authoritative checkpoint** with explicit activity-inclusion references. Activity is historical evidence already reflected in that checkpoint and is not replayed into holdings/cash. Earlier/later snapshots can be compared for reconciliation, but this slice does not implement arbitrary transaction replay. Ambiguous real-world cutoffs remain unsupported/staged.

Imports have preview/staged, rejected and committed states. Validate the whole proposed checkpoint before replacing the active reference in one database transaction. Rejection leaves the last valid state intact. A repeated identical import returns the prior result; same source event ID with changed content requires an explicit correction/supersession and review. Exact duplicates versus conflicting versions are different outcomes.

## Complete fictional fixture F001

All IDs/symbols below are fictional; no prices or records are market observations. This fixture is independent of the R01 optimization portfolio.

| Metadata | Value |
| --- | --- |
| Bundle/schema | F001 / synthetic-checkpoint-v1 |
| Profile/account | DEMO-HOUSEHOLD / DEMO-TAXABLE-1; one U.S. taxable traded account; USD |
| Cutoff | October 22, 2026, 16:00 America/New_York, `2026-10-22T16:00:00-04:00` |
| Inclusion convention | Closing checkpoint includes activity event BUY-001 and all stipulated earlier activity; quantities/cash below are post-event and stipulated settled |
| Coverage | September 22 through October 22 inclusive; synthetic source coverage for this fictional household; no other relevant accounts/acquisitions/loss sales/automation or outstanding restrictions stipulated |
| Tax/security evidence | Fictional domestic ordinary-corporation common shares, distinct issuer/security IDs; no special events, no basis/holding adjustments, no unresolved classifications stipulated |
| Intended state | Inspection/reconciliation only; not an actionable tax plan |

| Security | Internal ID | Quantity | Mark | Market value |
| --- | --- | --- | --- | --- |
| FAAA | SEC-FAAA | `12` | `90` | `1080` |
| FBBB | SEC-FBBB | `5` | `200` | `1000` |
| USD cash | CASH-USD | N/A | N/A | `319` |

Quote timestamps are the declared cutoff. These are valuation marks for this fixture, not execution quotes. Total NAV is `2399`.

| Lot ID | Security | Acquisition date | Remaining quantity | Total adjusted basis | Basis quantum |
| --- | --- | --- | --- | --- | --- |
| LOT-A-OLD | SEC-FAAA | 2024-01-02 | `10` | `1000` | `0.01` |
| LOT-A-NEW | SEC-FAAA | 2026-10-21 | `2` | `181` | `0.01` |
| LOT-B-OLD | SEC-FBBB | 2024-01-02 | `5` | `1000` | `0.01` |

BUY-001 is a purchase of `2` SEC-FAAA shares on October 21 at `90`, explicit fee `1`, gross principal `180`, cash outflow `181`, declared settlement date October 22, linked to LOT-A-NEW. The checkpoint already includes it. Acquisition fee `1` is already included in that lot's `181` basis.

Stipulated prior checkpoint F000, October 20 at the same local closing time: FAAA `10` at mark `100`, FBBB `5` at `200`, settled USD cash `500`, old lots only. Its NAV was `2500`. F001 minus F000 yields +2 FAAA shares, cash -181 and added basis 181. The new valuation is lower by 101: 100 from the changed FAAA mark on the old ten shares plus 1 explicit fee. This comparison is a reference explanation, not transaction replay logic or an investment performance metric.

Position quantities reconcile exactly to lots: FAAA `10 + 2 = 12`, FBBB `5`. Total basis is `2181`; per-security market-minus-basis is FAAA `-101`, FBBB `0`. Cash is stipulated both settled and available `319`; do not derive this funding status from trade dates for a real account.

No benchmark/covariance or investor trade limits are needed for this inspection-only slice. Their absence means portfolio-planning readiness is incomplete; it must not prevent truthful holdings inspection or permit a recommendation.

## Required variants and expected outcomes

| Variant | Change | Expected outcome |
| --- | --- | --- |
| F001 repeat | Import the same bundle again | Holdings stay 12 FAAA / 5 FBBB and cash 319; no duplicated event/lot/import mutation |
| F002 ambiguous inclusion | Keep BUY-001 but remove the proven checkpoint inclusion convention | Stage/reject commit with a specific boundary reason; do not report 14 shares |
| F003 lot mismatch | Position FAAA remains 12 but lot quantities sum to 13 | Reconciliation fails; active prior state unchanged |
| F004 missing basis | LOT-A-NEW basis null with reason `source_missing` | Preserve unknown; no zero/fee inference; lot analysis readiness incomplete. A structurally valid checkpoint may commit if quantity/cash reconcile, but no affected actionable financial result is available |
| F005 conflict | Same BUY-001 ID, different quantity/fee without supersession evidence | Report conflicting source versions; do not merge or silently overwrite |
| F006 precision | Exact field `0.1000000000001` | Reject with field/bound reason; no implicit rounding |
| F007 interruption | Fail before import transaction commits | Last committed checkpoint and receipts stay consistent; staged evidence is identifiable/recoverable |
| F008 concurrent commit | Two previews attempt to replace the same expected active generation | One atomic commit; the other receives stale-generation/review-required outcome; same-key retries are idempotent |
| F009 unknown coverage | External household coverage becomes unknown | Inspection remains available; coverage reason shown and planning readiness incomplete; no clean-household claim |

Strictness is layered: malformed or contradictory records cannot commit; explicit unknown fields may be stored as incomplete facts if structural/account reconciliation invariants hold. Financial capability remains blocked at its dependency scope, or account-wide where impact is unbounded. No partial silent row drops.

## Minimal interface and API behavior

Implement preview, inspect current checkpoint/readiness, and commit/reject through application services. Generate the TypeScript contract from the actual OpenAPI schema. Show fictional-data identity, source cutoff/inclusion, exact values with display rounding, error locations, readiness/reasons and the active generation. Do not show harvest recommendations or an enabled approve-trades control.

Use loopback-only access, bundled UI assets, explicit local session/origin checks, safe parser boundaries and private investor runtime storage outside the source repository, with ignored project-local synthetic test storage allowed. Provide one authoritative writer, expected-generation checks and idempotency receipts. Logical contract records need not each become a table/class. If work is synchronous in this slice, do not add a job queue/worker just to implement future solver lifecycle concepts.

## Acceptance and verification for the later implementation task

- Demonstrate F001 and every listed variant through domain/application checks; independently verify its arithmetic and declared inclusion semantics.
- Test exact-value string persistence and API/UI round trips, unknown propagation, error localization, active-state preservation, idempotency and generation conflicts.
- Use a small Playwright workflow for preview -> inspect -> commit -> repeat/reject; visual/manual acceptance checks formatting, fictional-data labeling and error usability.
- Establish uv/Ruff/type-check/test commands and compatible Python/frontend dependencies on Windows x64; pin only versions actually exercised. Select the strict checker from verified annotation support, not novelty alone.
- Capture actual import/preview latency and dependency footprint; compare with the provisional [measurement charter](VALIDATION.md), then refine budgets from observed paper workflow and workload measurements. The 100-stock/2,000-lot/500-universe target is not established by F001.
- Include a consistent local backup/restore acceptance case for the state/evidence used by this slice; do not claim later risk/optimizer/file recovery is qualified by it.
- Report exact candidate identity, checks/results, unrun checks and limitations. Until Git is deliberately initialized under an authorized task, use file hashes and state that no Git revision exists.

The planning artifacts specify these checks. T003.1 qualifies the developer baseline and [T003.2](../tasks/T003.2-exact-values.md) qualifies the primitive exact-value/synthetic allocation layer locally; [T004.1.1](../tasks/T004.1.1-synthetic-bundle-parsing.md) now qualifies structural parsing and source/normalized identity locally. [T004.1.2](../tasks/T004.1.2-checkpoint-reconciliation.md) now qualifies synthetic in-memory reconciliation/inspection locally; database, API/UI and recovery remain unimplemented. G0 is document-ready for the subsequent bounded implementation tasks. G1-G3, specialist review and all financial-use acceptance remain unpassed.
