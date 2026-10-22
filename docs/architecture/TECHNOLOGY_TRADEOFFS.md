# Architecture choices, alternatives, and showcase direction

Updated October 22, 2026. The owner has accepted the recommended baseline and staged learning approach; [ADR-0001](decisions/0001-adopt-project-architecture.md) and the [decision register](../DECISIONS.md) record adoption. This document preserves the reasoning and compared alternatives. Conditional recommendations remain conditional; compared alternatives are not all selected. No implementation is authorized and no packages, prototypes, performance measurements or integrations were run. Capability statements reflect the primary documentation reviewed; judgments about fit/interview value are not hiring-market measurements.

## The revised objective

The owner wants both a useful investor product and a current FinTech learning/showcase project. The first architecture proposal emphasized financial reliability, local privacy and delivery simplicity. It left the interface, analytical tooling and numerical stack largely unspecified. That was appropriate for the product-only objective but understated the value of deliberate technology exploration and an impressive, inspectable demonstration.

Evaluate choices on five dimensions: correctness/recoverability, investor experience/privacy, relevant learning, demonstrable technical depth, and implementation/maintenance cost. There is no universally best technology across these dimensions. A mature component can enable a more advanced system; novelty alone is not evidence of product value.

The adopted direction is a **modern local application with a Python financial core, a typed React interface, explicit API contracts, and a reproducible quantitative research layer**. Keep authoritative financial state conservative. Concentrate newer technology in analytics, research, interface, packaging and an optional bounded AI experience.

## Adopted stack and staged evaluations at a glance

| Concern | Adopted direction / condition | Why |
| --- | --- | --- |
| Deployment | Local first; optional synthetic-only hosted demonstration later | Preserve investor privacy while making interviews easy to demonstrate |
| Application structure | Modular application; one backend initially, explicit domain boundaries | Preserve simplicity; permit a separate local compute worker when measurement justifies it |
| Financial language | Typed Python; Rust extension only for a measured hotspot | Keep Python, make the selective native-code path explicit |
| Authoritative state | SQLite, exact-value encoding, versioned relational history | Keep SQLite with stronger numeric/provenance requirements |
| Analytics | Polars and immutable Parquet snapshots when tabular/history work begins; DuckDB at the research/query milestone | Add a modern analytical path without creating two authorities |
| Investor UI | React + TypeScript + Vite; routing only as needed | Upgrade from a possible Python-only interface |
| API/contracts | FastAPI + Pydantic, OpenAPI-generated TypeScript client | Make the Python/TypeScript boundary explicit and testable |
| Optimization | CVXPY + Clarabel for continuous reference/relaxation; independently validated whole-share candidate construction | Name a qualification candidate; discrete solver remains an evidence-based choice |
| Risk/research | Reviewed shrinkage covariance baseline; comparative factor/robust experiments in marimo | Add reproducible research and model comparison |
| Execution/history | Explicit lifecycle and versioned decisions/evidence with effective and recorded time | Strengthen replay and explainability without full event sourcing |
| Packaging | Local browser first, evaluate Tauri 2 + Python sidecar after end-to-end workflow | Add a contemporary desktop option without forcing a Rust core |
| AI | Optional later read-only explanation of verified results, explicit data controls | Add a bounded learning track, not AI-generated financial truth |
| Engineering | uv, Ruff, a qualified type checker, pytest/Hypothesis, Playwright; local metadata-only instrumentation | Make agent-produced changes reproducible and observable |

Exact releases must be pinned only after compatibility, licensing, supported OS and packaging checks during authorized implementation. Choosing the newest stable compatible release is different from choosing prereleases everywhere.

## 1. Local first versus hosted versus browser-only

**Original reasoning:** one investor already has account access, sensitive data should stay under their control, and no hosted operations are needed to import files and review a portfolio.

| Approach | Advantages | Costs and limitations | Best fit here |
| --- | --- | --- | --- |
| Local Python application with browser UI | Direct use of the numerical ecosystem; private files stay local by design; offline review after import | Installation, local process lifecycle, backups and updates must be engineered; cannot monitor while closed | Recommended investor product |
| Hosted web application with PostgreSQL | Easy access, centralized updates, reliable scheduled processing, natural multi-user direction | Identity/access isolation, portfolio uploads, secrets, ongoing operations and cost become product responsibilities | Reconsider for a deliberate hosted offering; not required by current scope |
| Browser-only application using WASM | No native install; very accessible demonstration; computation can remain on-device | Python/solver/WASM compatibility, large input performance, browser persistence/recovery and tab lifecycle need qualification | A coherent alternate product architecture or isolated research spike, not an automatic optimization |

**Revised choice:** local investor edition plus, later, a separately scoped synthetic-only showcase. A static showcase can replay precomputed signed/versioned research results without accepting real uploads. If live optimization is added to a hosted demo, it needs an explicitly authorized backend and operating budget; a Python service does not become browser-only by embedding a database in WASM.

PGlite demonstrates an interesting browser/Node Postgres option, with browser persistence through IndexedDB. It is a JavaScript/WASM component and is not a drop-in Python SQLite replacement. [PGlite documentation](https://pglite.dev/docs/about).

**Change trigger:** hosted monitoring, multi-device use or advisor workflows become a real requirement, or browser-native computation becomes the primary learning objective.

## 2. Modular application versus microservices and workflow infrastructure

**Original reasoning:** the initial user count, scope and workload do not justify independently deployed tax, risk, import and optimization services. Separate modules can retain clear responsibilities while sharing one transaction boundary.

**Recommended:** a modular backend with explicit application services. The React frontend is a separate build artifact, not a separate financial engine. In development there may be UI and API processes; a release can serve the static UI locally. A compute worker can be added to keep expensive optimization off the request loop. Do not promise a literal one-process architecture once desktop packaging or worker isolation is introduced.

**Alternatives:** microservices offer independent scaling/deployment and fault isolation when teams/workloads warrant them, but introduce service versioning, networking and distributed consistency. A task queue helps when multiple independent jobs must run asynchronously, but adds broker/worker operations. Temporal offers durable workflow execution and is compelling for later unattended brokerage/reconciliation workflows, but introduces a workflow service and additional deterministic replay/versioning concerns. Its durability does not make an external trade side effect exactly once. [Temporal workflow execution](https://docs.temporal.io/workflow-execution).

**Showcase value:** demonstrate clean module boundaries, cancellation/recovery, idempotent imports and job-state transitions. Those can be inspected without running a cluster. Add distributed orchestration when there is an external workflow to justify it.

**Change trigger:** independently scaling workloads, multiple backend workers, long-lived unattended integrations or a real multi-user service.

## 3. Python versus Rust, TypeScript and Julia

**Original reasoning:** this problem combines finance-domain logic, arrays, statistics and constrained optimization. Python lets a reviewer read the rules and research code together and offers a direct integration path to numerical libraries.

| Approach | Advantages | Costs and limitations |
| --- | --- | --- |
| Typed Python core | Readable domain rules; direct quantitative ecosystem; approachable contributions and agent verification | Types need enforcement; CPU-bound Python loops can require optimization; packaging numerical dependencies takes work |
| Rust core | Strong compile-time guarantees, explicit memory/concurrency control, native library/binary path | More specialized numerical/modeling integration work; another learning curve; memory safety does not validate tax rules |
| TypeScript end to end | Shared frontend/backend contracts and one main language; attractive browser-oriented design | Scientific/solver integration may still require Python, WASM or external tools; JavaScript Number is not exact money arithmetic |
| Julia + JuMP | Strong mathematical modeling and optimization research direction | Adds another runtime and integration/distribution surface for the investor application |

**Revised choice:** Python plus TypeScript at the interface. Rust is a targeted optional extension after profiling, using PyO3 if appropriate; choosing Rust is not necessary to benefit from Rust-built libraries. Julia is a serious alternative if optimization research becomes the dominant project outcome. [PyO3](https://pyo3.rs/), [JuMP](https://jump.dev/JuMP.jl/stable/).

**Learning artifact:** profile a real import/risk workload before and after one targeted optimization, and document the correctness equivalence and packaging cost. Do not promise a speedup before measurement.

## 4. SQLite versus PostgreSQL, DuckDB, PGlite and Turso

**Original reasoning:** the first product needs transactional local state for imports, lots, plan approvals, fills and reconciliation. It does not initially need a shared database server. SQLite explicitly targets application/device-local storage, while server databases prioritize shared centralized access. [SQLite usage guidance](https://sqlite.org/whentouse.html).

| Candidate | Strengths | Tradeoffs for Prosper | Recommendation |
| --- | --- | --- | --- |
| SQLite | Embedded deployment, transactions, simple local operational model, broad tooling | Limited write concurrency; exact decimal encoding needs deliberate design; local file access/encryption/backups remain our responsibility | Recommended authoritative store initially |
| PostgreSQL | Shared concurrent service, exact NUMERIC, rich constraints/query capabilities, straightforward hosted direction | Requires a managed or local server, credentials, upgrades and backup operations; local Docker is an end-user prerequisite unless hidden by an installer | Preferred alternative if hosted/multi-user becomes primary |
| DuckDB | Analytical SQL and direct columnar/file workflows; attractive for large research joins/aggregations | Analytical role differs from application state; a second store creates consistency questions; embedded concurrency and client/server modes must be understood | Add for reproducible research queries when useful, not as a novelty-driven swap |
| PGlite | Postgres in WASM, JavaScript integration, browser/Node deployment and local persistence | Moves storage ownership toward JS/WASM; Python integration, durability, extensions, upgrades and recovery need specific tests | Best frontier alternative for a browser-native architecture spike |
| Turso Database / libSQL ecosystem | Embedded and sync-oriented options; contemporary local/remote data experiments | Embedded engine, libSQL and cloud products are distinct; feature availability, numeric behavior, bindings, licensing and sync semantics need release-specific qualification | Optional bounded alternative-store experiment; no automatic cloud sync of portfolios |

PostgreSQL documents exact NUMERIC support. SQLite's REAL values use approximate binary floating point. A column named DECIMAL or an ORM Decimal object is not by itself an exact-storage guarantee in SQLite. Use explicitly scaled integers within checked bounds or canonical decimal text with validated conversions; define precision/rounding per field and test round trips. Do not silently SUM decimal strings through a floating-point cast. [PostgreSQL numeric types](https://www.postgresql.org/docs/current/datatype-numeric.html), [SQLite numeric representation](https://sqlite.org/floatingpoint.html).

DuckDB's current documentation distinguishes embedded single-writer-process operation from newer multi-process client/server options. It would be outdated to state that DuckDB simply cannot support multi-process writes. Our recommendation is about its workload role and operating model. [DuckDB rationale](https://duckdb.org/why_duckdb), [current concurrency documentation](https://duckdb.org/docs/stable/connect/concurrency).

Turso's documentation separates the embedded database from Cloud and sync features. Do not infer that every advertised feature is available in every runtime or that SQLite compatibility proves all our acceptance cases. [Turso overview](https://docs.turso.tech/introduction).

**Revised choice:** keep SQLite authoritative; use Parquet and, when justified, DuckDB for analytical snapshots. This is a meaningful heterogeneous-data design only if the analytics are rebuildable and cannot modify authoritative basis/approvals. Do not maintain SQLite and PostgreSQL authorities in parallel.

**Showcase artifact:** compare SQLite/PostgreSQL or one newer embedded candidate on exact-value round trips, transactional rollback, corrections, import idempotency and restore. Show measured results and the choice they support. A repository/store interface permits an experiment; it does not promise zero-effort database portability.

## 5. Polars/Parquet versus pandas versus SQL-first analytics

**Original reasoning:** no dataframe choice was made because the first portfolio is small. The showcase objective gives value to learning a current analytical workflow as long as it remains proportionate.

**Recommended:** Polars for typed tabular ingestion/transforms and historical analytics; immutable Parquet for accepted analytical input snapshots. Preserve the raw source and canonical financial records separately. Use lazy scans/projection/filtering where they simplify work. Convert intentionally to NumPy arrays for covariance/solver calculations. Polars' lazy API supports deferred/optimized execution, but performance must be measured on our workload. [Polars lazy API](https://docs.pola.rs/user-guide/concepts/lazy-api/).

**Alternatives:** pandas offers familiar research interoperability and can be the easiest route for an existing workflow, but does not teach the same expression/lazy-query model. DuckDB-first SQL is excellent when analytical joins and SQL reproducibility dominate; it can replace portions of dataframe code rather than duplicate them. Arrow is a useful interchange format where actual boundaries need it. Spark/Ray/cloud warehouses introduce distributed operational costs without a demonstrated requirement at our proposed scale.

**Tradeoff:** adopting Polars and DuckDB simultaneously for the first small import is unnecessary. Introduce Polars at the tabular milestone; add DuckDB when SQL research queries provide a concrete benefit. Decimal schemas, CSV inference, missing values, integer overflow and library-to-library casts require explicit tests. Financial calculations do not become correct merely because a dataframe has a schema.

**Showcase artifact:** a reproducible import/history query with inspectable plans, exact record reconciliation and memory/runtime measurements, using permitted synthetic data.

## 6. React/TypeScript versus Streamlit, SvelteKit and Next.js

**Original reasoning:** a Python-only interface could deliver an internal alpha rapidly and avoid a second language. It was left open rather than selected.

**Revised recommendation:** React + TypeScript + Vite for the main investor interface. It supports a deliberate lot-review table, linked risk/exposure views, what-if controls, plan comparisons and explicit approval/reconciliation states. The cost is real: frontend state, API integration, accessibility, component tests and build tooling must be maintained.

| Alternative | Advantages | Why not the revised default |
| --- | --- | --- |
| Streamlit | Very quick Python data applications; useful internal diagnostics | More framework-driven UI/session model; less control for the intended multi-step investor workflow and frontend learning goals |
| Svelte/SvelteKit | Concise component model and modern application framework; attractive if learning newer UI patterns is a primary objective | Another valid choice, but no identified product advantage sufficient to favor it over the proposed React direction |
| Next.js | Full React framework with routing/rendering/server capabilities; credible for hosted web products | Many capabilities are unnecessary for a local Python-backed application; static export is possible, so it is not inherently cloud-only |
| React Router framework | React-recommended framework direction, capable of client/static operation | Evaluate if routing/data-loading needs warrant it; avoid accumulating both a framework backend and FastAPI business logic |

React generally recommends frameworks, while also documenting constrained/from-scratch paths. A Vite SPA here is a deliberate local/Python-backed choice, not a claim that framework-based React needs a server. [React app guidance](https://react.dev/learn/creating-a-react-app), [Next.js static exports](https://nextjs.org/docs/app/guides/static-exports), [SvelteKit](https://svelte.dev/docs/kit/introduction), [Streamlit](https://docs.streamlit.io/).

**Showcase artifact:** a user can move a risk budget, compare valid plans, inspect why a lot was blocked and follow actual-versus-planned execution. Meaningful interaction and understandable evidence will carry more of the demo than the framework name.

## 7. FastAPI/contracts versus Django, tRPC and GraphQL

**Original reasoning:** the UI was supposed to call shared application services. A polished TypeScript frontend now makes the cross-language boundary a first-class design problem.

**Recommended:** FastAPI with Pydantic boundary models, explicit domain validation and an OpenAPI-generated TypeScript client. Use decimal strings for book-money/quantity JSON fields and separate display/risk floats. Reject unexpected fields and unsafe coercions where appropriate; test JSON and Python validation paths because strict mode has type/input-specific behavior. A generated client prevents some contract drift but cannot prove domain semantics or preserve decimals automatically. [FastAPI standards](https://fastapi.tiangolo.com/features/), [client generation](https://fastapi.tiangolo.com/advanced/generate-clients/), [Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/).

**Alternatives:** Django plus an API layer offers integrated administration/authentication/ORM conventions, attractive for an account-based hosted service, but adds framework surface the local financial core does not currently need. TypeScript tRPC is compelling for a TypeScript backend/frontend but does not remove a Python numerical boundary. GraphQL can support many clients with varied query needs, but introduces another schema/resolver/security layer for a small known set of workflows. Direct native IPC can avoid HTTP in a desktop-only edition, but reduces reuse by browser demos/other clients.

**Tradeoff:** local HTTP still needs origin/session protection and loopback binding. CPU-heavy solvers must not block request handling. Typed clients and runtime validators complement independent financial checks; they do not replace them.

## 8. Optimization: CVXPY/Clarabel, SCIP, HiGHS, JuMP and commercial solvers

**Original reasoning:** solver selection was intentionally open because our problem contains continuous risk and discrete lots/orders. We must establish the formulation before selecting a solver by name.

**Recommended candidate:** CVXPY with Clarabel for transparent continuous reference/relaxation problems and loss/risk frontier exploration. Whole shares and order counts require separate discrete candidate generation or a qualified mixed-integer formulation. Clarabel does not solve the full mixed-integer problem. Every rounded/repaired result must pass an independent exact-lot/cash/risk validator. [CVXPY solver capabilities](https://www.cvxpy.org/tutorial/solvers/index.html), [Clarabel](https://clarabel.org/stable/).

| Alternative | Strength | Limitation / use |
| --- | --- | --- |
| Transparent deterministic heuristic | Inspectable, controllable runtime, useful first baseline | Can miss better feasible plans; never label globally optimal without evidence |
| SCIP | Open-source mixed-integer nonlinear capability; serious candidate for discrete allocation with risk constraints | Modeling/backend compatibility, packaging and runtime at our scale need qualification |
| HiGHS | Strong open-source LP/MIP/QP option | Do not infer mixed-integer quadratic/conic support merely from separate MIP and QP features; verify the exact formulation/version |
| Julia/JuMP | Expressive mathematical modeling across solver backends | Additional runtime integration if the main product remains Python |
| Gurobi/MOSEK and other commercial solvers | Serious comparison candidates for demanding discrete/conic models | Licensing/distribution constraints; not required for an open-source user's default installation |

A hard tracking-error cap naturally produces a quadratic/conic constraint. With integer shares or order indicators, this is not just a linear MIP. Formulation compatibility is an acceptance criterion. [CVXPY mixed-integer guidance](https://www.cvxpy.org/tutorial/constraints/index.html), [SCIP](https://www.scipopt.org/), [HiGHS](https://highs.dev/), [JuMP](https://jump.dev/JuMP.jl/stable/).

**Showcase artifact:** compare a transparent heuristic, tiny exhaustive enumeration, continuous bounds and one qualified discrete solver on the same frozen input. Show objective/feasibility, compute time, gaps where available and failure behavior. That is a defensible quantitative engineering story.

## 9. Risk methodology and research: shrinkage, factors, JAX and marimo

**Original reasoning:** risk control needs a specified estimator, data and validation before it can meaningfully constrain trades. Choosing a fashionable computation library cannot resolve estimation uncertainty.

**Recommended candidate baseline:** documented shrinkage covariance, such as Ledoit-Wolf, with as-of aligned adjusted returns, PSD checks, missing-history policy, annualization and independent exposure calculations. This is an established baseline suitable for comparison, not a claim of superior out-of-sample investment performance. [scikit-learn covariance estimation](https://scikit-learn.org/stable/modules/covariance.html).

**Alternatives:** factor models can offer interpretable exposures and structured covariance but require factor definitions, histories and residual validation, with potential data rights costs. Commercial risk models may reduce development effort but can make redistribution/demo reproducibility harder. Robust optimization and bootstrap/stress scenarios can explore estimation uncertainty, but introduce additional assumptions and conservative tradeoffs. JAX is compelling for differentiable sensitivity analysis or many repeated numerical scenarios; it adds compilation/dtype/shape considerations and should remain outside exact-money accounting. [JAX numerical workflow](https://docs.jax.dev/en/latest/notebooks/thinking_in_jax.html).

**Research interface:** recommend marimo notebooks importing the same core functions for reproducible experiments and interactive explanations. Its reactive execution and Python-file representation are attractive for reviewable research. Jupyter remains a strong alternative where existing workflows matter more; notebook state still needs disciplined execution. Neither notebook should become an independent tax engine. [marimo documentation](https://docs.marimo.io/).

**Showcase artifact:** a model-comparison notebook with frozen synthetic/permitted data, frontier plots, exposure attribution, sensitivity to the estimation window and honest model limitations. Distinguish estimated TE from observed future tracking outcomes.

## 10. History and audit: versioned relational records versus full event sourcing

**Original reasoning:** imports, approvals, corrections and executions need reproducible versions. Full event sourcing is one way to achieve that, but it is not a prerequisite.

**Recommended:** normalized current state plus versioned/superseding evidence and explicit lifecycle transitions. Preserve effective time (when a trade or correction applies) and recorded time (when the application learned it). A plan refers to exact input/rule/model versions, and the application can reproduce what it knew at approval. This is a bounded use of two-time semantics, not an assertion that the whole database supports every possible bitemporal query.

**Alternatives:** mutable CRUD is simpler but loses explanation unless revisions are added. Full event sourcing/CQRS supports rich replay and separate projections but imposes event-schema evolution, correction and rebuild complexity. Blockchain is unnecessary when there is no multi-party trust problem; local hashes detect certain changes but are not a tamper-proof legal record.

**Tradeoff:** immutable history needs retention/export/deletion policies and private storage. Financial records and diagnostic logs have different payload and privacy requirements.

**Showcase artifact:** approve a plan, import a backdated correction, then show the original decision and the corrected result without overwriting history. Pair this with source-linked reason codes and a reproducible input bundle.

## 11. Browser launcher versus Tauri versus Electron

**Original reasoning:** a browser UI avoids early native packaging and lets the workflow stabilize. A typical investor still needs a supported install/start/update path.

**Revised recommendation:** launch locally first; evaluate Tauri 2 with a packaged Python sidecar once the end-to-end workflow exists. This adds contemporary desktop packaging, scoped native capabilities and a polished launch experience. It does not eliminate Python or guarantee a small final installer: numerical libraries and solver binaries still ship. [Tauri sidecar documentation](https://v2.tauri.app/develop/sidecar/).

**Alternatives:** Electron has a consistent bundled Chromium/Node environment and broad desktop tooling, with a runtime/distribution footprint that may be larger for comparable UI assets; actual size/performance must be measured for our bundle. A simple Python launcher/browser path is the least complex first release, but local server shutdown, browser-origin boundaries and updater UX require care. A fully native Rust/Tauri core removes the Python sidecar but substantially changes the quantitative stack. [Electron process model](https://www.electronjs.org/docs/latest/tutorial/process-model).

**Qualification:** one-click launch, file selection, local origin/session controls, signed update policy, shutdown/restart, backup/restore and supported OS packaging. Tauri Rust glue is a separate role from Rust financial logic.

## 12. Runtime AI and broker integrations

**Original reasoning:** deterministic correctness and manual brokerage execution do not require runtime AI. Your learning goal supports an optional AI experience with a tightly defined purpose.

**Recommended later experiment:** a read-only assistant that answers questions about a specific verified plan and its evidence: why a lot was blocked, which constraint bound, and how candidates differ. Retrieve approved rule documentation and tool-returned facts; cite plan/lot/reason IDs. Any requested setting/quantity change becomes an unapproved structured proposal that must run through deterministic analysis and validation again. The assistant cannot write authoritative basis, approve a plan or place trades.

**Alternatives:** deterministic templates are cheapest and most predictable; hosted-model tool calling can offer richer explanations but introduces disclosure/cost/evaluation needs; local models can reduce external disclosure but add hardware/quality/distribution requirements. A multi-agent autonomous manager increases failure surface without being necessary for this workflow. MCP is an interoperability option for exposing read-only tools to external assistants, not a correctness boundary or required internal API. [MCP architecture](https://modelcontextprotocol.io/docs/learn/architecture).

Keep synthetic-only AI demos first. Real portfolio disclosure needs explicit authorization for the data and model destination. Evaluate unsupported claims, arithmetic fidelity, source faithfulness, prompt injection, refusal on unknown data and attempted unauthorized changes. A fluent explanation is not proof that its numerical assertions match the plan.

Broker imports/manual execution stay confirmed. Read-only API connectivity can add OAuth/token lifecycle, schema and idempotency experience later, but needs qualified tax-lot evidence. Automated trading is a separate product change. A showcase can demonstrate these boundaries without handling live credentials or placing orders.

## 13. Development, verification and observability

**Original reasoning:** no toolchain should be installed before an authorized implementation slice. A concrete proposed toolchain now helps evaluate the learning and verification story.

**Recommended:** uv for Python environments/locking, Ruff for lint/format, a qualified strict type checker, pytest plus Hypothesis for domain/invariant/stateful tests, and Playwright for the investor workflow. Pyright or mypy are sensible baseline candidates; evaluate newer ty against real Pydantic/NumPy/solver annotations before making it the sole gate. Check actual package stubs/support rather than equating type-checker speed with correctness. [uv](https://docs.astral.sh/uv/), [Ruff](https://docs.astral.sh/ruff/), [ty](https://docs.astral.sh/ty/), [Hypothesis stateful tests](https://hypothesis.readthedocs.io/en/latest/stateful.html), [Playwright](https://playwright.dev/docs/intro).

**Alternatives:** conventional pip/venv plus separate tooling remains understandable; Conda can be useful for specific scientific binary requirements; all-in-one orchestration/build systems can add coordination at a larger repository scale. Choose the smallest reproducible setup for the actual dependencies. A Python lockfile and frontend lockfile need CI consistency; neither locks external tax interpretations or market data.

**Observability:** begin with structured local metadata and identifiers. Introduce OpenTelemetry traces at the first multi-stage analysis milestone if they improve diagnosis. Trace imports, screening, risk, solving and validation with timings/model/input IDs, not portfolio payloads. No automatic remote exporter. Golden cases, differential checks and stateful generation have more financial assurance value than a test-count target. [OpenTelemetry](https://opentelemetry.io/docs/what-is-opentelemetry/).

**Showcase artifact:** replay a failed generated import/execution sequence, inspect its minimal counterexample and follow a local trace to the failing boundary. Demonstrate independently checked financial expectations alongside agent-written code.

## Adoption sequence and learning budget

1. **Foundation:** typed Python, explicit exact-value storage, versioned schemas, uv/Ruff/type checking and independent reference fixtures. Establish the minimal React/TypeScript/FastAPI path at the first UI slice.
2. **Data/quantitative depth:** Polars at ingestion/history scale; CVXPY/Clarabel reference formulation and risk baseline; marimo for reproducible comparisons. Add DuckDB when a research query justifies it.
3. **Investor showcase:** linked lot/risk/plan views, temporal correction replay, reason codes and complete manual execution/reconciliation simulation.
4. **One frontier experiment at a time:** choose a PGlite/Turso storage spike, a JAX research comparison, or a bounded AI explainer. Keep the result removable until acceptance evidence justifies adoption. No dependency installation is authorized by this sequence.
5. **Distribution:** evaluate Tauri/sidecar packaging after workflow acceptance; a synthetic hosted demonstration is separately scoped and authorized.

Reserve roughly 20% of total engineering effort for explicit learning experiments, and review the budget as the project progresses. This policy is accepted. The [official plan](../PROJECT_PLAN.md) supersedes the original 12-22-week estimate with a 14-25-week core estimate and an approximately 18-32-week envelope if the learning reserve is fully used. These are unvalidated planning estimates, not calendar deadlines or a commitment to ship every optional extension. Re-estimate after the first qualified slices.

For each experiment record the question, strongest alternative, expected advantage, compatibility/license implications, measurable acceptance criterion, time budget and rejection condition. Preserve the experiment report even if the component is rejected. A well-supported decision against a fashionable component is still a useful interview discussion.

## Interview demonstration narrative

A proposed five-minute flow:

1. Import a synthetic stock portfolio and explain how authoritative lots and coverage are established.
2. Move a risk budget and compare loss/risk/cost candidates with the no-trade baseline.
3. Inspect a blocked lot and trace its reason to source evidence, not an LLM guess.
4. Reveal a late activity/correction and show original-versus-corrected state and plan invalidation.
5. Reconcile partial execution and explain what remains uncertain before the next trade.

The accompanying research notebook can compare solver/model alternatives on the same frozen inputs. The engineering evidence can show stateful tests, reproducibility and privacy boundaries. This combines portfolio judgment, data/architecture decisions and a usable financial workflow. Its interview value is a reasoned expectation, not evidence of recruiter or user feedback.
