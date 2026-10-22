# Financial/application core boundary

T003.1 supplies an importable typed package and pinned Python development baseline. T003.2 adds [exact.py](exact.py): bounded decimal strings, original text/quantum, explicit unknowns, precision-80 arithmetic and synthetic diagnostic allocation. See [task evidence](../../docs/tasks/T003.2-exact-values.md) for numeric semantics, tests and limits, and the [development guide](../../docs/engineering/DEVELOPMENT.md) for exercised commands. No checkpoint importer, tax engine or investor application exists yet.

The adopted boundaries are portfolio/lot state, tax screening, risk, portfolio planning, independent validation, application use cases and adapters. See [architecture](../../docs/architecture/ARCHITECTURE.md). Create modules as authorized vertical slices need them; do not prepopulate empty classes or stub behavior.

The [foundation child plan](../../docs/tasks/T003-T004-foundation-plan.md) sequences exact values, canonical checkpoints and import/reconciliation behavior using synthetic data. Follow STATUS's one next candidate; do not jump directly to brokerage APIs or an unreviewed optimizer.
