# Change log

This file summarizes authored changes. Entries under Unreleased are development checkpoints, not financial-use acceptance or a product release. Detailed commands, artifacts and qualification limits remain in the linked task reports.

## Unreleased

### October 22, 2026: synthetic checkpoint foundation

- Added [bounded exact decimal primitives](docs/tasks/T003.2-exact-values.md): original source text/quantum, explicit unknowns, deterministic arithmetic and a synthetic diagnostic basis-allocation rule.
- Added [strict synthetic bundle parsing](docs/tasks/T004.1.1-synthetic-bundle-parsing.md), frozen record models, bounded input/error handling, separate raw/canonical fingerprints and fictional F000/F001 fixtures. Qualified the pinned Pydantic runtime and required packages.
- Added [in-memory checkpoint inspection and comparison](docs/tasks/T004.1.2-checkpoint-reconciliation.md): reference/cutoff/inclusion checks, lot/position/cash/basis/valuation reconciliation, scoped readiness and located findings. F001 inspects to 12 FAAA/5 FBBB, settled cash `319`, settled-cash NAV `2399` and basis `2181`, without replaying BUY-001.
- Added [immutable original-evidence storage](docs/tasks/T003.3.1-immutable-evidence.md), explicit synthetic/private runtime boundaries, verified bounded retrieval and Windows alias/publication failure cases.
- Added [exact immutable SQLite checkpoint versions](docs/tasks/T003.3.2-sqlite-checkpoints.md): canonical decimal strings and null/reason pairs in TEXT, original-evidence reconstruction, distinct source/recorded times, retained prior versions and transaction rollback. Storage does not activate an import or accept a correction.
- Added [durable preview/rejection](docs/tasks/T004.2.1-durable-previews.md) and [atomic synthetic activation/command receipts](docs/tasks/T004.2.2-atomic-activation.md), with schema-three row-preserving upgrades, historical source-conflict review, original-outcome retries and real rollback/restart/competing-writer checks.
- Added bounded parsing/reconciliation and evidence/SQLite child plans, persistent next-task progression, task evidence and developer API documentation.
- Adopted [efficient agent execution defaults](docs/engineering/NEXT_STEP.md#efficient-execution-defaults): focused context, cohesive implementation/check batches, required verification without redundant repeats, one owning evidence record and lightweight timing. Financial checks and authority gates are retained.
- Adopted [nonblocking GitHub CI handoff](docs/engineering/NEXT_STEP.md#github-synchronization-and-hosted-ci-handoff): source syncs verify local checks and upload, then finish without waiting for the new Actions run. The next sync reviews the prior relevant run and addresses in-scope failures.

Local qualification covers 348 synthetic/toolchain tests, lint/format, strict typing and isolated wheel/runtime checks. Independent software/tax/risk review, full investor workflow, recovery, API/UI, broker qualification, investor acceptance and release remain outstanding. [Current status](docs/STATUS.md) identifies the next task and current verification; [GitHub synchronization evidence](docs/tasks/SYNC-2026-10-22-github.md) records the uploaded source boundary.
