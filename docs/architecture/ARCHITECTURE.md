# Adopted architecture

Current architecture, October 25, 2026. This page incorporates the retained architecture decisions directly. [Data contracts](DATA_CONTRACTS.md), [numerics](../engineering/ADVISORY_NUMERICS.md), [domain contracts](../engineering/AGENT_WORKFLOW.md#task-navigation) and the selected task supply detail. [STATUS](../STATUS.md) distinguishes current code from required changes. No ADR chain or obsolete foundation plan is required intake.

## Shape and boundaries

Use one local single-user modular application. A typed deterministic Python core owns financial calculations; no LLM decides basis, tax classification, wash eligibility, limits or quantities. The local service exposes the same core to the React UI, tests and research. One current authoritative SQLite store owns selected imports, revisions, settings and saved outputs; retained external inputs have explicit ownership and recovery. Derived caches are rebuildable and do not become a second financial authority.

| Layer | Adopted choice and limit |
| --- | --- |
| Core/service | Python; explicit domain checks, scoped failures and shared calculation code |
| State | SQLite transactions; imported quantity/basis/entered exact amounts as decimal TEXT, finite derived estimates; current-format backup/restore |
| UI/API | React/TypeScript/Vite, FastAPI/Pydantic and generated OpenAPI TypeScript client; intentional contract generation and consumer checks |
| Tables | Polars first for ingestion/alignment/joins/filters/grouping/coverage; validate cardinality/completeness/order. Ordinary Python is appropriate for simple boundary work |
| Analytical files | Parquet when a consumer actually needs persistent analytical files; no new storage subsystem just to adopt a format |
| Numerics | Qualified NumPy/SciPy for the maintained selected risk core; Float64 with calculation-specific tolerances and small decimal final checks |
| Candidate/reference | One bounded search and separate final validation; CVXPY/Clarabel references only for a concrete numerical question, not an MVP dependency |
| Verification | uv, Ruff, strict mypy, pytest/Hypothesis, Playwright; scoped ordinary checks and full explicit checkpoint/CI |
| Research | Focused marimo/reference questions using the shared core; no second production model authority |
| Later options | DuckDB only for a concrete derived research query; Tauri/Python-sidecar evaluation after workflow acceptance; optional accelerators/AI/showcase only for bounded demonstrated needs |

Exact runtime/development pins and their evidence live in `pyproject.toml`, `uv.lock` and [dependency inventory](../engineering/DEVELOPMENT_DEPENDENCIES.md); compared alternatives are not selected dependencies. Material license/cost/distribution choices remain owner decisions.

## State, calculations and refresh

The current advisory workflow is import/preview -> select snapshot/settings -> estimate -> independently validate candidate -> save/export -> refreshed import. Original source copies and material facts are retained without per-field token proofs, universal rational transport or intermediate hash/registry chains. Preserve explicit unknowns/exclusions and data as-of versus import time. Saved current-format output is readable without rerunning current code.

Use short transactions for snapshot replacement and result publication. Bind mutations to durable command identities and relevant input/settings revisions; an identical retry returns its original outcome, while changed-payload reuse is rejected. A failed replacement preserves selected work. A late result cannot publish over newer inputs/settings; cancellation/timeout cannot become a successful current result. Begin with one bounded calculation/writer policy. Do not add reservations, event sourcing, multi-service queues or execution commitments.

[Market inputs](../domain/BENCHMARK_INPUTS.md) define persistent compatible history reuse, requested/manual missing-window refresh and separate current quotes/taxonomy. Save only the data actually used by runs plus chosen reusable cache. Refresh must not rewrite saved output. Background scheduling, timer/catch-up/pending-dispatch lifecycle and broad supporting-object proof registries are outside v1.

## Security and local operation

Bind to loopback; keep session authorization, trusted host/origin protections and explicit development-origin allowances. Reject foreign/missing sessions and unsafe paths; protect the runtime and SQLite sidecars from aliases/links/restore-incomplete state. HTTP clients cannot select arbitrary storage paths. Imported files/pages are data, never commands. Bound file/row/request work and make errors safe; do not print portfolio payloads, credentials or arbitrary OS details in normal logs.

Synthetic fixtures/logs/screenshots/examples are the development default. Private portfolio data and secrets stay outside source control and require explicit data/destination authorization before AI access. Diagnostics remain local/private with IDs/counts; add OpenTelemetry only for an actual pipeline diagnostic need, with no default remote export. Source-control backup is separate from investor-data recovery.

## Development and recovery

Use a normal local checkout, project `.venv` editable installation, locked refreshes, normal caches, UTF-8/LF authored text and ignored `.local` artifacts. No Google Drive/external-runtime workaround or copied environment. [DEVELOPMENT](../engineering/DEVELOPMENT.md) owns reproducible commands; the installed private runtime is separate from source/dependencies.

Provide one consistent current SQLite backup plus required external input files, clean-destination restore, explicit cache rebuild/unavailable behavior and honest interruption/corruption/unsupported-format outcomes. Preserve transactional current user work. No source-code hash defines compatibility. Prosper is unreleased: internal APIs/schemas/readers/backups can be replaced directly, affected callers updated and obsolete compatibility-only paths removed. A scoped fresh development runtime/reimport can replace migration. Never silently wipe/repair state or reinterpret unsupported data as an empty portfolio.

## Qualification and delivery

The first investor target is Windows x64 with supported versions/browser/dependencies and actual install/launch/restore checks. Start with the simplest qualified local browser launcher. Tauri is a later evaluation, not a prerequisite rewrite. Public distribution needs owner-selected license/data/dependency rights, legal/service scope, privacy/support details, independent review where applicable and explicit publication authority. No local check or source commit grants those permissions.

Accepted methodology and economic/tax limits remain in the direct domain contracts. Independent final candidate checks, tax/model review and current-format recovery remain material controls even without backward compatibility. Implemented, locally verified, independently reviewed, paper accepted, financially authorized and released remain distinct states under [VALIDATION](../engineering/VALIDATION.md).
