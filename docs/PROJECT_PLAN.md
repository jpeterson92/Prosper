# Project plan

Official planning baseline adopted by the project owner on October 22, 2026. T003.1's developer baseline and T003.2's exact-value/synthetic diagnostic allocation primitives are locally verified under later direct `/next` invocations; T004.1.1 also qualifies the strictly parsed synthetic bundle/evidence boundary. [STATUS](STATUS.md) owns current implementation/verification state; scope approval, local verification, independent acceptance and release remain distinct. Plan approval alone authorizes the documentation baseline; subsequent implementation follows scoped agent policy. The product name Prosper is a working name; availability has not been checked.

## Product thesis

Give a sophisticated individual investor a usable way to maintain an individual-stock portfolio near a benchmark while harvesting selected losses, using their existing brokerage account and retaining control of every trade. The product must make its calculations, data gaps, risk tradeoffs, and assumptions inspectable.

The first useful outcome is an investor completing a repeatable review cycle: **import, reconcile, inspect risk and eligible lots, compare a harvest with doing nothing, execute selected trades manually, then reconcile and monitor**. A good result may be an explicit recommendation to take no action.

Direct indexing makes portfolio construction a core requirement. Ranking the largest unrealized losses is insufficient: selling them can create large security, sector, or factor exposures relative to the intended benchmark. The adopted product plan addresses loss harvesting and portfolio maintenance together.

The project also serves as a current FinTech learning/interview showcase. Evaluate technology choices for relevant learning and demonstrable technical depth alongside reliability, privacy, usability and delivery cost. The owner has accepted the recommended architecture and staged learning approach. [ADR-0001](architecture/decisions/0001-adopt-project-architecture.md) records that approval; the [architecture tradeoff review](architecture/TECHNOLOGY_TRADEOFFS.md) preserves the reasoning and alternatives.

## Confirmed goals and adopted product baseline

| Topic | Status | Direction |
| --- | --- | --- |
| Investor ownership | User-confirmed | Self-directed investor using their own brokerage; open-source software goal |
| Initial portfolio | User-confirmed | Individual stocks / direct indexing |
| Initial connectivity | User-confirmed | Broker undecided; file imports and manual trades |
| Work authorized now | User-confirmed | Plan and project structure before implementation |
| Learning/showcase | User-confirmed | Consider current and emerging technology and FinTech interview demonstration value |
| Jurisdiction | Adopted | U.S. federal individual taxable accounts; tax-year-specific policies |
| First account scope | Adopted | One account for proposed trades, household accounts/related activity as monitoring inputs |
| Deployment | Adopted | Local application with browser interface, single user, no hosted custody or account aggregation |
| Benchmark | Adopted | User-supplied weighted basket with documented usage rights; synthetic basket for development |
| Asset support | Adopted | Long-only USD ordinary domestic-corporation common equity with qualified tax evidence; cash and all diagnostic holdings retained |
| Strategy boundary | Adopted | First pilot already owns a qualified sleeve; funding from cash/ETFs and large transitions deferred; no automatic gain or risk-cap relaxation |
| First release target | Adopted | Windows x64 with local browser launcher; exact OS/browser/runtime versions qualified during setup |
| Order/gain policy | Adopted | Whole-share proposed orders, fractional holdings preserved, zero positive-gain budget initially |
| Tax/optimization policy | Adopted | Avoid known conflicts; maximize eligible price/basis loss at frozen reference prices, excluding costs from reward; explicit budgets and independent validation |

These choices do not need repeated owner approval. Data completeness, factual tax cases, numerical implementation and investor-specific limits still require qualification. The [decision register](DECISIONS.md) distinguishes accepted policy from genuinely open details.

The [critical pre-implementation review](reviews/2026-10-22-pre-implementation-review.md) preserves this baseline and identifies five product choices (D031-D035), now adopted through [ADR-0002](architecture/decisions/0002-adopt-critical-review-actions.md): existing-stock-sleeve pilot, strict caps/zero gains, explicit loss/cost economics, qualified ordinary domestic-corporation equity cases and Windows x64 first. These are policy decisions; feasibility and acceptance evidence remain outstanding. Engineering clarifications now make snapshot boundaries, stale-result checks, bidirectional household screening, reservations and recovery explicit.

## First usable release

An investor can import a qualified lot snapshot, position/cash snapshot, sufficiently complete activity history, quotes, a benchmark, and restrictions. The application displays reconciliation and household coverage before offering a plan. On supported cases it produces a constrained set of lot sales and replacement purchases, shows before/after benchmark exposures and modeled risk, and explains loss amounts and assumptions. It produces a human-readable execution worksheet with exact lot references, then imports confirmations and new snapshots to reconcile actual results and track future restrictions.

The product specification is in [SPEC.md](product/SPEC.md). Initial supported scale has a **qualification target** of 100 held stocks, 2,000 open lots, and a 500-name candidate/benchmark universe. This is an adopted test target, not measured capacity. Broader scale requires profiling and new acceptance evidence.

It will not initially place orders, select an investment strategy for the user, file taxes, reconstruct every historical tax event, manage margin/options/shorts, or promise outperformance or tax savings. It will not silently treat missing household visibility as evidence that no conflict exists.

## Adopted architecture

Use one repository and one modular local application initially. A deterministic domain core separates lot/basis semantics, wash-sale checks, portfolio risk, candidate generation, and independent plan validation. Import adapters translate broker formats into versioned contracts. A local interface exposes the same application services used by tests and diagnostic tooling. Development UI/API processes, a later compute worker or a desktop sidecar do not imply microservices.

| Layer | Adopted choice | Introduction and qualification |
| --- | --- | --- |
| Financial core | Typed deterministic Python | P1 onward; exact money/quantity rules and independently justified cases |
| Authoritative persistence | SQLite; canonical exact decimal strings stored as TEXT under the foundation numeric contract | P1 exact round trips, transactional imports, corrections and recovery |
| Investor interface | React + TypeScript + Vite | Minimal import/review UI in P1, full linked lot/risk/plan workflow in P4 |
| API/contracts | FastAPI + Pydantic; OpenAPI-generated TypeScript client | P1; decimal-string transport, contract drift, domain validation and local security |
| Analytical pipeline | Polars + immutable Parquet inputs | Introduce when ingestion/history work needs tabular transformations; preserve authoritative provenance |
| Analytical SQL | DuckDB, conditional on a concrete query | Research stage; rebuildable derived state, no second financial authority |
| Continuous optimization | CVXPY + Clarabel reference/relaxation models | P3; exact formulation/numerical tests; discrete order construction remains separately qualified |
| Risk/research | Reviewed shrinkage covariance baseline; marimo comparisons | P3; initial Ledoit-Wolf reference candidate, frozen inputs, PSD/as-of/annualization checks |
| History/lifecycle | Versioned relational evidence, effective and recorded time | P1 onward; replay late corrections and preserve known-at-approval state |
| Engineering | uv, Ruff, strict typing, pytest/Hypothesis, Playwright | Introduce with implementation; qualify exact versions/checker, independent cases and stateful/e2e checks |
| Observability | Structured private local diagnostics; conditional OpenTelemetry | Instrument a real analysis pipeline when useful, without portfolio payloads or default remote export |
| Desktop distribution | Local browser launcher first; Tauri 2/Python-sidecar evaluation | Evaluate after P4 workflow acceptance; final installer choice requires supported-OS/security/recovery evidence |
| AI/exploration | Optional read-only synthetic-first AI explainer; one exploratory track at a time | Later bounded experiment, no authoritative financial writes/approval/trading; PGlite/Turso/JAX/Rust remain alternatives |

Approval adopts these choices and their conditions, not all compared alternatives. [T003.1](tasks/T003.1-development-baseline.md) locally qualified CPython 3.12.4, uv/Ruff/strict mypy/pytest/Hypothesis and a minimal build backend; versions and dependency metadata are in the [development guide](engineering/DEVELOPMENT.md). Other compatible stack versions, discrete solver/candidate method, risk-data provider/settings, final installer and first exploratory track remain to qualify. Bootstrap type-check support does not establish future API/numerical annotation compatibility.

See [architecture](architecture/ARCHITECTURE.md), [data contracts](architecture/DATA_CONTRACTS.md), [portfolio construction](domain/PORTFOLIO_CONSTRUCTION.md), and [tax policy](domain/TAX_POLICY.md). The [architecture adoption ADR](architecture/decisions/0001-adopt-project-architecture.md) records consequential choices and reconsideration triggers.

## Local development and source control

The owner moved the project out of Google Drive and adopted a standard local filesystem baseline in [ADR-0003](architecture/decisions/0003-adopt-standard-local-development.md). Development dependencies live in project-local `.venv`; normal caches and ignored synthetic artifacts are allowed. Private investor data remains outside source. The owner created [jpeterson92/Prosper](https://github.com/jpeterson92/Prosper) for source backup/change control and origin is connected. Local main is uploaded and tracks origin/main. The first hosted Windows CI run passed; its exact revision and evidence are recorded in STATUS. Core architecture choices retain their product/financial rationale and qualification gates. See the [development guide](engineering/DEVELOPMENT.md) and [setup evidence](tasks/SETUP-local-filesystem.md).

## Milestones and acceptance gates

The revised durations below are estimates in focused engineering weeks for one experienced owner working with coding agents. They include the adopted React/API and reproducible-research baseline, exclude the separate learning reserve, and exclude waits for data rights, broker access, specialist review and user availability. They are planning judgments without measured delivery data. Re-estimate after T003/T004; agent throughput is not a basis for a deadline promise.

| Phase | Deliverable and investor-visible result | Exit evidence | Dependency | Initial estimate |
| --- | --- | --- | --- | --- |
| P0: Frame | Adopted plan/architecture and reviewed reference specification; no application | Approval recorded; remaining data/tax questions and first build brief explicit | Written foundation brief complete; specialist review unperformed | Written baseline complete |
| P1: Establish truth | In progress: developer/exact-value primitives verified; remaining qualified generic import, exact SQLite state and minimal typed React/API review workflow | Synthetic lots/positions/activity reconcile; exact-value round trips and contract/error cases pass; commands exercised | Implementation authorization; initial contracts | 2-4 weeks |
| P2: Establish eligibility | Deterministic lot economics and conservative wash-sale screening | Reviewed rule examples, boundary tests, household coverage and unsupported-case blocking | P1; rule expectations reviewed | 2-4 weeks |
| P3: Construct a portfolio | Risk/optimization pipeline, constrained candidates and reproducible marimo comparison | Enumeration/reference bounds; independent post-rounding validation; reviewed risk inputs; model/solver comparison; no-trade outcomes | P2; qualified model/data/formulation | 4-6 weeks |
| P4: Complete the loop | Linked investor UI, frontier/plan comparison, worksheet, fills, monitoring and temporal replay | End-to-end cases include partial fills, lot mismatch, late corrections, stale plans and understandable explanations | P3; qualified broker workflow | 3-5 weeks |
| P5: Qualify a private alpha | Supported install, independent review, observed user sessions | Three representative paper workflows; reviewed tax/risk cases; privacy, recovery and installation evidence | P4; suitable test users and reviewers | 2-4 weeks |
| P6: Publish a beta | Open-source release and supported user documentation | License/data rights resolved, release artifact identified, public-use scope reviewed | P5; owner release approval | 1-2 weeks plus review |
| P7: Expand | Read-only broker adapters, larger scale, broader transitions | Separate feature-specific acceptance | Beta evidence and demand | Unestimated |

The adopted core P1-P6 scope totals approximately **14-25 focused engineering weeks**. Reserve roughly **20% of total engineering effort** for explicitly bounded learning experiments. If that reserve is fully used, the overall planning envelope is approximately **18-32 focused engineering weeks** (core divided by 0.8, rounded). This supersedes the earlier 12-22-week product-only estimate and is not an approved calendar deadline or a promise that every optional feature will ship. Experiments are time-bounded choices within that reserve; do not add them again as an uncounted parallel roadmap. Basic supported distribution belongs in the core; Tauri exploration belongs in the reserve until selected, with any material production-hardening overrun re-estimated.

The first useful import/reconciliation workflow arrives before a complete harvesting product. Independent review, paper acceptance and explicit financial-use authorization remain required; green engineering checks alone do not establish financial readiness.

## Dependency and readiness checkpoints

The roadmap is not authority for an unrestricted full build. Use these checkpoints to retire expensive assumptions before the features that depend on them. A failed check produces a documented gap/decision, not a fabricated passing fixture.

| Checkpoint | Evidence required | Boundary |
| --- | --- | --- |
| G0: Synthetic foundation brief | One precisely specified synthetic bundle, snapshot/event inclusion, numeric/unknown semantics and bounded import/reconciliation/UI/API acceptance | Can support the first slice after implementation authorization; no actionable financial plan |
| G1: Investor/data feasibility | First pilot/entry path and burden, one broker lot/export/manual-confirmation workflow, benchmark/quote/history rights and refresh plan, paper exception walkthrough | Before substantial broker-facing workflow/UI and quantitative build-out |
| G2: Financial/model qualification | Objective/cost semantics, supported tax cases and household restrictions, aligned risk inputs, discrete method and final-state validator | Before acceptance of actionable candidates in paper mode |
| G3: Pilot readiness | Independent review dispositions, observed paper use, supported install/recovery, real-data authorization and named artifact/use | Before owner-authorized financial-use pilot |

G0 is document-ready in the [foundation specification](engineering/FOUNDATION_SPEC.md): complete fictional bundle, numeric rules, variants and bounded T003/T004 brief. This is not a passed software check. G1-G3 have not passed. G0 does not require selecting every optional feature, contacting external parties or completing a full legal review before a synthetic importer. Bring the paper manual-execution/recovery walkthrough forward instead of waiting until P5 to discover that it is impractical. Validate data/solver/installer availability early while retaining full Tauri work after P4. The schedule envelope remains provisional until these feasibility checks produce evidence.

## Learning and interview-showcase workstreams

| Workstream | Status and timing | Required result / decision |
| --- | --- | --- |
| Reproducible quantitative research | Adopted core, P3 | Same frozen inputs across reference/heuristic/solver and risk-model comparisons; record feasibility, gaps, costs and limitations |
| Interactive investor demonstration | Adopted core, P4 | Compare risk/loss/cost candidates, inspect blocked lots, reveal late corrections, reconcile partial execution |
| Analytical SQL | Adopted conditional, P3 or later | Add DuckDB only for a documented analytical query and prove results reproduce canonical inputs |
| Desktop packaging experiment | Adopted evaluation after P4 | Compare local launcher and Tauri/sidecar on install, lifecycle, security, size and recovery; adoption follows evidence |
| Frontier experiment | Accepted policy; first selection open | Choose PGlite/Turso, JAX, AI explanation or a measured Rust need; one exploratory track active at a time |
| AI explanation | Accepted optional experiment after verified plan facts | Synthetic data first; evaluate factual fidelity, citations, unknowns/injection and rejected unauthorized changes |
| Interview showcase distribution | Adopted later scope after core workflow | Synthetic-only replay/demo, static/versioned outputs first; hosting/live backend and publication remain separately authorized |

Each experiment has a question, strongest alternative, bounded effort, acceptance/rejection criteria, dependency/license implications and an evidence report. Rejected components remain documented learning outcomes. Do not let experiments silently change the source of financial truth or the approved trading model.

## First task sequence

Work one reviewable slice at a time. Backlog items are not authorization to implement. A future direct **next** / **let's work on the next step** request uses the adopted [next-step protocol](engineering/NEXT_STEP.md): inspect current truth, assess fit for one GPT-6.1 Sol/high run, and either complete one fitting task or decompose the oversized stage in a documentation-only run that stops before implementation. The broad T003/T004 foundation brief is a parent scope to assess, not a promise of one-run completion. STATUS owns the next-task pointer; child briefs live under tasks. Conversation titles identify the actual mode/task.

At the owner's explicit request, the [remaining work plan](tasks/REMAINING_WORK_PLAN.md) now gives each remaining unsplit scope two components in advance: four later foundation leaves, T003's numerical remainder (T003.5), and T002/T005-T018. It preserves completed work and the existing T004.2 split. The 20 pairs define 40 components with outcomes, exclusions, dependencies, acceptance and conditional sizing; they do not expand the product or pass open gates. Refresh a prepared component's fit when selected and execute it if it passes, without a mandatory extra decomposition-only run. Distant work remains conditional on actual prerequisites and decisions. The table below retains umbrella done conditions; the linked component plan owns their decomposition.

| ID | Task | Concrete done condition | Phase |
| --- | --- | --- | --- |
| T001 | Finalize the reference pack and first implementation brief | Accepted scope/architecture consumed without re-approval; written expectations, open specialist/data questions and bounded next brief complete | P0/P1 |
| T002 | Qualify one broker export workflow without account access | Field-by-field evidence for lot, cash, activity, specific-lot execution and confirmations; gaps documented | P1 |
| T003 | Qualify adopted architecture and establish reproducible development | When implementation is authorized, demonstrate exact-value round trips and typed UI/API boundary; pin compatible versions/checker and local checks; qualify solver formulation before P3 | P1 |
| T004 | Import one generic portfolio end to end | Versioned canonical import, provenance, preview, duplicate handling, reconciliation, no recommendations yet | P1 |
| T005 | Screen lot eligibility | Exact arithmetic and conservative known-conflict/unknown statuses match reviewed cases | P2 |
| T006 | Add benchmark and risk diagnostics | Frozen benchmark and risk inputs yield independently checked exposures and TE; incomplete inputs block plans | P3 |
| T007 | Produce constrained plans | Small deterministic candidate engine, baseline, independent validation and diagnostic infeasibility | P3 |
| T008 | Deliver investor review and manual worksheet | User can understand, reject, revise and approve a specific immutable plan | P4 |
| T009 | Reconcile fills and monitor | Partial fills, external activity, new restrictions and broker-lot discrepancies handled without replaying a plan | P4 |
| T010 | Run shadow/paper acceptance | Representative workflows and adversarial cases pass with documented limitations | P5 |
| T011 | Prepare public release | License, data distribution, supported installation, specialist findings, support and recovery reviewed | P6 |
| T012 | Build the reproducible research comparison | marimo uses shared core/frozen inputs; enumerate tiny cases and compare numerical alternatives with honest evidence | P3 |
| T013 | Evaluate desktop packaging | After P4, exercise launcher versus Tauri/Python-sidecar criteria and record installer decision | Post-P4 learning reserve |
| T014 | Run one selected frontier experiment | Written question/budget and acceptance criteria; isolated result accepted or rejected; no parallel exploratory tracks | Learning reserve |
| T015 | Prepare the synthetic interview showcase | Reproducible five-minute flow, source/research explanation, no real portfolio data; publication separate | P4-P6, staged |
| T016 | Evaluate optional read-only AI explanation | If selected through T014, pass synthetic factuality/authority/privacy checks before any wider scope | Later learning reserve |
| T017 | Establish paper investor/data feasibility | G1 evidence sheet for pilot, source bundle, benchmark/history/quote rights and exact-lot manual recovery; no account access/outreach implied | Before substantial P3/P4 work |
| T018 | Qualify state/analysis contracts | Same-day snapshot inclusion, frozen-run/current-generation checks, result taxonomy, reservations, exact allocation and application-level restore scenarios specified and later tested | G0/P1 onward |

**T001 planning deliverables are complete:** the [foundation specification](engineering/FOUNDATION_SPEC.md) supplies the written G0 numeric/bundle contract and independently reasoned fictional outcomes. The October 22 direct `/next` assessment found the combined T003/T004 parent too broad for one conservatively sized run and completed a planning-only [child plan](tasks/T003-T004-foundation-plan.md). D031-D035 remain adopted; no repeated policy approval is needed.

The foundation roadmap now sequences T003.1 development baseline -> T003.2 exact values -> T004.1 checkpoint validation (T004.1.1 parsing -> T004.1.2 reconciliation/readiness) -> T003.3 persistence (T003.3.1 evidence/runtime -> T003.3.2 SQLite checkpoints) -> T004.2 imports (T004.2.1 durable preview/rejection -> T004.2.2 atomic activation/receipts) -> T004.3 recovery (T004.3.1 backup/restore -> T004.3.2 interrupted-state/orphan recovery) -> T003.4 local typed API (T003.4.1 protected runtime -> T003.4.2 import endpoints) -> T004.4 browser review (T004.4.1 preview/inspection -> T004.4.2 commit/reject) -> T004.5 integrated evidence (T004.5.1 reproducibility -> T004.5.2 measurements/handoff). Each child includes its own tests/review and stops before its successor. T003.1 and [T003.2](tasks/T003.2-exact-values.md) are locally verified. A later planning-only assessment [decomposed T004.1](tasks/T004.1-checkpoint-validation-plan.md) because new parser/schema/identity and financial reconciliation/readiness work left insufficient conservative completion margin. [T004.1.1](tasks/T004.1.1-synthetic-bundle-parsing.md) and [T004.1.2](tasks/T004.1.2-checkpoint-reconciliation.md) are locally verified. Fresh assessment [decomposed T003.3](tasks/T003.3-checkpoint-persistence-plan.md) because new runtime/evidence publication and SQLite storage boundaries leave insufficient conservative completion margin together. Both T003.3 children and the bounded exact persistence parent are now locally verified; execution evidence is linked from the child plan. Fresh assessment [decomposed T004.2](tasks/T004.2-import-workflow-plan.md) because durable staging/schema evolution and coordinated activation/receipt/concurrency qualification leave insufficient conservative margin together. Both T004.2 children are now locally verified: [durable previews](tasks/T004.2.1-durable-previews.md) and [atomic activation/receipts](tasks/T004.2.2-atomic-activation.md). [T004.3.1 backup/restore](tasks/T004.3.1-backup-restore.md) is now locally verified. Fresh [T004.3.2 assessment](tasks/T004.3.2-interrupted-recovery-plan.md) splits interrupted-state/orphan recovery into T004.3.2.1 inspection (subsequently [locally verified](tasks/T004.3.2.1-inspection.md)) and T004.3.2.2 guarded recovery/retention (subsequently [locally verified](tasks/T004.3.2.2-guarded-recovery.md)). The bounded T004.3 recovery parent is now locally verified; T003.4.1 is ready to attempt after fresh dependency/sizing assessment. No child implementation began in that decomposition run; later foundation tasks wait on complete parent acceptance. The owner then requested advance paired decomposition of remaining work, recorded in the linked remaining work plan. STATUS retains the single next-candidate pointer. T003's later solver qualification is T003.5.1/T003.5.2, outside the foundation sequence and conditional on G1/numerical prerequisites. No child implementation began during any decomposition invocation.

T017/G1 must obtain early broker/data/manual-workflow evidence before substantial quantitative or broker-facing build-out; T018 carries state/recovery checks into the relevant slices. The [feature brief](templates/FEATURE_BRIEF.md) and [review package](templates/REVIEW_PACKAGE.md) remain reusable templates. No implementation is authorized by this roadmap; a later invocation supplies only the scoped authority defined by agent policy.

## Highest-risk assumptions and how to retire them

| Assumption | What would invalidate it | Evidence before relying on it |
| --- | --- | --- |
| Imports can support exact lot execution | Only aggregate cost basis is available, or broker cannot confirm selected lots | T002 qualification and manual workflow evidence |
| Household activity can be monitored sufficiently | Missing spouse/IRA/employee-plan activity or automatic purchases | Coverage ledger, bounded attestations and explicit blocked status |
| Risk estimates are affordable and useful | Missing history, unstable covariance, unlicensed data, too many trades | Model validation and rights review; benchmark-aware paper scenarios |
| Manual execution is workable | Excessive orders, rapid price changes, frequent lot mismatches | Small trade-count limits, observed paper sessions, implementation shortfall report |
| An open-source release is distributable | Unresolved software ownership, data or solver licensing | License and dependency/data-rights inventory |
| The product can be made available as intended | Legal analysis of the actual distribution/service model changes scope | Qualified review before external pilot/public beta; no assumed exemption |

## Definition of success

Success is a repeatable, understandable and supported investor workflow with no unexplained holdings, basis, cash, eligibility, or plan discrepancies in qualified cases. Alpha acceptance targets are: all mandatory [validation scenarios](engineering/VALIDATION.md) meet their expectations; every proposed order maps to lots/cash and independently passes hard constraints; a new test user completes the paper workflow without developer intervention; no portfolio information appears in public artifacts or default diagnostics.

Track gross realized losses, modeled allowable losses, transaction costs, active exposures, estimated tracking error, trade count, reconciliation exceptions and user review time separately. A backtest or harvested-loss total does not establish incremental after-tax performance. Longer-term economic validation needs a specified counterfactual, tax scenarios, flows, terminal taxes and reproducible assumptions.

## Operating model

The owner decides outcomes, tax/risk policy and acceptance; coding agents complete scoped engineering and verification. Independent expectations, immutable plan identities and exact release evidence are essential because code and tests can share the same mistaken assumption. See the [agent workflow](engineering/AGENT_WORKFLOW.md).

Planning, local prototype verification, independent review, user acceptance and release are different states. The [status file](STATUS.md) records what actually exists and what remains unverified.
