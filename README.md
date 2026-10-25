# Prosper

An open-source project in formation for investors who want to manage tax-loss harvesting in their own brokerage accounts. The initial product direction is **individual stocks and direct indexing, with file imports and trades placed by the investor**.

The project also serves as a current FinTech learning/interview showcase. The owner adopted the recommended architecture and staged learning approach on October 22, 2026. The [official project plan](docs/PROJECT_PLAN.md) and [adoption ADR](docs/architecture/decisions/0001-adopt-project-architecture.md) record the baseline; the [architecture comparison](docs/architecture/TECHNOLOGY_TRADEOFFS.md) preserves reasoning, alternatives and qualification conditions.

**Implementation status:** [Current status](docs/STATUS.md) records locally verified capabilities, the exact candidate, unrun checks and one next task. Task reports own detailed evidence; roadmap/architecture describe intended scope. Development uses locked local tools and synthetic data. The owner-created [GitHub source repository](https://github.com/jpeterson92/Prosper) is connected; upload, merge and release remain separate actions. No investor application or released product exists.

## Start here

1. Start agent work with [AGENTS.md](AGENTS.md) and the compact [current status](docs/STATUS.md): current authority, active blockers and exactly one next task.
2. Follow the selected brief and [subsystem map](docs/engineering/AGENT_WORKFLOW.md#task-navigation) to the relevant code, tests, contracts and [decisions](docs/DECISIONS.md). Read broader plans and historical evidence only when the task depends on them.
3. Use the [development guide](docs/engineering/DEVELOPMENT.md) for locked setup and affected-check commands. The [agent workflow](docs/engineering/AGENT_WORKFLOW.md) describes planning, review and handoff.

For product orientation, the [project plan](docs/PROJECT_PLAN.md), [remaining roadmap](docs/REMAINING_ROADMAP.md) and [product specification](docs/product/SPEC.md) explain scope and sequencing. The [change log](CHANGELOG.md), [critical review](docs/reviews/2026-10-22-pre-implementation-review.md) and [ADR-0002](docs/architecture/decisions/0002-adopt-critical-review-actions.md) preserve adopted findings. These are navigation rather than a full reading list for every task.

The adopted first-product plan is a local application that imports tax lots and activity, reconciles them, compares a stock portfolio with a benchmark normally selected from a Vanguard ETF's full reported holdings, proposes an explainable harvest within explicit risk limits, and reconciles trades afterward. The investor controls account activity and execution. [ADR-0009](docs/architecture/decisions/0009-adopt-vanguard-benchmark-selection.md) adopts fund/date selection with explicit secondary file uploads; creation/redemption baskets are excluded. The current acquisition component is separate from future benchmark reconciliation, activation and browser controls.

The owner's [holdings-first input update](docs/architecture/decisions/0004-adopt-holdings-first-inputs.md) makes broker transaction history and cash optional. Planned conditional optimization retains an unverified-wash-sale warning and optional manual restrictions. Each future run reviews an editable additional-cash budget, including zero; risk covers the stock sleeve plus selected cash. These requirements are assigned to downstream tasks, not implemented optimizer controls.

## Project map

| Location | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Shared agent instructions and next-step sizing/authority entry point |
| [CLAUDE.md](CLAUDE.md) | Imports the shared agent instructions |
| [Product specification](docs/product/SPEC.md) | Users, workflow, exclusions, acceptance criteria |
| [Tax policy](docs/domain/TAX_POLICY.md) | Sourced rules, conservative product policies, unsupported cases |
| [Portfolio construction](docs/domain/PORTFOLIO_CONSTRUCTION.md) | Benchmark, risk, lot selection, objective, failure behavior |
| [Written reference portfolio](docs/domain/REFERENCE_PORTFOLIO.md) | Fully synthetic, hand-checkable direct-indexing problem |
| [Architecture](docs/architecture/ARCHITECTURE.md) | Adopted boundaries, data flow, technology choices and staged qualification |
| [Architecture alternatives](docs/architecture/TECHNOLOGY_TRADEOFFS.md) | Preserved rationale, pros/cons and alternatives to the adopted direction |
| [Data contracts](docs/architecture/DATA_CONTRACTS.md) | Adopted conceptual semantics; schemas still to implement and qualify |
| [Foundation specification](docs/engineering/FOUNDATION_SPEC.md) | Complete fictional import bundle, exact numeric contract and bounded first implementation brief |
| [Foundation child plan](docs/tasks/T003-T004-foundation-plan.md) | T003/T004 fit assessment, bounded serial tasks and expanded first ready development-baseline brief |
| [Brokerage feasibility](docs/research/BROKERAGES.md) | Fidelity selected as the initial test broker; field/workflow evidence and remaining qualification |
| [Fidelity lot collection](docs/guides/FIDELITY_IMPORT.md) | Retail per-position download/consolidation procedure, reusable assistant prompt and fictional stock test files |
| [Validation](docs/engineering/VALIDATION.md) | Acceptance scenarios, independent expectations, release evidence |
| [Agent workflow](docs/engineering/AGENT_WORKFLOW.md) | Task intake, authority, review, handoff, starter prompts |
| [Sources](docs/research/SOURCES.md) | Primary sources checked and their limits |
| [Development](docs/engineering/DEVELOPMENT.md) | Project-local Python setup/check/package commands, GitHub preparation and evidence limits |
| [Development dependencies](docs/engineering/DEVELOPMENT_DEPENDENCIES.md) | Exact tool/build versions, sources and installed license metadata |
| [src/prosper](src/prosper/README.md), [frontend](frontend/README.md), [apps](apps/README.md) | Shared Python core, synthetic browser review and reserved later application boundary |
| [tests](tests/README.md), [examples](examples/README.md), [scripts](scripts/README.md) | Implemented verification, synthetic examples and reproducible development tooling |

## Advance the project

Say **let's work on the next step** or **next**. The agent will inspect current progression, make a quick rough judgment about whether one task fits a GPT-6.1 Sol/high run including checks/review, and reuse its short execution sketch as the coding plan. A six-row assessment or separate coding-plan rewrite is not required. If it needs splitting, that run only writes bounded substages and stops; a later next-step request can execute one ready child. Use **next, planning only** to keep a run documentation-only. `/next` is a prompt alias if the client passes it through, not an installed native slash command.

[The protocol](docs/engineering/NEXT_STEP.md) defines the full behavior and stage-specific Codex conversation naming. Select your desired model/effort in the client; repository instructions do not change that setting. Configuring this workflow does not begin application implementation.

## Development status

Follow the [development guide](docs/engineering/DEVELOPMENT.md): run `scripts/dev.ps1 -Command bootstrap` for first Python setup, then use `-Command dev` for ordinary affected checks, adding an explicit `-TestPath` while selection state is cold/stale. Use `-Command docs` for documentation changes. Full Python/package/browser verification uses `scripts/checkpoint.ps1` at an explicitly authorized commit/sync checkpoint; an ordinary task does not trigger it. Dependencies live in ignored `.venv`; locked refreshes use `scripts/dev.ps1 -Command sync`. Tests cover the toolchain and synthetic import/recovery/API/browser components at the scopes recorded in STATUS and owning reports. They do not establish tax correctness, qualified broker accounting or investor acceptance.

Run `.venv/Scripts/python.exe -m prosper.local_api` for the synthetic loopback diagnostic process. It prints only its public `http://127.0.0.1:<port>` origin. The [runtime instructions](docs/engineering/DEVELOPMENT.md#protected-synthetic-loopback-runtime) describe session acquisition, shutdown and explicit synthetic-runtime configuration. Protected typed routes expose preview/current/commit/reject and OpenAPI over the import services. The [synthetic browser review](frontend/README.md) provides implemented preview/current and reviewed commit/reject controls; its guide owns build/launch commands. Investor installation, actionable harvesting and release remain unqualified. See [current status](docs/STATUS.md) for exact evidence.

This project assumes a standard local filesystem folder. Git/GitHub version authored source and lockfiles; environments, caches and generated synthetic artifacts are ignored and rebuildable. Keep real brokerage files, private portfolio databases/reports and credentials outside the repository. Git ignore rules do not remove already tracked files. See [SECURITY.md](SECURITY.md).

## Open-source direction

The intended software and reproducible synthetic examples will be open source. License selection, ownership details, public hosting, contribution terms, and redistribution rights for third-party data remain decisions to resolve before public distribution. See [CONTRIBUTING.md](CONTRIBUTING.md) and [decisions](docs/DECISIONS.md).

The tax material defines requirements for a future planning tool. It is not a validated tax computation or a conclusion about an individual investor's tax return.
