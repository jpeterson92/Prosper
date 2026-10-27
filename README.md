# Prosper

Current direction: one local exploratory workspace. Start with actual-input diagnostics, then use the existing model/candidate/worksheet path and improve observed pain points. See the [MVP route](docs/tasks/REMAINING_WORK_PLAN.md#mvp-delivery-route) and [local guide](docs/guides/LOCAL_ARTIFACT.md). All inputs use the same application contracts without a synthetic/real category; independent review/calibration and public-release work remain separate from exploratory use.

A local advisory application in development for self-directed tax-loss harvesting in existing individual-stock/direct-indexing portfolios. V1 is current-snapshot import -> estimated loss/risk -> independently checked whole-share suggestions -> dated manual worksheet -> refreshed holdings next session. The investor makes brokerage trades. Execution tracking, basis/account reconstruction, reservations, forward monitoring and background scheduling are outside v1.

## Current state and next work

[STATUS](docs/STATUS.md) records what exists, actual checks and one next candidate. [PROJECT_PLAN](docs/PROJECT_PLAN.md) defines a working v1; [REMAINING_WORK_PLAN](docs/tasks/REMAINING_WORK_PLAN.md) is the sole executable backlog. The current app has source-shaped and normalized import, conditional lot diagnostics, benchmark/history/input review, exploratory risk/candidates, dated worksheets and current-format recovery. The minimal CSV opening retains unknown facts without a context file. Coding checks use invented fixtures; an actual-input owner session, source/profile adequacy and independent financial acceptance remain separate. Follow the short MVP route rather than repeating historical foundation tasks.

No backwards compatibility is required for this unreleased application. Current financial/source/security/transaction/recovery checks remain. Prior plans/ADRs are in Git checkpoint `69f8cba299b7d130a87684809df77fe124b8fe5d`; current requirements are incorporated directly below, without an archive or mandatory decision-history reading.

## Project map

| Need | Current document |
| --- | --- |
| Agent authority, next-step intake/checks | [AGENTS](AGENTS.md), [NEXT_STEP](docs/engineering/NEXT_STEP.md) |
| V1 behavior and delivery | [Product](docs/product/SPEC.md), [plan](docs/PROJECT_PLAN.md), [remaining tasks](docs/tasks/REMAINING_WORK_PLAN.md) |
| Tax/screening and lot/cash/objective rules | [Tax](docs/domain/TAX_POLICY.md), [portfolio](docs/domain/PORTFOLIO_CONSTRUCTION.md) |
| Vanguard equity proxy, history/marks/classification | [Market inputs](docs/domain/BENCHMARK_INPUTS.md) |
| Selected Python IDR-DCC-NL and review/calibration | [Risk](docs/domain/RISK_MODEL.md) |
| State, numerics and software boundaries | [Records](docs/architecture/DATA_CONTRACTS.md), [numerics](docs/engineering/ADVISORY_NUMERICS.md), [architecture](docs/architecture/ARCHITECTURE.md) |
| Development, source/check entry points | [Development](docs/engineering/DEVELOPMENT.md), [subsystem map](docs/engineering/AGENT_WORKFLOW.md#task-navigation) |
| Acceptance/review and unresolved decisions | [Validation](docs/engineering/VALIDATION.md), [decision locator](docs/DECISIONS.md) |
| Qualified sources and private file collection | [Sources](docs/research/SOURCES.md), [Fidelity guide](docs/guides/FIDELITY_IMPORT.md) |

## Development

From the repository root in PowerShell, use `./scripts/dev.ps1 -Command bootstrap` once and `-Command dev` for affected work with explicit test paths when the baseline is cold/stale. Browser and current synthetic-launch commands are in [DEVELOPMENT](docs/engineering/DEVELOPMENT.md). Full checkpoints run only when authorized. Synthetic examples/tests/logs are the default; private data/secrets stay outside source and require explicit authority before AI access.

Source commits and local tests do not authorize account access, real-data disclosure, financial use or publication. [SECURITY](SECURITY.md) and [CONTRIBUTING](CONTRIBUTING.md) apply; the software distribution/license and supported investor release remain open.
