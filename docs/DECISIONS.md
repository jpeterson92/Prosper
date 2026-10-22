# Decision register

Updated October 22, 2026. **Confirmed** records an explicit user goal or constraint. **Accepted** is adopted project policy or architecture; qualifications and staging in the decision remain binding. **Open** identifies a choice or evidence not settled by approval. Acceptance of this plan is not authorization to implement, access accounts or publish.

Approval record: after reviewing the thirteen-choice architecture comparison, the owner stated, "I agree with all of your suggestions. Can you please incorporate them into the official project plan?" The recommended baseline and staged learning approach are therefore accepted. Alternatives presented for comparison were not all selected simultaneously. [ADR-0001](architecture/decisions/0001-adopt-project-architecture.md) records scope and consequences.

Local setup approval: the owner moved Prosper out of Google Drive and explicitly requested a standard local development setup with future GitHub source backup/change control. [ADR-0003](architecture/decisions/0003-adopt-standard-local-development.md) records the filesystem audit and adopted replacement.

Review-action approval: after the complete product/engineering review, the owner instructed, "Make all suggested changes." [ADR-0002](architecture/decisions/0002-adopt-critical-review-actions.md) adopts the recommendations and records concrete D031-D035 outcomes. This settles policy choices, not the still-unobserved feasibility/qualification evidence.

| ID | Status | Decision / recommendation | Rationale and next evidence |
| --- | --- | --- | --- |
| D001 | Confirmed | Build toward open-source software for self-directed investors using their own brokerage | User's stated long-term goal |
| D002 | Confirmed | Start with individual stocks / direct indexing | User's response October 22, 2026 |
| D003 | Confirmed | Begin with file imports and manual trades; brokerage undecided | User's response October 22, 2026 |
| D004 | Confirmed | This stage is planning and project structure, before implementation | Current task boundary |
| D005 | Accepted | U.S. federal individual taxable scope; one traded account plus household monitoring | Adopted baseline; specific ownership/coverage cases still need source-backed qualification |
| D006 | Accepted | Maintain an existing long-only USD stock sleeve; zero positive-gain budget, whole-share orders | Preserve fractional holdings/residuals; larger transitions and fractional orders require separate qualified scope |
| D007 | Accepted | Local single-user application; private investor data outside source repository, project-local synthetic development artifacts permitted (ADR-0003) | Validate install/update/recovery; synthetic hosted showcase is a later workstream |
| D008 | Accepted | Typed Python financial core and SQLite authority with explicit exact-value encoding | Qualify numeric storage/recovery in T003; future store experiments cannot create a second authority |
| D009 | Accepted | Avoid known-conflict harvests rather than optimize partial wash disallowance | Conservative product policy; acceptance does not constitute professional tax validation |
| D010 | Open | Qualify and choose first broker export/manual execution workflow | T002 must demonstrate lot/history/cash/confirmation coverage; API existence is insufficient |
| D011 | Accepted | Supply a licensed/permitted weighted basket and synthetic development data | Actual data source/rights remain to qualify; no commercial constituents automatically licensed |
| D012 | Open | Risk-data provider, estimator settings, discrete solver/candidate method and investor thresholds | Shrinkage baseline and continuous solver direction are accepted separately; numerical/data qualification remains required |
| D013 | Accepted | Maximize eligible price/basis loss at reference prices under hard risk/cash/cost limits | D033 defines cost-free objective reward, indicative net-proceeds P&L and deterministic cost/order tie-breaks; tax-dollar scenarios remain conditional |
| D014 | Open | Software license, copyright holder and contribution terms | Recommend considering Apache-2.0 or MIT; owner selects before public distribution. No license grant installed yet |
| D015 | Accepted | Independent tax/risk review and paper acceptance before financial-use pilot | Review/acceptance policy adopted; reviewer availability/budget and actual findings remain unresolved |
| D016 | Open | Legal scope for actual external distribution/service model | Resolve before external pilot/public beta; no assumed self-directed/open-source exemption |
| D017 | Open | Exact freshness horizons, limits and supported tax years | Calibrate with selected broker, data availability and paper sessions; never inherit illustrative values silently |
| D018 | Open | Repository visibility/creation, name availability, release packaging, support contact | GitHub is the owner's intended source backup/change-control host; no remote creation/upload authorized by the local setup request |
| D019 | Confirmed | Include current/emerging technology, learning and FinTech interview-showcase value in planning | User's follow-up October 22, 2026; novelty is a consideration rather than a requirement for every layer |
| D020 | Accepted | React/TypeScript/Vite interface with FastAPI/Pydantic and an OpenAPI-generated client | Qualify exact-value transport, contract drift, local security and investor workflow |
| D021 | Accepted | Polars/Parquet analytical path; DuckDB introduced only for justified research queries | DuckDB inclusion is conditional on a concrete query/use case; derived data stays rebuildable |
| D022 | Accepted | CVXPY/Clarabel continuous reference formulation; whole-share candidates independently validated | Discrete production method still needs qualification; no claim Clarabel solves integer orders |
| D023 | Accepted | marimo research; evaluate Tauri 2/Python sidecar after end-to-end workflow acceptance | Tauri evaluation is adopted, not a prequalified installer commitment or Rust-core rewrite |
| D024 | Accepted | Optional later read-only AI explainer, initially synthetic-only | Accepted as a bounded experiment option; provider/priority remain open; no authoritative tax/state/trading powers |
| D025 | Accepted | Versioned relational evidence with effective/recorded time; explicit lifecycle transitions | Original and corrected decisions remain reproducible; full event sourcing is a deferred alternative |
| D026 | Accepted | Reserve roughly 20% of total engineering effort for explicit learning experiments; run one exploratory track at a time | Review budget after early evidence; optional tracks can be rejected; no automatic adoption of compared alternatives |
| D027 | Open | Select and bound the first exploratory track | PGlite/Turso storage, JAX sensitivity research or AI explanation; choose based on a written question and acceptance criteria |
| D028 | Accepted | uv, Ruff, strict typing, pytest/Hypothesis, Playwright; structured local diagnostics and conditional OpenTelemetry | [T003.1](tasks/T003.1-development-baseline.md) locally qualified pinned Python tools and mypy strict for the bootstrap cases; API/numerical annotation support, Playwright and later stack versions remain to qualify; no remote telemetry exporter by default |
| D029 | Accepted | Stage a synthetic-only interview showcase after core workflow exists | Static/versioned results first; hosting/provider/cost and any live backend need separate concrete scope and release authority |
| D030 | Accepted | Reviewed shrinkage covariance baseline with reproducible marimo model/solver comparisons | Ledoit-Wolf is the initial reference candidate; data, window, missingness, annualization and specialist validation remain to qualify |
| D031 | Accepted | First pilot already owns an eligible stock sleeve and can supply supported lot/household evidence | ETF/cash onboarding deferred; measure actual setup/order/recovery burden at G1; no minimum capital or usability claim inferred |
| D032 | Accepted | Retain strict caps, zero positive gains and whole-share orders; report baseline breaches and blocked/no-candidate reasons | No automatic baseline-relative relaxation or gain-budget repair; assess representative candidate yield before expanding scope |
| D033 | Accepted | Reference-price/basis loss objective excluding cost reward; separate execution-cost and net-proceeds P&L fields; explicit budgets and optional investor economic screens | Formulas in portfolio construction; no personalized monetary/rate defaults; lower cost/fewer orders break objective ties; qualify accounting before financial use |
| D034 | Accepted | Initially support qualified ordinary domestic-corporation common equity and reviewed basis/holding evidence; special/uncertain classes/events blocked | Exclude REIT/RIC/BDC, partnership, ADR/foreign/uncertain cases from actionable generation; preserve diagnostic holdings/NAV; no broad historical tax-engine claim |
| D035 | Accepted | Windows x64 is the first supported investor platform target | Exact Windows/browser/runtime versions and installer checks remain qualification work; macOS/Linux release support deferred |
| D036 | Accepted | Direct next-step prompts inspect state and conservatively size one GPT-6.1 Sol/high task; oversized work gets a planning-only decomposition run, then a later invocation executes one ready child | [Protocol](engineering/NEXT_STEP.md); small verified slices, persistent task pointer and current-chat stage naming; future next invocation supplies scoped local synthetic implementation authority; no model-switch or native-command claim |
| D037 | Accepted | Standard local filesystem checkout; `.venv` editable development, normal caches, ignored generated artifacts, normalized text and prepared Windows GitHub CI | Owner's explicit migration/setup request; [ADR-0003](architecture/decisions/0003-adopt-standard-local-development.md) supersedes Drive-specific restrictions; private investor data stays outside source; remote upload and hosted CI remain unperformed |

## Recording a consequential decision

The [architecture tradeoff review](architecture/TECHNOLOGY_TRADEOFFS.md) preserves reasoning, alternatives and qualification triggers. The decision register and accepted ADR identify what was adopted. Neither approval nor documentation is evidence of successful implementation, numerical validation or a measured benchmark.

The [pre-implementation review](reviews/2026-10-22-pre-implementation-review.md) identified D031-D035, now adopted by the follow-up owner instruction. Its snapshot/atomicity/recovery/result-status requirements are incorporated in the design. [The foundation specification](engineering/FOUNDATION_SPEC.md) supplies a complete written G0 contract and fictional import case. No software behavior, broker feasibility or specialist review is verified by these decisions.

For a choice that changes tax behavior, risk methodology, data semantics, architecture or distribution, add an ADR under `docs/architecture/decisions/` when the decision is made. Use a short Markdown file containing: ID/date/status, question, context and evidence, alternatives, decision and approver, consequences, acceptance evidence, and what would trigger reconsideration. No empty ADR files are required now.

Accepted decisions should be reflected in the product/architecture documents and this register. When evidence overturns a choice, supersede it with a new entry; do not rewrite history to imply the original choice never existed.
