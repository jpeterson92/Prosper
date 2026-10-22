# Future financial/application core

T003.1 supplies a minimal importable typed package and pinned Python development baseline. The package initializer contains no financial behavior. See the [development guide](../../docs/engineering/DEVELOPMENT.md) for exercised commands and project-local environment paths.

The adopted boundaries are portfolio/lot state, tax screening, risk, portfolio planning, independent validation, application use cases and adapters. See [architecture](../../docs/architecture/ARCHITECTURE.md). Create modules as authorized vertical slices need them; do not prepopulate empty classes or stub behavior.

The [foundation child plan](../../docs/tasks/T003-T004-foundation-plan.md) sequences exact values, canonical checkpoints and import/reconciliation behavior using synthetic data. Follow STATUS's one next candidate; do not jump directly to brokerage APIs or an unreviewed optimizer.
