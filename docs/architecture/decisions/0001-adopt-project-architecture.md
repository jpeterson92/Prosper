# ADR-0001: Adopt the local FinTech architecture and staged showcase plan

Date: October 22, 2026. Status: **Accepted**. Approver: project owner, in this chat.

## Decision and authorization evidence

The owner reviewed the architecture comparison and stated: "I agree with all of your suggestions. Can you please incorporate them into the official project plan?"

This adopts the recommended project baseline and the conditional/staged learning approach. It does not select mutually exclusive alternatives, authorize implementation, validate tax/risk calculations or authorize account access, real-data disclosure, publication or deployment.

## Context

Prosper is intended as open-source software for self-directed tax-loss harvesting of individual-stock/direct-indexing portfolios. File imports and investor-placed brokerage trades are the confirmed starting workflow. The project should also demonstrate current financial technology, quantitative judgment, product design and effective use of coding agents.

The [technology review](../TECHNOLOGY_TRADEOFFS.md) compares thirteen choices. The [decision register](../../DECISIONS.md) records accepted choices and details still open.

## Adopted baseline

Subsequent refinement: [ADR-0007](0007-adopt-enhanced-dcc-nl-industry-risk.md) selects enhanced DCC-NL with sector/industry risk for v1, superseding the initial generic shrinkage reference direction below. Detailed algorithm/settings qualification and G1-G3 remain required; the original adoption record is historical context.

- Local single-user modular application with a deterministic typed Python core; one authoritative state store.
- SQLite for financial/application state with exact-value encoding, transactional import/reconciliation and tested recovery. Real data resides outside the source repository. The original synced-folder development restrictions are superseded by [ADR-0003](0003-adopt-standard-local-development.md); standard local development artifacts are permitted inside ignored checkout folders.
- React/TypeScript/Vite investor UI; FastAPI/Pydantic boundary; OpenAPI-generated TypeScript client; exact book values cross JSON as validated decimal strings.
- Polars/Parquet analytical pipeline; add DuckDB only for a concrete analytical query, as rebuildable derived state.
- CVXPY/Clarabel for continuous reference/relaxation models; separately qualified whole-share candidate construction and independent feasibility validation.
- Reviewed shrinkage covariance reference methodology, initially evaluating Ledoit-Wolf; marimo for reproducible model/solver comparisons.
- Versioned relational evidence and explicit lifecycle transitions preserving effective and recorded time.
- uv/Ruff, strict type checking, pytest/Hypothesis, Playwright and privacy-preserving local diagnostics. Add OpenTelemetry when a real multi-stage diagnostic use warrants it.
- Existing long-only USD common-stock sleeve, U.S. federal taxable scope, one traded account plus household monitoring, whole-share proposed orders and zero positive-gain budget. Preserve fractional holdings and explicit unsupported cases.
- Conservative known-conflict exclusion, eligible gross-loss objective under hard limits, source-backed requirements and independent tax/risk review plus paper acceptance before financial-use pilot.

## Adopted conditional and staged work

- Keep a roughly 20% effort budget for explicit learning experiments; evaluate one exploratory track at a time against written criteria.
- Evaluate Tauri 2 with a Python sidecar after the end-to-end workflow is accepted. Selection as a release installer depends on packaging, security, recovery and supported-OS evidence.
- Keep a read-only AI explainer as an optional synthetic-first experiment. It may explain verified results but cannot write authoritative financial state, approve plans or trade.
- PGlite/Turso storage experiments, JAX research and a targeted Rust extension remain alternatives/experiments selected only for a concrete question or measured need.
- Prepare a synthetic-only interview showcase after the core workflow exists. Any publication, live backend, cost or real-data use still needs its own scope/authority.

## Alternatives considered

Hosted PostgreSQL, browser-only WASM, microservices/Temporal, Rust or TypeScript cores, Julia/JuMP, pandas/SQL-first analytics, Streamlit/SvelteKit/Next.js, Django/tRPC/GraphQL, full event sourcing, Electron and alternative solvers remain documented comparison options. They are not co-adopted dependencies. A stronger fit discovered through evidence can supersede the relevant decision.

## Consequences

The project has a wider engineering surface than a Python-only local prototype. UI/API contract checks, numerical qualification, temporal replay and research reproducibility become planned work. The original 12-22-week estimate is superseded by the planning envelope in the [official project plan](../../PROJECT_PLAN.md), still subject to re-estimation after early implementation evidence.

Agents should use these decisions without repeatedly asking for architecture approval. Exact versions, broker/data providers, software license, investor-specific thresholds, discrete solver, type checker and the first optional experiment remain open. A dependency is qualified only after applicable compatibility, licensing and acceptance checks.

## Acceptance evidence and reconsideration

Observed: owner approval and documentation adoption. Unrun: all application, numeric round-trip, solver, UI, packaging, performance and user-acceptance checks.

Reconsider a choice when a qualification fails, a materially better alternative is demonstrated, requirements change, maintenance/distribution costs become unacceptable or a legal/data-rights constraint changes scope. Record the evidence and supersede the decision explicitly rather than silently switching the stack.
