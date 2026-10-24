# Prosper: the remaining project roadmap

Written October 23, 2026, at the owner's request for a comprehensive, human-readable explanation of the remaining work. This is a planning companion to the [official project plan](PROJECT_PLAN.md) and [technical task briefs](tasks/REMAINING_WORK_PLAN.md). It explains the existing scope; it does not approve new financial policy, implementation, data access or release. [STATUS](STATUS.md) owns current evidence and the single next-task pointer. Future status changes there take precedence over this dated snapshot.

## What we are building toward

Prosper should let a sophisticated self-directed investor maintain an existing individual-stock portfolio near a chosen benchmark while selectively harvesting losses. The investor keeps their brokerage account and controls every trade. Prosper supplies a repeatable, inspectable process:

**Import evidence -> reconcile the portfolio -> establish eligibility and risk -> compare harvesting with doing nothing -> review a specific plan -> trade manually -> reconcile actual results -> monitor later activity.**

The first useful release completes that entire loop for a deliberately narrow set of supported cases. It is a local, single-user Windows application with a browser interface, one taxable account for proposed trades, and relevant household activity used for conflict monitoring. It starts with qualified ordinary domestic-corporation common equity, whole-share proposed orders, explicit risk/cash/cost limits and a zero positive-gain budget. Fractional holdings and unsupported holdings remain visible in the portfolio evidence.

There is also a second goal: make Prosper a convincing FinTech learning and interview showcase. The best demonstration will come from the same working product: clear financial reasoning, careful state management, reproducible quantitative research and a usable investor workflow. Optional technology experiments support that goal within the adopted learning reserve.

The broader success criterion is an understandable process with no unexplained holdings, basis, cash or plan discrepancies in qualified cases. A result that says "take no action" can be correct and useful. Harvested-loss totals alone do not establish after-tax investment performance.

## Where the project stands

Much of the underlying engineering foundation is already locally verified: exact decimal values, synthetic bundle parsing and reconciliation, immutable source evidence, SQLite checkpoints, durable import previews, atomic activation, backup/restore, conservative recovery, a protected local API, and a generated browser client with a minimal diagnostic interface. The written product baseline and reference examples also exist. These completed pieces are dependencies to reuse, rather than remaining tasks to rebuild.

The original roadmap was drafted while T004.4.1.2 was being qualified. Subsequent [reviewed commit/reject](tasks/T004.4.2-lifecycle-ui.md), [integrated candidate](tasks/T004.5.1-integrated-candidate.md) and [workload measurements/handoff](tasks/T004.5.2-import-measurements.md) now locally verify the bounded synthetic import foundation. The foundation rows below remain as the roadmap's original scope reference; they are no longer remaining work. Their reports own actual verification results and exclusions. T002.1's public evidence review is also complete and the owner selected Fidelity; the T002 rows below explain its remaining format/workflow gaps. STATUS owns the single next-candidate pointer. No broker research started in the measurement task.

The project does not yet have qualified lot eligibility, a portfolio risk model, a constrained harvesting engine, the full manual execution/reconciliation loop, or an accepted investor installation. G1-G3 remain open. Those are the major remaining outcomes described below.

The owner's October 23 [holdings-first input decision](architecture/decisions/0004-adopt-holdings-first-inputs.md) updates those future tasks: lot snapshots are the normal starting point, transaction history is optional with conditional wash-sale warnings/manual restrictions, and cash is an always-editable additional investment budget. Risk covers the stock sleeve plus selected cash; untouched cash is outside that scope. Missing total account cash, a redundant position export or a bulk history file does not by itself prevent optimization. Required basis/security/risk facts and known contradictions still need resolution. These controls are planned, with validation assigned to existing tasks; the current inspector remains a read-only source observer.

## How this turns into successive `/next` tasks

Each direct `/next` invocation inspects the current state and attempts one bounded, dependency-ready task. It includes that task's checks, review, necessary fixes and handoff. If concrete scope makes the selected task too broad, that invocation writes smaller child briefs and stops; a later invocation executes one child. An unfinished task is resumed or remedied before progressing past it. Asking for this roadmap does not invoke an implementation task.

Task numbers identify stable scopes, not a strictly numerical execution order. T002 and T017 deliberately bring feasibility evidence forward; T003.5 belongs later with the numerical work; T018 spans several phases. The following sequence is a dependency guide, not a second automatic queue:

| Step | What becomes possible | Main remaining tasks |
| --- | --- | --- |
| 1. Finish the import foundation | Accept or reject a reviewed synthetic import through the browser, then reproduce and measure the complete path | T004.4.2, T004.5.1-.2 |
| 2. Establish broker and data feasibility | Know whether the intended investor can supply sufficient evidence and carry out the proposed manual process | T002.1-.2, T017.1-.2; G1 |
| 3. Establish lot eligibility | Distinguish supported harvestable loss opportunities from conflicts, unknowns and unsupported cases | T005.1-.2 |
| 4. Establish portfolio risk and numerical methods | Measure benchmark deviations and qualify the machinery used to search for portfolios | T006.1-.2, T003.5.1-.2, T012.1-.2; T018.1 before its dependent integrations |
| 5. Construct constrained plans | Compare independently validated harvesting candidates with doing nothing | T007.1-.2; G2 before actionable paper-candidate acceptance |
| 6. Complete the investor loop | Review an immutable plan, prepare a manual worksheet, reconcile actual fills and monitor later changes | T008.1-.2, T009.1-.2, T018.2 |
| 7. Qualify a private alpha | Demonstrate complete paper workflows, obtain independent review and observe user understanding | T010.1-.2; supported installation evidence; G3 |
| 8. Prepare a distributable beta | Resolve rights/support obligations and qualify an identified Windows release candidate | T011.1-.2; explicit publication decision |
| 9. Deliver the showcase and selected experiments | Explain the product through a reproducible fictional demonstration and bounded learning results | T015.1-.2; T013/T014 and optional T016 as selected |

Feasibility work can happen before the import foundation is fully finished when its own inputs are available. Research accompanies the quantitative work; it need not wait for the investor UI. Showcase preparation can follow usable P4 behavior before public beta. Optional experiments do not all have to ship for the core product to succeed.

## 1. Finish a trustworthy import and review workflow

**Broader purpose:** establish the portfolio facts that every later calculation will depend on. If the application cannot explain what it imported, identify contradictions and recover the same exact state, later harvesting results cannot be trusted.

| Task | What it accomplishes | Evidence that finishes it |
| --- | --- | --- |
| **T004.4.2: Commit and reject in the browser** | Let the user explicitly accept or reject reviewed evidence. Explain durable outcomes, repeated commands, conflicts and stale state so a refresh or second window cannot accidentally activate the wrong import. This approves an import, not a trade. | Real preview-to-commit/reject workflows, duplicate/retry behavior, two-window stale-state handling and restart behavior. The complete review-screen parent is now locally verified; this task is ready for fresh assessment. |
| **T004.5.1: Reproduce the integrated foundation** | Prove the pieces work together against one identified candidate: clean developer setup, bundled UI, protected API, SQLite, exact values and recovery after browser-driven changes. | An integration report linking the fictional foundation cases to actual evidence, including backup/restore and honest residual findings. Existing component tests remain their owners' responsibility. |
| **T004.5.2: Measure the foundation and hand it off** | Find out whether the import path remains practical beyond tiny examples. Measure a deterministic 100-stock/2,000-lot synthetic workload and document host, footprint and latency. | Independently checked input totals, repeatable measurements and a complete foundation handoff. Import performance does not establish future optimizer capacity. |

**Result for the investor:** a credible local import/reconciliation review experience with explicit gaps and durable state. It still produces no harvesting recommendation. This is the nearest usable milestone and the remaining P1 foundation work.

## 2. Establish that the broker, data and manual process are workable

**Broader purpose:** retire expensive assumptions before building substantial broker-facing or quantitative behavior. A generic importer does not prove that a particular brokerage export contains the lot evidence required by the strategy.

| Task | What it accomplishes | Evidence that finishes it |
| --- | --- | --- |
| **T002.1: Broker capability and field evidence** | Research a bounded candidate workflow using current official public documentation. Check lot identifiers, adjusted basis, holding evidence, cash categories, activity cutoffs, specific-lot selection and confirmations. | [Public evidence review complete](tasks/T002.1-public-broker-evidence.md), October 23. Owner selected Fidelity; the matrix preserves unsupported fields and conflicting help. This does not qualify the workflow or pass G1. No account access or outreach occurred. |
| **T002.2: Source-to-canonical mapping** | Map fictional Fidelity lot records and supplement profile/as-of/security facts through attributable user/provider routes. Rehearse duplicates, contradictions and manual exact-lot confirmations. | [Fixture preparation](tasks/T002.2-fidelity-fixture-preparation.md) and the [read-only combined-lot inspector](tasks/T002.2-combined-lot-mapping.md) are locally verified under the owner's stock-shape assumption. Remaining work is now split into [T002.2.1-T002.2.3](tasks/T002.2-holdings-first-qualification-plan.md): a local synthetic assembled-input assessment, opening-source semantics/fidelity, and manual execution/confirmation/funding evidence. [T002.2.1](tasks/T002.2.1-assembled-input-assessment.md) is now implemented and locally verified as a pure diagnostic. [T002.2.2](tasks/T002.2.2-opening-source-disposition.md) has completed its public opening-source disposition; actual source/account qualification remains incomplete. [T002.2.3](tasks/T002.2.3-manual-workflow-disposition.md) has now completed its bounded public manual-workflow disposition, retaining unknown interface/account applicability, correction/funding and burden gaps. Remaining G1 evidence requires new owner/provider inputs; no successor began in that review run. Persisted assembly/import integration remains a later explicitly scoped obligation. Missing optional cash/history/position exports alone are not blockers under ADR-0004; actual contradictions still are. No authoritative checkpoint activation or G1 qualification is established. |
| **T017.1: Pilot and permitted-data feasibility** | Check holdings-first pilot fit, user/provider supplements, optional manual history restrictions and cash budget, plus a usable benchmark, quotes and market history for risk. Identify rights, refresh and setup burden. | [T017.1 input package and sheet](tasks/T017.1-pilot-data-feasibility.md) now supply fictional 20/100/200-stock sleeves and a stylized 500-name benchmark, with evidence, user assumptions and gaps separate. Uses T002 and ADR-0004; actual workflow/provider rights remain unqualified and no real portfolio upload or full broker history/cash export is required. The expanded public-universe experiment is [split into membership, coverage and refresh qualification children](tasks/T017.1-coverage-refresh-plan.md); no child execution occurred during decomposition and G1 remains unpassed. |
| **T017.2: Manual execution and exception rehearsal** | Walk through fictional exact-lot sales, funding, replacement failures, wrong-lot confirmations and recovery using the proposed broker process. Discover whether the manual burden is tolerable before building the full execution UI. | [Paper rehearsal complete](tasks/T017.2-manual-execution-rehearsal.md), October 23, with partial/failed/unknown execution, wrong-lot, selected-cash/coverage/recovery cases and independent arithmetic. Actual broker fidelity, investor burden and provider rights remain gaps; G1 is not passed. |

**Result for the project:** a defensible first workflow and data plan, or an early finding that the current approach needs a decision. **G1 passes only when the underlying evidence supports it.** D043 permits local synthetic numerical qualification while G1 remains open; unresolved operational/input evidence blocks the features that depend on it. See the [adopted sequencing record](tasks/G1-evidence-proposal.md#owner-adopted-sequencing-and-behavior).

## 3. Determine which lots can be considered

**Broader purpose:** distinguish a position that has fallen in price from a supported, eligible loss opportunity. This is where sourced tax requirements, conservative product policy and factual evidence begin controlling candidate eligibility.

| Task | What it accomplishes | Evidence that finishes it |
| --- | --- | --- |
| **T005.1: Supported lot economics and evidence** | Compute supported quantity/basis allocations, reference-price loss, fees and net-proceeds P&L. Track holding/classification evidence and preserve unsupported holdings and unknowns. | Independently justified arithmetic and allocation cases, reconciliation/conservation checks and explicit exclusion of unqualified cases. Needs the completed foundation, relevant G1 evidence and reviewed supported tax/broker semantics. |
| **T005.2: Household conflict and coverage screening** | Screen both proposed sales and replacement purchases against relevant household activity and security relationships. Explain known conflicts and unknown coverage instead of declaring an unseen account clean. | Reviewed boundary/cross-year cases, explicit coverage intervals and conservative unknown/conflict outcomes. Depends on T005.1 and reviewed identity/date/coverage requirements. |

**Result for the investor:** explainable lot-level opportunities and blocks. The first product avoids known conflicts and can block complex cases; it does not need a complete historical tax-return engine or partial-wash optimizer. Agent-written tests remain engineering evidence; independent factual tax review is still required.

## 4. Measure the portfolio and qualify the numerical approach

**Broader purpose:** make loss harvesting a portfolio-construction problem. A large loss can be an unattractive trade if it creates unacceptable benchmark deviation, cash needs or transaction costs.

| Task | What it accomplishes | Evidence that finishes it |
| --- | --- | --- |
| **T006.1: Benchmark, prices and exposure diagnostics** | Establish frozen benchmark weights and prices, identifier alignment, source dates and coverage. Calculate portfolio weights and security/sector deviations from the benchmark, including existing breaches. Introduce the adopted analytical tools only where a concrete ingestion/history path needs them. | Hand-checkable weights/NAV, explicit cash denominators and no silent deletion or renormalization of missing inputs. Requires foundation and G1 permitted-data evidence. |
| **T006.2: Enhanced DCC-NL and industry risk** | Build the D041-selected IDR/OHLC-enhanced DCC-NL forecast and sector/industry exposures, limits and signed contributions from the same covariance. [D042/ADR-0008](architecture/decisions/0008-adopt-python-dcc-implementation.md) selects maintained Python delivery with qualified NumPy/SciPy and no investor MATLAB runtime. | [Bounded children](tasks/T006.2-dcc-industry-plan.md) retain published parity, input/fitting/horizon, group reconciliation and forward TE/scale qualification. Waiting on T006.1, detailed settings and required G1 evidence; neither selection nor sector weights establish qualified risk. |
| **T003.5.1: Continuous reference formulation** | Qualify CVXPY/Clarabel on a small frozen problem whose economics and risk constraints are understood. Use the continuous model as a reference or bound for the later whole-share problem. | Independently derived or enumerated feasible/infeasible cases, objective accounting and numerical diagnostics. Depends on G1 and qualified T005/T006 contracts; fractional mathematical solutions do not certify executable orders. |
| **T003.5.2: Whole-share method qualification** | Compare a bounded candidate/repair method or suitable discrete backend with tiny exhaustive enumeration. Prepare the method decision before production adoption. | Reproducible hard-cap/cost/lot cases, timeout behavior, runtime and optimality limitations. Depends on the continuous reference; D012 adoption remains open. Search failure must not be called proof that no solution exists. |
| **T012.1: Frozen-input research notebook** | Introduce a reproducible marimo notebook using the same read-only financial core and frozen inputs. Make baseline exposures, tiny reference cases and assumptions inspectable. | Fresh execution reproduces identified results with recorded versions and inputs. Depends on qualified T005/T006 and T003.5 reference outputs. Research cannot rewrite authoritative book records. |
| **T012.2: Focused v1 qualification report** | Compare the selected v1 risk/candidate method with its necessary reference on identical frozen data. Explain calibration, feasibility, numerical gaps, costs and runtime. Broad covariance-family research is deferred to v2. | A reproducible bounded report retaining numerical/independent validation and distinguishing proposals from adopted methodology; no repeated solver qualification or silent policy change. |

**Result for the investor:** meaningful baseline risk diagnostics. **Result for the project:** a justified numerical method and an auditable research story. Focused validation of the selected v1 risk model, numerical reference/solver checks and reproducible evidence remain core work. The owner has deferred the broad risk-family comparison to [v2 research preparation](tasks/V2-risk-model-comparison.md); it is not a v1 delivery dependency. [D041/ADR-0007](architecture/decisions/0007-adopt-enhanced-dcc-nl-industry-risk.md) now adopts enhanced DCC-NL/industry risk; the [prior EWMA suggestion](tasks/T006.2-v1-risk-recommendation.md) is superseded. Providers, detailed estimator settings, classifications and investor limits still require qualification.

## 5. Construct constrained harvesting plans

**Broader purpose:** turn eligible losses and portfolio-risk information into specific proposed trades, with understandable tradeoffs and a valid no-trade alternative.

| Task | What it accomplishes | Evidence that finishes it |
| --- | --- | --- |
| **T007.1: Small candidate engine and independent validator** | Generate whole-share/lot candidates on a tiny universe with known answers. Respect hard risk, cash, cost and zero-positive-gain limits. Implement a separate deterministic validator that recomputes final orders rather than trusting the optimizer's constraint-building logic. | Exhaustive tiny-case comparisons, independently specified final-state checks, honest blocked/infeasible/search-limited outcomes and deterministic ties. Requires qualified eligibility/risk, method adoption, G1 and explicit settings. |
| **T007.2: Bounded portfolio candidate workflow** | Orchestrate multiple risk/loss/cost candidates on the intended workload. Freeze inputs/settings, handle cancellation and late results, and measure whether representative portfolios produce useful qualified candidates. | Measured runtime and candidate yield, hard limits after costs/rounding, stale-result rejection and representative drifted/DRIP-heavy/small-sleeve cases. Depends on T007.1 and T018.1; G2 is required before actionable paper-candidate acceptance. |

**Result for the investor:** a small set of inspectable alternatives showing lots sold, replacement purchases, loss, cash, cost, trade count and modeled risk alongside doing nothing. Constraints stay strict even when that means no qualified candidate. The optimizer does not invent investor preferences or relax policy to make a demonstration look successful.

The stated 100-stock/2,000-lot/500-name universe is a qualification target. The foundation workload measurement covers imports; T007 must separately establish candidate-analysis capacity.

## 6. Complete review, manual execution and follow-up

**Broader purpose:** close the gap between a mathematically valid proposal and an understandable process that survives real execution uncertainty.

| Task | What it accomplishes | Evidence that finishes it |
| --- | --- | --- |
| **T008.1: Immutable review and approval** | Present the baseline and candidates with linked risk/loss/cost/gap explanations. Let the investor reject or revise a candidate; revisions create new validated versions. Bind approval to exact inputs and reserve the relevant lots/cash atomically. | Changed facts expire candidates, two windows cannot double-reserve, retries remain coherent and edited quantities are revalidated. Depends on T007, G2 and T018.1. Local approval does not submit an order. |
| **T008.2: Manual execution worksheet** | Produce the human-readable instructions needed at the selected brokerage: exact sell lots, whole-share quantities, sides, source times, funding assumptions, restrictions and expiry. Track reported submitted/not-submitted/unknown status. | Exact-lot paper rehearsal, safe exported text and retained commitments when external submission is uncertain. Depends on T008.1 and qualified broker/manual/freshness requirements. Expiry cannot imply brokerage cancellation. |
| **T009.1: Actual fills and lot reconciliation** | Import fictional confirmations and new snapshots, then compare what happened with the intended plan. Reconcile actual shares, prices, cash, fees and broker-confirmed lots. | Partial fills, failed replacements, duplicates and wrong-lot cases remain explicit. Needs T008 and qualified source mappings. A worksheet is never replayed as though it were a fill. |
| **T009.2: Forward monitoring and corrections** | Update provisional outcomes when later activity arrives; preserve the original approved facts and invalidate affected unexecuted plans. Show coverage, last review and the next required check. | Reviewed late/backdated/cross-year cases, reproducible original evidence and blocks when coverage is unknown. Depends on T009.1 and reviewed restriction semantics. No monitoring is assumed while the local app is closed. |

**Result for the investor:** the complete repeatable review cycle. A partial execution becomes an explicit reconciliation problem with retained evidence, rather than an unexplained portfolio change. Full linked UI work belongs to these investor-facing tasks; completing the early import screen does not complete this interface.

## 7. Carry trustworthy state through every phase

**Broader purpose:** preserve what was known when a result was generated or approved, even after new imports, corrections, competing windows or recovery. This is cross-cutting work, not a separate second implementation of imports or approvals.

| Task | What it accomplishes | Evidence that finishes it |
| --- | --- | --- |
| **T018.1: Frozen-state and lifecycle contracts** | Align real foundation interfaces with snapshot inclusion, effective versus recorded time, frozen inputs, freshness, result statuses and commitments. Assign every invariant to its implementing feature and expected cases. | Traceable contracts with no unowned check or hidden write authority. Can build on the actual foundation before later lifecycle integrations; required by T007.2 and T008.1. |
| **T018.2: Temporal, concurrency and recovery integration** | Test the whole lifecycle across services: late analysis, backdated corrections, approval races, uncertain submissions and recovery with missing source/risk evidence. | Original facts remain reproducible, stale results cannot become actionable, commitments survive uncertainty and missing evidence blocks dependent results. Depends on T007-T009 and T018.1. |

**Result for the investor:** a plan continues to mean one identifiable set of facts. Individual features still own their first-line tests; these tasks qualify the joins between them before paper acceptance.

## 8. Qualify a private alpha through paper use and review

**Broader purpose:** find out whether the complete product is correct enough, understandable enough and operationally reliable enough for its supported use. Passing engineering tests alone cannot answer those questions.

| Task | What it accomplishes | Evidence that finishes it |
| --- | --- | --- |
| **T010.1: Complete synthetic paper cycles** | Run end-to-end import, screening, comparison, review, execution-report, reconciliation and monitoring cases against one identified candidate. Include adversarial paths and recovery. | Traceable independently specified outcomes and no unexplained lot/cash/basis changes. Needs T005-T009 and applicable T018 qualification; it is not a substitute for missing component checks. |
| **T010.2: Observed sessions and independent review** | Observe representative users completing paper workflows and obtain tax/risk/software review with documented scope. Record confusion, assistance, manual burden and finding dispositions. | Actual session records and review evidence against a named artifact, or explicit unresolved blockers. Needs T010.1, authorized participants and available reviewers. Agent-authored scenarios cannot substitute for participation. |

The representative paper stories are a clean harvest cycle, a household/automatic-purchase conflict cycle, and a partial-fill or lot-mismatch cycle with recovery. Measure setup, recurring review and exception-recovery burden separately from application latency. The existing provisional targets are evaluation questions, not achieved service levels; see the [measurement charter](engineering/VALIDATION.md#provisional-measurement-charter).

**Result for the project:** dispositions supporting G2/G3, or concrete reasons the product is not ready. G3 also needs supported installation/recovery evidence, appropriate real-data authorization and a named artifact/use boundary. Any financial-use pilot requires explicit owner authorization; paper acceptance does not place trades or authorize a public release.

## 9. Prepare a supported, distributable beta

**Broader purpose:** make the software something another person can install, recover, understand and use within its stated scope, with rights and support responsibilities addressed.

| Task | What it accomplishes | Evidence that finishes it |
| --- | --- | --- |
| **T011.1: Distribution, rights and support readiness** | Assemble candidate-specific software/dependency/data rights, ownership, privacy/service scope, product-name, platform and support findings. Prepare concrete unresolved choices for the owner. | A complete readiness package with decisions and residual gaps linked to evidence. Depends on mature candidate evidence and D014/D016/D018; writing it cannot declare legal clearance or select the license automatically. |
| **T011.2: Named release candidate and Windows qualification** | Identify/build the selected distribution path and exercise supported installation, update, uninstall, offline operation, security, interruptions and recovery. Document artifacts, versions and release notes. | Observed supported-matrix and failure-path results, exact source/artifact identity and explicit remaining approvals. The existing brief requires T011.1 and T010/G3 readiness; actual publication remains a separate owner action. |

There is a sequencing detail to resolve before scheduling the private-alpha/release boundary: G3 requires supported installation/recovery evidence, while the current T011.2 brief also lists G3 as a prerequisite. The plan needs to identify which bounded pre-G3 task supplies that evidence and which final-candidate checks T011.2 repeats. T013's launcher evaluation can inform the answer but is not automatically installation acceptance. This is an open planning dependency, not a reason to block the current synthetic foundation or silently mark G3 passed.

**Result for a future user:** an identified supported Windows build with clear setup, recovery, scope and support documentation. GitHub source synchronization, a passing CI run, a prepared candidate, publication and authorization for financial use are distinct events. Repeated `/next` requests do not imply permission to publish or change account settings.

## 10. Turn working behavior into an interview showcase

**Broader purpose:** make the learning and engineering depth easy to demonstrate without exposing private data or relying on unimplemented claims.

| Task | What it accomplishes | Evidence that finishes it |
| --- | --- | --- |
| **T015.1: Versioned demonstration narrative** | Build a five-minute fictional story showing reconciliation, a blocked case, risk/loss/cost choices and an actual-fill deviation. Link each claimed capability to the working candidate and evidence. | Durable synthetic inputs/results and a coherent demonstration grounded in observed implementation. Waits for usable P4 behavior; it can precede public beta. |
| **T015.2: Reproducible local showcase package** | Supply a local replay/demo entry point, reset and launch instructions so another authorized tester can reproduce the story. Reuse the same financial engine. | Clean/offline launch and reset, privacy checks and an understandable five-minute flow with stated limits. Hosting, public links and live backend operation require separate scope/authority. |

**Result for the owner:** a reusable FinTech demonstration that explains both product judgment and implementation choices. Static/versioned outputs come first; a hosted service is not required for this outcome.

## 11. Run bounded learning experiments when useful

These tracks use the adopted reserve of roughly 20% of total engineering effort. They are choices within that reserve, not extra unlimited projects. One exploratory track is active at a time; a well-supported rejection is a valid learning result. Core reproducible research in T012 is already part of the product plan.

| Task | What it accomplishes | Entry and completion conditions |
| --- | --- | --- |
| **T013.1: Evaluate the local launcher** | Measure the existing launcher as a distribution baseline: startup/shutdown, local session/path security, offline assets, footprint and recovery. | After accepted P4 workflow, on a bounded Windows/browser/runtime matrix. Produce named artifacts and real lifecycle/failure observations. |
| **T013.2: Compare Tauri and a Python sidecar** | Test one bounded desktop candidate against the same baseline and recommend adopt, reject or defer. | Requires T013.1 and an authorized experiment. Record measured platform/security/recovery and license findings. Adopting Tauri is a separate decision; a Rust financial-core rewrite is outside this scope. |
| **T014.1: Choose and bound one frontier experiment** | Prepare a concrete question, strongest baseline, budget, synthetic inputs, isolation, rights/cost implications and stop criteria for D027. | Needs a real learning need and available reserve. Finish with a reviewable selection package; do not start competing probes or commit to paid services. |
| **T014.2: Execute and disposition the selected experiment** | Run the approved isolated probe and report reproducible results against its charter. | Requires owner-selected scope. Remove production coupling unless separately accepted. Possibilities include alternative storage, JAX research, AI explanation or a measured Rust need; these are alternatives rather than an instruction to build all of them. |
| **T016.1: Bound optional AI explanation** | If AI is selected, expose only cited immutable synthetic plan facts and unknowns, with no financial mutation powers. Test attempted writes, malicious imported instructions and information boundaries immediately. | Requires the selected AI charter, qualified facts and provider/runtime authorization. Finish with a tested read-only fact/tool contract. |
| **T016.2: Evaluate AI explanation quality** | Measure factual accuracy, citations, explicit unknowns, abstention and resistance to misleading or injected instructions. | Requires T016.1 and permitted synthetic provider access. Produce a bounded evaluation and disposition; explanations never determine basis, eligibility, quantities or approvals. |

If AI is chosen under T014, **T016 is the detailed work for that experiment**, not a second parallel track or a second budget charge. The baseline release can use the qualified local launcher; it does not automatically depend on Tauri or an AI feature. DuckDB likewise remains conditional on a concrete analytical query, rather than a mandatory standalone workstream.

## Decisions and evidence that can change the route

Most architectural and product choices are already adopted. The following remaining decisions require concrete evidence, rather than repeated approval of settled policy:

| Open area | What must be settled | Where it matters |
| --- | --- | --- |
| **D010: First broker workflow** | Fidelity is selected as the initial test broker; the exact export/specific-lot/confirmation process still needs supported field and workflow evidence | T002.2, T017 and later manual execution |
| **D012: Risk data, settings, method and investor limits** | Permitted history/data, reviewed estimator configuration, qualified whole-share method and explicit investor-specific thresholds | T006, T003.5, T007 and G2 |
| **D017: Supported years and freshness** | Supported tax years, coverage/refresh horizons and expiry settings justified by the workflow | Eligibility, candidate validity, worksheet and monitoring |
| **D014/D016/D018: Distribution** | Software license/ownership/contribution terms, actual legal/service scope, data/dependency rights, name/support and packaging responsibilities | External pilot/public beta and T011 |
| **D027: First exploratory track** | One useful, bounded selection within the learning reserve | T014 and optional T016; does not block the core |
| **Independent evidence and participants** | Review availability, tax/risk/software findings, observed user sessions and permissions for the particular data/use | G2/G3 and T010 |

The three major remaining gates answer different questions:

- **G1: Can we obtain sufficient evidence and operate this broker/manual workflow?** T002/T017 supply the early feasibility evidence.
- **G2: Are the financial rules, model and candidate-validation process qualified for actionable paper candidates?** Eligibility, reviewed risk inputs, numerical methods and independent final-state validation supply the evidence.
- **G3: Is a named artifact ready for the specified pilot?** Independent dispositions, observed paper use, supported installation/recovery and authorized data/use supply the evidence. Financial-use authorization is explicit.

The source plans own the detailed gate requirements. A useful independent task can proceed when another branch is blocked, but missing evidence cannot be replaced by invented synthetic facts or broader authority.

## What the roadmap does not silently add

The first product remains focused on an already-owned, supported stock sleeve. It does not require brokerage credentials, automatic orders, hosted multi-user operation, ETF/cash onboarding, major concentrated-position transitions, multi-account trade optimization, state-tax calculations, tax filing, universal corporate-action reconstruction or supported macOS/Linux distribution. Those are later expansion choices, not hidden prerequisites to finishing this plan.

P7 expansion can consider read-only broker adapters, larger scale and broader transitions when beta evidence and user demand justify specific briefs. There is no adopted detailed implementation queue for those extensions yet. A synthetic showcase and optional read-only AI explanation do not expand real-data or brokerage authority.

## How to judge progress and remaining effort

The three immediate foundation scopes are concrete: add commit/reject controls, reproduce the integrated foundation, then measure and hand it off. Later tasks have written component briefs, but their fit remains conditional on actual prerequisites; some will split again when selected. The number of headings therefore does not predict the number of `/next` invocations.

The original project plan's 14-25 focused engineering weeks for core P1-P6, or roughly 18-32 with the learning reserve fully used, were whole-project planning estimates made before measured delivery evidence. They are **not estimates of work remaining from this snapshot**. Do not subtract completed task counts from them: numerical qualification, external review and observed usability have different uncertainty from foundation implementation. Re-estimate after the foundation measurements and G1 evidence, and keep waiting for reviewers, decisions and data rights separate from engineering effort.

For each completed task, the handoff should say what behavior exists, which checks actually ran, which candidate they identify, what remains unresolved and what comes next. The useful progression is **implemented -> locally verified -> independently reviewed -> paper accepted -> explicitly authorized for a named financial-use pilot -> explicitly released**, with evidence appropriate to each step. This roadmap is a map of that progression, not evidence that those later states have been reached.

## Planning record for this document

This request fits one documentation-only outcome: explain the existing remaining scopes, map their dependencies and user value, link the roadmap from the entry points, then check coverage, links, authority and artifact identity. No application, test, fixture or tooling implementation is included.

Current conversation title: **Prosper | Plan: explain the remaining project roadmap**. Git HEAD at intake: `ab4f395cca12ef7f6d70bdb16732840233220898`, branch then `codex/t004.4.1.1-browser-client`. The incoming dirty tree includes T004.4.1.2 implementation and its report, which advanced concurrently during this request; this planning work does not edit those files. Final observed revision and documentation verification are recorded in STATUS and the handoff. This request does not create a build candidate, commit or GitHub synchronization.

The documentation verification outcome is recorded in [STATUS](STATUS.md); the authored manifest identifies the working-tree files collectively and does not independently qualify application behavior. No application tests, frontend/browser/package qualification, independent review, broker/data verification or release operation ran for this planning request. The next implementation action is fresh assessment of **T004.4.2** under a direct next-step invocation.
