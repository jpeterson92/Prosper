# Current status and handoff

Updated October 22, 2026. This file owns current state and the single next-task pointer; linked task reports own detailed historical evidence.

## Current task and authority

**Sync accumulated source to GitHub**, explicitly authorized by the owner's request to sync all changes with documentation. [Synchronization evidence](tasks/SYNC-2026-10-22-github.md) and the [change log](../CHANGELOG.md) summarize scope and verification. Conversation: **Prosper | Sync: publish verified foundation to GitHub**. This is source synchronization, not a next-stage build or product release.

T003.3.2 and its bounded T003.3 parent remain implemented and locally verified. The seven accumulated commits and remaining workflow-guidance changes are uploaded through a fast-forward main update and ordinary push, with hosted Windows CI passed for the synchronization checkpoint. The documentation-only follow-up records those results and the owner's explicit nonblocking CI preference. Future syncs review the previous run and fix in-scope failures, then finish without waiting for their new Actions run. No T004.2 implementation, broker/account access, real data, subagent, release, deployment or financial-use acceptance is included. Financial/acceptance gates are unchanged.

## What exists

- Adopted product/architecture/reference plans, decision register, foundation contract, bounded briefs and sourced domain requirements.
- Locally qualified Python 3.12.4/uv/Ruff/strict-mypy/pytest/Hypothesis, project `.venv`, lockfile, check/package helper and normal caches under ADR-0003. Pydantic 2.14.1/core 2.50.1 and required locked packages support the synthetic schema; [dependency inventory](engineering/DEVELOPMENT_DEPENDENCIES.md) records versions/license metadata and limits.
- T003.2 exact decimal values, source text/quantum, explicit unknowns, precision-80 arithmetic and synthetic diagnostic allocation.
- T004.1.1 frozen strict synthetic bundle models, bounded JSON parser, source/normalized identity and fictional F000/F001 fixtures. Parse success remains `parsed_unvalidated`.
- T004.1.2 reference/cutoff/inclusion checks, exact position/lot/cash/basis/valuation inspection, scoped incomplete/contradictory readiness and snapshot comparison. Validated means inspection-valid under synthetic source assertions; planning-ready remains false. Cash buckets stay separate; `settled_cash_nav` values holdings plus supplied settled cash without assuming other buckets are zero.
- T003.3.1 explicit synthetic/private runtime boundaries, immutable versioned original-evidence publication and bounded hash/length-verified retrieval. Private-mode qualification used only synthetic scratch; no investor runtime is installed. Missing/corrupt/redirected/multiple-link objects fail explicitly. Receipts do not commit imports.
- T003.3.2 standard-library SQLite 3.45.3, version-one STRICT canonical-TEXT checkpoint storage, immutable append/read, raw duplicate reuse, source/recorded-time separation and verified reconstruction from original evidence. Failed inserts/evidence checks roll back references; prior versions remain queryable. Stored versions do not select an active portfolio or accept corrections.
- Local Git and the connected owner-created [GitHub source repository](https://github.com/jpeterson92/Prosper). Main now includes the accumulated feature history and workflow-policy changes; [sync evidence](tasks/SYNC-2026-10-22-github.md) records the uploaded checkpoint and passing hosted CI. Source backup does not cover private investor state or ignored artifacts.

## Current evidence and limits

The standard helper check passed lint/format, strict mypy and **259 tests** (37 SQLite, 43 evidence, 37 checkpoint, 82 parser, 56 exact-value, four bootstrap), with no skips. SQL TEXT/unknown-pair round trips, real transaction rollback, schema/evidence corruption and Windows database/sidecar symlink guards passed. Offline fresh-wheel/runtime qualification and separate installed-module checkpoint write/read processes passed. [Task evidence](tasks/T003.3.2-sqlite-checkpoints.md) records implementation commands, wheel identity, review findings and timing. The sync repeated full local check/package and observed hosted [run 39878226584](https://github.com/jpeterson92/Prosper/actions/runs/39878226584) pass for `5ba7d6b0e7543b721eb813009ac7eea7b83166b2`. That is the reviewed preceding run; the documentation-only follow-up's new hosted result is intentionally unverified until the next sync under the owner's preference. Its exact uploaded hash is reported in the final handoff.

Final sync authored text/links/manifest verification passed **72 files, 47 Markdown files and 354 local links**; `git diff --check` passed after the CI-preference update. Application code/tests did not change after the passing full check/package. No unresolved finding blocks this bounded outcome. Failed transactions may leave complete unreferenced evidence; interrupted publication/initialization remains non-ready where applicable. Automatic cleanup/complete recovery remain T004.3. No ACL isolation, hostile concurrent path-replacement or power-loss guarantee is established.

F001 yields 12 FAAA/5 FBBB, settled cash 319, settled-cash NAV 2399, basis 2181 and market-minus-basis -101. F000 comparison yields +2 FAAA, -181 cash, +181 basis and -101 value; the descriptive bridge shows -100 prior-holdings mark effect and 1 reported new-event fee. No transaction replay or investment return is implemented. F002/F003 block validation; F004/F009 preserve incomplete basis/coverage while holdings inspection can remain available. Basis/fees are not reconstructed or counted twice.

Same-agent review and independently derived expectations were exercised; independent software/tax/risk review, investor acceptance, fresh-session instruction-loading qualification and release were not. No active transactional import/correction/idempotency workflow, recovery, API/UI, tax/risk engine, optimizer, broker adapter, investor installer or released product exists. Checkpoint persistence is locally verified; full transport/workflow, financial eligibility and G1-G3 remain unpassed. Earlier hosted CI applies only to its older uploaded checkpoint.

## Next task and remaining gates

**Single next candidate: [T004.2: preview and atomic import commit](tasks/T003-T004-foundation-plan.md#t0042-preview-and-atomic-import-commit)**, ready to attempt after fresh fit/dependency assessment of actual SQLite/evidence contracts and application failure cases. The bounded T003.3 parent is locally verified. No T004.2 implementation began here.

T002/T017 must obtain G1 broker/manual-workflow and permitted data evidence before substantial broker-facing/quantitative work. T018 carries recovery/state requirements into later slices. G2/G3 still need independent model/specialist/investor evidence. Ready is not accepted/released.

The [decision register](DECISIONS.md) retains 25 accepted, 5 confirmed and 7 open entries. Open: D010 broker/workflow; D012 risk data/settings/discrete method/investor limits; D014 license; D016 distribution/service qualification; D017 supported years/freshness; D018 public release/name/support; D027 first experiment. Accepted architecture/product/tax policy is unchanged.

## Identity and historical evidence

Workflow configuration, October 22: at the owner's request, [AGENTS.md](../AGENTS.md) adopts [efficient execution defaults](engineering/NEXT_STEP.md#efficient-execution-defaults), referenced by the agent workflow. The original documentation-only configuration checks passed while T003.3.1 was in progress; the later build reports preserve that chronology. This sync incorporates those previously separate uncommitted policy edits. Fresh-session adherence and a speed improvement remain unverified.

The exact final local commit is reported in the handoff and resolved with `git rev-parse HEAD`, avoiding a self-referential hash. The [authored manifest](PLANNING_MANIFEST.sha256) fingerprints source/tests/fixtures/docs/lock; ignored/private state and Git internals are excluded. Publication, merge and release are separate owner-directed actions.

The earlier evidence/SQLite build commits deliberately excluded concurrent AGENTS/NEXT_STEP/AGENT_WORKFLOW edits. This explicitly authorized synchronization now includes them and regenerates one manifest for the complete authored tree.

- [Parser execution](tasks/T004.1.1-synthetic-bundle-parsing.md) and [T004.1 decomposition](tasks/T004.1-checkpoint-validation-plan.md).
- [T003.3 decomposition and storage acceptance](tasks/T003.3-checkpoint-persistence-plan.md); planning only, no storage experiments.
- [Exact-value execution](tasks/T003.2-exact-values.md) and [original toolchain qualification](tasks/T003.1-development-baseline.md).
- [Filesystem/GitHub setup evidence](tasks/SETUP-local-filesystem.md), including initial hosted [run 39865871731](https://github.com/jpeterson92/Prosper/actions/runs/39865871731) for `ae0360c2d3e93cd276f26f1466619beff3346fdc`. That task observed public visibility/unprotected main; settings were not changed or freshly queried here.
- [ADR-0001](architecture/decisions/0001-adopt-project-architecture.md), [ADR-0002](architecture/decisions/0002-adopt-critical-review-actions.md), [ADR-0003](architecture/decisions/0003-adopt-standard-local-development.md) and [pre-implementation review](reviews/2026-10-22-pre-implementation-review.md). Historical counts/results describe those runs; sources/tax/legal checks were not renewed here.
