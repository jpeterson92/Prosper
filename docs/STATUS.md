# Current status and handoff

Updated October 22, 2026. This file owns current state and the single next-task pointer; linked task reports own detailed historical evidence.

## Current task and authority

**Plan T003.3: decompose exact checkpoint persistence**, under the owner's direct `/next`. Fresh inspection against clean `0dfa234814d68502b6fa36c2422cfb1e4ee1ca04` found that bounded changes and completion margin need decomposition; the other four fit criteria pass. The [child plan](tasks/T003.3-checkpoint-persistence-plan.md) records evidence, complete briefs and scope boundaries. Branch: `codex/t003.3-persistence-plan`. Conversation: **Prosper | Plan T003.3: split evidence and checkpoint persistence**.

This invocation changes documentation only and stops before child implementation. T003.3.1 owns immutable original evidence and runtime-path qualification; T003.3.2 waits for that verified interface before adding exact immutable SQLite checkpoint versions. No application, executable test/fixture, dependency, evidence store or database schema was created. No broker/account access, real data, subagent, push, merge, deployment or financial-use acceptance is included. Authorization and verification gates are unchanged.

## What exists

- Adopted product/architecture/reference plans, decision register, foundation contract, bounded briefs and sourced domain requirements.
- Locally qualified Python 3.12.4/uv/Ruff/strict-mypy/pytest/Hypothesis, project `.venv`, lockfile, check/package helper and normal caches under ADR-0003. Pydantic 2.14.1/core 2.50.1 and required locked packages support the synthetic schema; [dependency inventory](engineering/DEVELOPMENT_DEPENDENCIES.md) records versions/license metadata and limits.
- T003.2 exact decimal values, source text/quantum, explicit unknowns, precision-80 arithmetic and synthetic diagnostic allocation.
- T004.1.1 frozen strict synthetic bundle models, bounded JSON parser, source/normalized identity and fictional F000/F001 fixtures. Parse success remains `parsed_unvalidated`.
- T004.1.2 reference/cutoff/inclusion checks, exact position/lot/cash/basis/valuation inspection, scoped incomplete/contradictory readiness and snapshot comparison. Validated means inspection-valid under synthetic source assertions; planning-ready remains false. Cash buckets stay separate; `settled_cash_nav` values holdings plus supplied settled cash without assuming other buckets are zero.
- Local Git and the connected owner-created [GitHub source repository](https://github.com/jpeterson92/Prosper); earlier main baseline was uploaded. This and preceding feature branches remain local/unmerged. Source backup does not cover private investor state or ignored artifacts.

## Current evidence and limits

Previous implementation evidence at the incoming commit: the standard helper check passed lint/format, strict typing and **179 tests** (37 checkpoint, 82 parser, 56 exact-value, four bootstrap). Offline fresh-wheel/runtime verification and isolated installed-module F000/F001 smoke passed. Exact commands, artifact identity, review findings and wall-clock phases are in the [execution report](tasks/T004.1.2-checkpoint-reconciliation.md). These application checks were not rerun for this documentation-only invocation. No current-revision hosted CI result is claimed.

Current planning verification: `.venv\Scripts\python.exe scripts/check_project.py --write-manifest` and the subsequent read-only checker passed **64 authored files, 43 Markdown files and 312 local links**. `git diff --check` passed. Scope/diff review found only the child plan, parent plan, roadmap, status and manifest changed. Same-agent review maps every original T003.3 acceptance obligation to a child; no unresolved finding blocks the planning outcome. Application check/package, filesystem/SQLite qualification, independent review, hosted CI and investor acceptance were not run in this invocation.

F001 yields 12 FAAA/5 FBBB, settled cash 319, settled-cash NAV 2399, basis 2181 and market-minus-basis -101. F000 comparison yields +2 FAAA, -181 cash, +181 basis and -101 value; the descriptive bridge shows -100 prior-holdings mark effect and 1 reported new-event fee. No transaction replay or investment return is implemented. F002/F003 block validation; F004/F009 preserve incomplete basis/coverage while holdings inspection can remain available. Basis/fees are not reconstructed or counted twice.

Same-agent review and independently derived expectations were exercised; independent software/tax/risk review, investor acceptance, fresh-session instruction-loading qualification and release were not. No database, transactional import/correction/idempotency workflow, recovery, API/UI, tax/risk engine, optimizer, broker adapter, investor installer or released product exists. Full storage/transport, financial eligibility and G1-G3 remain unpassed. Earlier hosted CI applies only to its older uploaded checkpoint.

## Next task and remaining gates

**Single next candidate: [T003.3.1: immutable evidence and runtime boundary](tasks/T003.3-checkpoint-persistence-plan.md#t00331-immutable-evidence-and-runtime-boundary)**, ready to attempt after fresh fit/dependency assessment. T003.1, T003.2, T004.1.1 and T004.1.2 remain locally verified; the in-memory T004.1 parent is complete within its synthetic boundary. T003.3.2 waits for T003.3.1; T004.2 still waits for the complete T003.3 parent. No child implementation began here.

T002/T017 must obtain G1 broker/manual-workflow and permitted data evidence before substantial broker-facing/quantitative work. T018 carries recovery/state requirements into later slices. G2/G3 still need independent model/specialist/investor evidence. Ready is not accepted/released.

The [decision register](DECISIONS.md) retains 25 accepted, 5 confirmed and 7 open entries. Open: D010 broker/workflow; D012 risk data/settings/discrete method/investor limits; D014 license; D016 distribution/service qualification; D017 supported years/freshness; D018 public release/name/support; D027 first experiment. Accepted architecture/product/tax policy is unchanged.

## Identity and historical evidence

The exact final local commit is reported in the handoff and resolved with `git rev-parse HEAD`, avoiding a self-referential hash. The [authored manifest](PLANNING_MANIFEST.sha256) fingerprints source/tests/fixtures/docs/lock; ignored/private state and Git internals are excluded. Publication, merge and release are separate owner-directed actions.

- [Parser execution](tasks/T004.1.1-synthetic-bundle-parsing.md) and [T004.1 decomposition](tasks/T004.1-checkpoint-validation-plan.md).
- [T003.3 decomposition and storage acceptance](tasks/T003.3-checkpoint-persistence-plan.md); planning only, no storage experiments.
- [Exact-value execution](tasks/T003.2-exact-values.md) and [original toolchain qualification](tasks/T003.1-development-baseline.md).
- [Filesystem/GitHub setup evidence](tasks/SETUP-local-filesystem.md), including initial hosted [run 39865871731](https://github.com/jpeterson92/Prosper/actions/runs/39865871731) for `ae0360c2d3e93cd276f26f1466619beff3346fdc`. That task observed public visibility/unprotected main; settings were not changed or freshly queried here.
- [ADR-0001](architecture/decisions/0001-adopt-project-architecture.md), [ADR-0002](architecture/decisions/0002-adopt-critical-review-actions.md), [ADR-0003](architecture/decisions/0003-adopt-standard-local-development.md) and [pre-implementation review](reviews/2026-10-22-pre-implementation-review.md). Historical counts/results describe those runs; sources/tax/legal checks were not renewed here.
