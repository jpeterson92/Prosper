# Current status and handoff

Updated October 22, 2026. This file owns current state and the single next-task pointer; linked task reports own detailed historical evidence.

## Current task and authority

**Build T004.1.2: checkpoint reconciliation/readiness and development-time profile**, authorized by the owner's direct next-step request. All six fit criteria passed against clean `f8b59c39e8664d61fb9f9653dd05e6fe67820591`; [execution evidence and timing](tasks/T004.1.2-checkpoint-reconciliation.md) record scope, results and limits. Branch: `codex/t004.1.2-checkpoint-reconciliation`. Conversation: **Prosper | Build T004.1.2: reconcile checkpoints and profile delivery**.

The in-memory synthetic inspection/comparison layer is implemented and locally verified. This run stops before T003.3. No new dependency, broker/account access, real data, subagent, push, merge, deployment or financial-use acceptance is included. The timing review centralizes changing status here and links historical evidence, reducing repeated histories. Authorization and verification gates are unchanged.

## What exists

- Adopted product/architecture/reference plans, decision register, foundation contract, bounded briefs and sourced domain requirements.
- Locally qualified Python 3.12.4/uv/Ruff/strict-mypy/pytest/Hypothesis, project `.venv`, lockfile, check/package helper and normal caches under ADR-0003. Pydantic 2.14.1/core 2.50.1 and required locked packages support the synthetic schema; [dependency inventory](engineering/DEVELOPMENT_DEPENDENCIES.md) records versions/license metadata and limits.
- T003.2 exact decimal values, source text/quantum, explicit unknowns, precision-80 arithmetic and synthetic diagnostic allocation.
- T004.1.1 frozen strict synthetic bundle models, bounded JSON parser, source/normalized identity and fictional F000/F001 fixtures. Parse success remains `parsed_unvalidated`.
- T004.1.2 reference/cutoff/inclusion checks, exact position/lot/cash/basis/valuation inspection, scoped incomplete/contradictory readiness and snapshot comparison. Validated means inspection-valid under synthetic source assertions; planning-ready remains false. Cash buckets stay separate; `settled_cash_nav` values holdings plus supplied settled cash without assuming other buckets are zero.
- Local Git and the connected owner-created [GitHub source repository](https://github.com/jpeterson92/Prosper); earlier main baseline was uploaded. This and preceding feature branches remain local/unmerged. Source backup does not cover private investor state or ignored artifacts.

## Current evidence and limits

The standard helper check passes lint/format, strict typing and **179 tests** (37 checkpoint, 82 parser, 56 exact-value, four bootstrap). Offline fresh-wheel/runtime verification and isolated installed-module F000/F001 smoke pass. Authored text/local links/manifest and whitespace pass. Exact commands, artifact identity, review findings and wall-clock phases are in the execution report. No current-revision hosted CI result is claimed.

F001 yields 12 FAAA/5 FBBB, settled cash 319, settled-cash NAV 2399, basis 2181 and market-minus-basis -101. F000 comparison yields +2 FAAA, -181 cash, +181 basis and -101 value; the descriptive bridge shows -100 prior-holdings mark effect and 1 reported new-event fee. No transaction replay or investment return is implemented. F002/F003 block validation; F004/F009 preserve incomplete basis/coverage while holdings inspection can remain available. Basis/fees are not reconstructed or counted twice.

Same-agent review and independently derived expectations were exercised; independent software/tax/risk review, investor acceptance, fresh-session instruction-loading qualification and release were not. No database, transactional import/correction/idempotency workflow, recovery, API/UI, tax/risk engine, optimizer, broker adapter, investor installer or released product exists. Full storage/transport, financial eligibility and G1-G3 remain unpassed. Earlier hosted CI applies only to its older uploaded checkpoint.

## Next task and remaining gates

**Single next candidate: [T003.3: exact checkpoint persistence](tasks/T003-T004-foundation-plan.md#t0033-exact-checkpoint-persistence)**, ready to attempt after fresh fit/dependency assessment of actual parser/inspection contracts, evidence and failure cases. T003.1, T003.2, T004.1.1 and T004.1.2 are locally verified; the in-memory T004.1 parent is complete within its synthetic boundary. No T003.3 schema, database or persistence implementation began here.

T002/T017 must obtain G1 broker/manual-workflow and permitted data evidence before substantial broker-facing/quantitative work. T018 carries recovery/state requirements into later slices. G2/G3 still need independent model/specialist/investor evidence. Ready is not accepted/released.

The [decision register](DECISIONS.md) retains 25 accepted, 5 confirmed and 7 open entries. Open: D010 broker/workflow; D012 risk data/settings/discrete method/investor limits; D014 license; D016 distribution/service qualification; D017 supported years/freshness; D018 public release/name/support; D027 first experiment. Accepted architecture/product/tax policy is unchanged.

## Identity and historical evidence

The exact final local commit is reported in the handoff and resolved with `git rev-parse HEAD`, avoiding a self-referential hash. The [authored manifest](PLANNING_MANIFEST.sha256) fingerprints source/tests/fixtures/docs/lock; ignored/private state and Git internals are excluded. Publication, merge and release are separate owner-directed actions.

- [Parser execution](tasks/T004.1.1-synthetic-bundle-parsing.md) and [T004.1 decomposition](tasks/T004.1-checkpoint-validation-plan.md).
- [Exact-value execution](tasks/T003.2-exact-values.md) and [original toolchain qualification](tasks/T003.1-development-baseline.md).
- [Filesystem/GitHub setup evidence](tasks/SETUP-local-filesystem.md), including initial hosted [run 39865871731](https://github.com/jpeterson92/Prosper/actions/runs/39865871731) for `ae0360c2d3e93cd276f26f1466619beff3346fdc`. That task observed public visibility/unprotected main; settings were not changed or freshly queried here.
- [ADR-0001](architecture/decisions/0001-adopt-project-architecture.md), [ADR-0002](architecture/decisions/0002-adopt-critical-review-actions.md), [ADR-0003](architecture/decisions/0003-adopt-standard-local-development.md) and [pre-implementation review](reviews/2026-10-22-pre-implementation-review.md). Historical counts/results describe those runs; sources/tax/legal checks were not renewed here.
