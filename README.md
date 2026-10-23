# Prosper

An open-source project in formation for investors who want to manage tax-loss harvesting in their own brokerage accounts. The initial product direction is **individual stocks and direct indexing, with file imports and trades placed by the investor**.

The project also serves as a current FinTech learning/interview showcase. The owner adopted the recommended architecture and staged learning approach on October 22, 2026. The [official project plan](docs/PROJECT_PLAN.md) and [adoption ADR](docs/architecture/decisions/0001-adopt-project-architecture.md) record the baseline; the [architecture comparison](docs/architecture/TECHNOLOGY_TRADEOFFS.md) preserves reasoning, alternatives and qualification conditions.

**Implementation status:** [Current status](docs/STATUS.md) records locally verified capabilities, the exact candidate, unrun checks and one next task. Task reports own detailed evidence; roadmap/architecture describe intended scope. Development uses locked local tools and synthetic data. The owner-created [GitHub source repository](https://github.com/jpeterson92/Prosper) is connected; upload, merge and release remain separate actions. No investor application or released product exists.

## Start here

1. Read the [project plan](docs/PROJECT_PLAN.md) for the adopted scope, milestones, and immediate next work.
2. Read the [product specification](docs/product/SPEC.md) for the investor workflow and initial acceptance criteria.
3. Review [decisions](docs/DECISIONS.md). Accepted architecture, conditional evaluations and genuinely open details are distinguished.
4. See [current status](docs/STATUS.md) before starting another session.
   The [change log](CHANGELOG.md) summarizes development changes and links to their evidence.
5. Read the [critical pre-implementation review](docs/reviews/2026-10-22-pre-implementation-review.md) for product/engineering findings and their adopted disposition in [ADR-0002](docs/architecture/decisions/0002-adopt-critical-review-actions.md).

The adopted first-product plan is a local application that imports tax lots and activity, reconciles them, compares a stock portfolio with a supplied benchmark, proposes an explainable harvest within explicit risk limits, and reconciles trades afterward. The investor controls account activity and execution.

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
| [Brokerage feasibility](docs/research/BROKERAGES.md) | Evidence and qualification procedure; no broker selected |
| [Validation](docs/engineering/VALIDATION.md) | Acceptance scenarios, independent expectations, release evidence |
| [Agent workflow](docs/engineering/AGENT_WORKFLOW.md) | Task intake, authority, review, handoff, starter prompts |
| [Sources](docs/research/SOURCES.md) | Primary sources checked and their limits |
| [Development](docs/engineering/DEVELOPMENT.md) | Project-local Python setup/check/package commands, GitHub preparation and evidence limits |
| [Development dependencies](docs/engineering/DEVELOPMENT_DEPENDENCIES.md) | Exact tool/build versions, sources and installed license metadata |
| [src/prosper](src/prosper/README.md), [apps](apps/README.md) | Minimal importable package and reserved application interface boundary |
| [tests](tests/README.md), [examples](examples/README.md), [scripts](scripts/README.md) | Future verification, synthetic examples, development tooling |

## Advance the project

Say **let's work on the next step** or **next**. The agent will inspect current progression and assess whether the next useful task fits one GPT-6.1 Sol/high run, including verification and review. If it needs splitting, that run only writes bounded substages and stops; a later next-step request can execute one ready child. Use **next, planning only** to keep a run documentation-only. `/next` is a prompt alias if the client passes it through, not an installed native slash command.

[The protocol](docs/engineering/NEXT_STEP.md) defines the full behavior and stage-specific Codex conversation naming. Select your desired model/effort in the client; repository instructions do not change that setting. Configuring this workflow does not begin application implementation.

## Development status

Follow the [development guide](docs/engineering/DEVELOPMENT.md): run `scripts/dev.ps1 -Command bootstrap` once, then `scripts/dev.ps1 -Command check` and `scripts/dev.ps1 -Command package`. Dependencies live in the ignored project-local `.venv`; future dependency refreshes use `scripts/dev.ps1 -Command sync`. These commands are locally verified developer operations. The 424-test suite exercises the toolchain, exact-value/synthetic allocation, strict parsing, checkpoint inspection, evidence/SQLite persistence, atomic imports and consistent backup/isolated restore; it does not establish tax correctness, qualified broker accounting or investor acceptance. There is no application run command or investor installation flow yet. See the [change log](CHANGELOG.md) and [current status](docs/STATUS.md) for the development boundary.

This project assumes a standard local filesystem folder. Git/GitHub version authored source and lockfiles; environments, caches and generated synthetic artifacts are ignored and rebuildable. Keep real brokerage files, private portfolio databases/reports and credentials outside the repository. Git ignore rules do not remove already tracked files. See [SECURITY.md](SECURITY.md).

## Open-source direction

The intended software and reproducible synthetic examples will be open source. License selection, ownership details, public hosting, contribution terms, and redistribution rights for third-party data remain decisions to resolve before public distribution. See [CONTRIBUTING.md](CONTRIBUTING.md) and [decisions](docs/DECISIONS.md).

The tax material defines requirements for a future planning tool. It is not a validated tax computation or a conclusion about an individual investor's tax return.
