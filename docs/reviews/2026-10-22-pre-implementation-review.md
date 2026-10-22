# Pre-implementation product and engineering review

**Subsequent disposition, October 22, 2026:** the owner instructed, "Make all suggested changes." [ADR-0002](../architecture/decisions/0002-adopt-critical-review-actions.md) adopts D031-D035 and the review actions. The original findings/recommendations below are retained as the review record; their references to open owner choices describe the state at review time. The action matrix at the end records current disposition. No implementation or qualification evidence is implied.


Date: October 22, 2026. Scope: the complete planning package, from product thesis through architecture, domain/data contracts, delivery, verification, security and agent workflow. This is one agent's critical review through product-manager and senior-engineering lenses; it is not an independent specialist audit or user research.

Reviewed input identity: `docs/PLANNING_MANIFEST.sha256`, SHA-256 `7321c24df098020bd4cc53c7bbde44b08d968afa05708b8229559d39b19cfe78`. Its 29 authored-file entries identify the pre-review package. There was no Git revision. The output manifest is regenerated after this review's documentation changes.

## Assessment

The adopted architecture is a reasonable foundation. Keep the deterministic Python core, React/API boundary, SQLite authority, exact-value contracts, independent validation and staged learning. The plan is substantially stronger on technology and defensive requirements than on proving that the first target investor can actually complete the workflow with obtainable data.

**Do not treat the entire harvesting product as ready for unrestricted implementation.** A bounded synthetic import/reconciliation foundation can be prepared for authorization after its brief fixes the relevant semantics. Before substantial optimizer/full-review-UI work, retire broker/data/manual-workflow feasibility risks. Before actionable financial use, qualify all relevant tax, numerical, operational and review requirements. This review does not authorize any implementation.

The most consequential product questions are who the first user is, how they arrive with a stock sleeve, how much manual work is tolerable, and what economically worthwhile outcome the product should screen for. The most consequential engineering gaps are ambiguous snapshot boundaries, stale computation/approval races, incomplete actionability states, bidirectional household restriction checks, and recovery across the database plus external evidence files.

## Findings and disposition

P1 means high-priority before the dependent feature or user claim; it does not mean that money has already been put at risk. P2 means a material delivery/reliability issue to settle before the indicated milestone. “Clarified” means documentation was tightened, not that software behavior has been verified. “Open” means evidence or an owner decision remains.

| ID | Priority / lens | Finding | Disposition |
| --- | --- | --- | --- |
| R01 | P1 / product | Broker, benchmark/risk data and manual execution feasibility are unproven, yet broad development can precede their qualification | Earlier feasibility checkpoints added; actual evidence open under D010/D012 |
| R02 | P1 / product | Existing-sleeve scope excludes investors starting from cash or ETFs; the first-user/onboarding thesis is unvalidated | D031 open; adopted scope preserved |
| R03 | P1 / product/quant | Zero gains, strict TE caps, whole shares and conservative wash screening can jointly eliminate useful candidates | D032 open; constraint relaxation is not silently adopted |
| R04 | P1 / product/quant | Gross-loss objective and cost-adjusted tax P&L are insufficiently distinguished; a feasible harvest need not be worthwhile | D033 open; separate reporting and accounting requirements clarified |
| R05 | P1 / domain | U.S.-listed common stock is not a complete supported-tax-case definition | D034 open; unsupported classification/history remains blocked |
| R06 | P1 / engineering | A dated opening snapshot and dated trades do not establish which same-day events are already included | Explicit event-inclusion boundary and shadow/committed-state rules added |
| R07 | P1 / engineering/domain | Replacement buys must be checked against earlier household loss sales, not just the planned sale's recent acquisitions | Bidirectional screening and unknown-sale-outcome handling made explicit |
| R08 | P1 / engineering | Versioned inputs alone do not prevent stale worker results, duplicate approvals or unsafe reservation release | Analysis/approval atomicity, request identity and execution-uncertainty rules added |
| R09 | P1 / engineering/quant | Search failure is not proof of infeasibility; pre-cost or relaxed results cannot certify final whole-share risk | Result taxonomy and post-cost/post-rounding validation clarified |
| R10 | P2 / engineering | Exact decimal transport does not specify allocation precision, residual handling or double-counting rules | Required field-level numeric/accounting contract added before storing/computing supported financial values |
| R11 | P2 / engineering | Backup/restore does not yet cover immutable raw evidence, analytical files and database references together | Application-level recovery/export requirements added |
| R12 | P2 / product/delivery | Useful end-to-end execution feedback arrives too late; large UI/quant layers can accumulate without a usable cycle | Early paper walkthrough and a small complete synthetic cycle added to sequencing |
| R13 | P2 / delivery | Supported OS, installation footprint and measurable service/usability budgets are unsettled | D035 open; early capability checks required, full Tauri work still later |
| R14 | P2 / product/process | Showcase breadth and numerical schedule ranges can look more certain than user/data evidence supports | Milestones treated as evidence gates; experiment reserve remains a cap, estimates conditional |

## R01: Prove the input and execution path before expanding the build

The [brokerage notes](../research/BROKERAGES.md) correctly avoid claiming a qualified adapter, but a generic importer alone cannot show that a real investor can supply the required bundle. The [product spec](../product/SPEC.md) also asks for benchmark, prices, covariance inputs, classifications and household coverage without a concrete acquisition/refresh process.

Require one broker evidence sheet and one input inventory: exact export fields and cutoffs, cash/fill semantics, selected-lot identification/confirmation, relevant deadlines, household monitoring source, permitted benchmark weights, quote/history quality and usage rights. A redacted/synthetic equivalent can qualify mappings without account access; it cannot prove live capabilities or legal permissions that have not been observed.

IBKR's public documentation describes lot-detail reporting and manual Specific Lot matching with a remaining-time display. That supports further investigation, not a claim that our investor workflow has been tested. [Open Positions reference](https://www.ibkrguides.com/reportingreference/reportguide/open%20positionsfq.htm), [Tax Optimizer window](https://www.ibkrguides.com/traderworkstation/the-tax-optimizer-window.htm).

The earlier gate should expose a missing provider/workflow while little software depends on it. Synthetic foundation work can remain broker-independent; broad workflow claims cannot.

## R02: Define the first investor and entry path

The initial product maintains an existing stock sleeve, while the long-term goal sounds accessible to a sophisticated investor with a brokerage account. Those are different acquisition/activation requirements. A user holding ETFs cannot exercise the full product merely by importing them. No discovery evidence currently supports demand, willingness to maintain household coverage, capital/whole-share practicality or acceptable order burden.

Recommendation for D031: choose a first pilot persona who already holds an eligible stock sleeve and can provide the required evidence. Test the workflow with a written representative portfolio and an owner-led walkthrough. Keep cash-to-stocks onboarding and ETF/concentrated transitions as explicitly deferred features unless the owner chooses to change scope. Do not infer a minimum account value or user satisfaction from the synthetic $16,000 two-stock arithmetic example.

No outreach, user interviews or real-data collection was performed. Such work requires its own authorized participation/data scope.

## R03: Test whether the conservative policy combination remains useful

An appreciated or drifted portfolio may need gain realization to repair benchmark exposures. Whole shares and small trade counts restrict possible repairs. Recent acquisitions can exclude an entire security under PP01. These are valid conservative choices, but their combined candidate yield is unknown.

Keep the accepted zero-positive-gain and absolute-risk-limit behavior until changed. D032 should decide whether to retain a narrower supported pilot, explicitly support a baseline-relative remediation policy, or allow a bounded gain budget in a later release. These choices materially change behavior; this review does not adopt a relaxation.

Write representative cases for an already-compliant sleeve, a sleeve above its TE cap, a restricted/DRIP-heavy sleeve and a small whole-share sleeve. Report how many lots/candidates survive each screen and why a plan is unavailable. An empty feasible set is an honest product result; a product that is almost always blocked for its target user would require scope revision.

## R04: Make trade economics and objective semantics explicit

The current objective maximizes eligible gross loss within hard limits. That does not by itself reject a $20 pre-fee loss with $30 costs if the configured cost budget permits it. Without a loss-utilization scenario it is also impossible to infer that a $200 loss is worth $200 or even any immediate tax dollars.

Recommendation for D033: define the candidate objective precisely, distinguishing price/basis loss from loss calculated using net sale proceeds; specify cost/turnover/notional/trade-count limits and an optional investor-entered minimum economic screen. Keep tax-dollar scenarios optional and conditional. In particular, costs must not accidentally increase the optimizer's reward simply because sale expenses affect reported P&L. The owner must choose the intended behavior before actionable optimization is implemented.

Separately, document where spread/impact assumptions enter indicative execution prices, where commissions enter cash/net proceeds, and how acquisition fees enter basis. Costs already embedded in a price or basis must not be subtracted a second time. The paper case's zero-cost/full-reinvestment assumption is a numerical fixture, not a usable execution default.

## R05: Define supported tax facts beyond a ticker/type label

Common-share listing/type does not establish ordinary tax treatment for every issuer or event. IRS Publication 550 includes special loss-character rules for some fund/REIT holdings and extraordinary qualified dividends, as well as holding-period carryover cases. These matter even when order generation excludes options and funds. [IRS Publication 550](https://www.irs.gov/publications/p550).

D034 should determine the first supported tax-classification/event policy: ordinary supported equity cases only, with special cases blocked pending reviewed inputs/rules, or separately implement the required special-case semantics. Do not silently shrink or broaden the adopted common-stock universe. Capture classification evidence and known special events, preserve adjusted holding-period provenance, and block affected plans when required facts are unknown. Acquisition date alone cannot override supported carried holding-period evidence.

The identity policy also needs scalable rule coverage: versioned, reviewed classification/relationship rules plus exceptions, not an unstated assumption that every possible pair receives an individual professional opinion. Ambiguous pairs still require review or exclusion. The exact rule set needs specialist qualification.

## R06: Reconcile snapshots and event streams without assuming a cutoff

The data contract says events on/before cutoff C are already in the opening snapshot. Broker files may instead describe closing/settled/trade-date state with only a report date. A 10 a.m. purchase and a 4 p.m. position snapshot have the same date; including or excluding it by date alone can double holdings or lose activity.

The adapter must establish snapshot inclusion semantics and the comparable event sequence, not invent a timestamp. If inclusion is ambiguous, stage the evidence and block state mutation that relies on that assumption. Events can be used as historical screening evidence without replaying them into a snapshot. Hypothetical fills go into shadow scenarios; imported executed events and confirmations update actual state. A newer authoritative snapshot establishes a new reconciled checkpoint while preserving prior evidence and discrepancies.

Unsupported corporate actions, unsettled trades, cancellations and corrections must not disappear. An unexplained split/transfer remains a blocking discrepancy until supported or reconciled through reviewed replacement evidence.

## R07: Screen every action in both directions

Checking whether SAAA was recently bought before selling SAAA is only one direction. A plan that sells SAAA and buys SBBB can affect a loss sale of SBBB in another household account earlier in the window. The household event/coverage input must therefore include relevant loss sales and their known/unknown outcomes, not just acquisition activity or current holdings.

For both sale and purchase legs, check prior relevant activity, outstanding restrictions, planned same-batch actions and declared external commitments. If an earlier sale's P&L is unknown, do not assume it was a gain. Newly detected conflicts can mark basis/holding evidence unresolved under PP06 and require authoritative correction; v1 must not silently become a full historical basis engine. This is a clarification of the already adopted household/wash-screening policy. [IRS wash-sale scope](https://www.irs.gov/publications/p550).

## R08: Prevent stale completion and approval races

An import can change lots while a solver is running. A result with a valid hash of old inputs may then reach the UI and be approved unless the commit path checks current state. Two UI windows can approve/reserve the same shares. An expired worksheet may still correspond to an order the investor submitted externally.

Require a frozen analysis-input bundle and run ID, state-generation checks at result publication and approval, and atomic validation/reservation within the one authoritative writer. The worker computes from immutable inputs and does not commit account changes. Repeated commands use idempotency keys; same key/different payload is rejected. Canceled, late or stale jobs remain diagnostic evidence, not actionable plans.

Worksheet expiry invalidates recommendation freshness, not broker orders. If execution may have occurred, retain an execution-uncertainty hold and require reconciliation/explicit evidence before reusing shares/cash. “No activity exists in the app” is not proof that an external order does not exist. SQLite's transaction model supports the local writer approach; the actual application logic is still to implement. [SQLite transactions](https://sqlite.org/lang_transaction.html).

## R09: Distinguish failure to find a plan from proof there is none

The current language can turn a heuristic search failure into “no feasible plan.” Require separate statuses: incomplete inputs; stale analysis; validated candidate; baseline only/no qualified candidate found; timeout/cancellation; numerically invalid result; and proven infeasibility for the exact qualified model. Only a solver status/proof that applies to that model supports the last claim. Binding-constraint explanations from a heuristic are diagnostics unless proved.

Compute final holdings, fees, cash and NAV from final integer/lot orders; derive weights and TE from that state. A fixed-NAV or other continuous relaxation may be useful for candidate generation, but must be disclosed and revalidated. Validate cost/slippage assumptions, limit residuals and model/input version alignment. Same covariance, different asset ordering must not produce a valid-looking risk number.

The mathematical research base should also inform the formulation. Author summaries of [Tax-Aware Portfolio Construction via Convex Optimization](https://web.stanford.edu/~boyd/papers/tax_aware_portfolio.html) and [Portfolio Construction as Linearly Constrained Separable Optimization](https://stanford.edu/~boyd/papers/portf_constr_lcso.html) discuss tax-lot optimization, relaxations/heuristics and discrete restrictions. Review their assumptions and reference code before inventing a production algorithm. Their tax/trading assumptions and reported performance do not establish household wash-sale compliance or performance for Prosper. Only author summaries/abstracts were reviewed here; no research implementation was reproduced.

## R10: Finish the numeric contract before persisting financial state

For each amount/quantity field define accepted precision, scale/bounds, rounding stage, handling of excess precision and residual allocations. Splitting a lot three ways must conserve its total basis under the supported method. Buying fractional holdings in source data must not turn them into whole shares merely because order generation is whole-share.

Store/transport exact values according to that contract; chart floats and risk arrays are derived values. Financial precision and SQL affinity, serialization, dataframe casts and solver tolerance are different concerns. A successful Decimal round trip does not validate allocations or cash conservation. Choose routine engineering representations in T003 from accepted semantics and actual source precision; unresolved tax-accounting methods require reviewed expectations.

## R11: Restore the application, not only the SQLite file

The proposed state is split across SQLite, raw imported evidence and Parquet/risk inputs. A database backup can be valid while referenced files are missing, or a copied database can be inconsistent with active writes. Use a consistent backup mechanism for SQLite and a versioned application bundle manifest for authoritative referenced evidence. Derived analytical caches can be rebuilt; evidence needed for prior decisions cannot silently be lost. [SQLite backup guidance](https://sqlite.org/backup.html).

Specify staging/publication order for immutable input files and their database references, recovery of orphan/uncommitted files, interrupted migrations, schema compatibility and deliberate retention/export/deletion. Restored outstanding plans are non-actionable until state/coverage/freshness and possible external execution are reconciled. No restore test or database exists yet.

## R12-R14: Deliver a small complete experience before expanding breadth

Add an early paper/manual walkthrough using representative synthetic evidence, including exact lot selection, confirmation and a failed replacement leg. Then build the smallest complete synthetic cycle before broad solver/UI feature depth. Preserve React/Python and the adopted technologies, but instantiate each when its slice needs it. Keep a research notebook dependent on shared core APIs, not a parallel calculation path.

D035 should choose the first supported investor OS and distribution acceptance target. The Windows workspace is not proof of a cross-platform release, nor proof that Windows-only is the right product strategy. Evaluate install/solver-binary capability early; keep full Tauri packaging after the accepted workflow as planned.

Measure import/setup burden, manual orders and lot selections, end-to-end review/reconciliation time, blocked-candidate reasons, exception recovery, runtime, cancellation and baseline risk/cost differences. Assign numeric budgets in the first brief/paper review; they have not been measured and should not be presented as validated promises. A five-minute synthetic interview demo remains distinct from investor task completion and investment performance.

The 14-25 core / 18-32 total engineering-week envelope is a provisional planning estimate, not a forecast supported by velocity or vendor access. Keep it as a scenario until early evidence permits a new estimate. The 20% learning reserve is a ceiling/review budget, not an obligation to spend it or a way to hide required financial-quality work.

## Readiness checkpoints

| Checkpoint | Required evidence | Work it unlocks after explicit implementation authorization |
| --- | --- | --- |
| G0: Synthetic foundation brief | Exact field/cutoff semantics for one synthetic bundle; precision/unknown rules; bounded import/reconciliation and typed UI/API acceptance | First synthetic implementation slice; no financial recommendations |
| G1: Investor/data feasibility | First persona/entry path; one broker mapping/manual-confirmation workflow; permitted benchmark/history/quote plan; paper exception walkthrough | Substantial broker-facing workflow/UI and quantitative build-out |
| G2: Financial/model qualification | Objective/cost semantics, supported tax cases, reviewed household screening cases, risk inputs and discrete formulation, final-state validator | Actionable-candidate feature acceptance in paper mode |
| G3: Pilot readiness | Independent review dispositions, observed paper use, supported install/recovery, actual data authorization and named artifact/use | Owner-authorized financial-use pilot, never inferred from this review |

These checkpoints clarify dependencies in the adopted plan; they do not require choosing every optional feature before G0 or completing a full legal review before a synthetic importer. G1/G2/G3 have not passed.

## Follow-up choices and recommendation

Use the five open decision entries D031-D035 rather than silently altering adopted scope. My recommendations are: an existing-sleeve first pilot; preserve strict limits until its feasibility is demonstrated; define cost-aware minimums and unambiguous objective semantics; initially support a clearly classified subset of ordinary tax cases with explicit exclusions; and select one supported OS before installer promises. These remain recommendations where they change product behavior.

No additional implementation, dependency installation, account access, outbound messages, portfolio collection or publication occurred. Documentation clarification is complete for the identified engineering contracts; all behavioral acceptance and feasibility evidence remains future work.

## Adopted action disposition

| Finding | Planning action now adopted/delivered | Evidence still required |
| --- | --- | --- |
| R01 | G1 moved ahead of substantial broker-facing/quantitative work; four-case paper charter prepared | Qualified broker mapping, source rights/refresh and completed walkthrough |
| R02 | D031 existing qualified stock-sleeve pilot; ETF/cash onboarding deferred | Demand, actual entry fit and manual burden |
| R03 | D032 strict caps/whole shares/zero positive gains retained; no automatic remediation scope | Representative valid/blocked candidate yield and observed usefulness |
| R04 | D033 frozen-reference price/basis objective; costs excluded from reward, explicit budgets/screens, cash/net-P&L equations and V42-V43 | Qualified fee/funding assumptions, investor settings and financial implementation/review |
| R05 | D034 qualified ordinary domestic-corporation common equity; explicit excluded/uncertain cases retain diagnostic NAV | Supported classification/adjustment/holding rules and independent case review |
| R06 | Snapshot inclusion/checkpoint contract and complete F001 included-event example | Import/reconciliation behavior exercised |
| R07 | Both sale and replacement purchase legs screened against household history/restrictions | Reviewed cases and implementation evidence |
| R08 | Frozen generations, atomic approval/reservations, idempotency and uncertain external commitments specified | Concurrency/stale/retry/expiry scenarios exercised |
| R09 | Honest search taxonomy and independent final rounded net-state validation required | Discrete method/solver qualification and numerical acceptance |
| R10 | Canonical decimal TEXT, quantum/bounds, diagnostic residual rule, fee accounting and written numerical cases | Exact round trips and qualified broker production allocation semantics |
| R11 | Consistent database plus referenced evidence recovery manifest; restored plans non-actionable until reconciled | Interrupted publication/backup/update/restore checks |
| R12 | Bounded complete synthetic foundation brief plus early G1 paper charter | First software slice and actual paper execution evidence |
| R13 | D035 Windows x64 first; provisional measurement charter and installation/recovery acceptance | Exact supported versions/runtime/hardware, installer and measured results |
| R14 | Evidence gates, provisional schedule and capped one-track learning reserve preserved | Re-estimate from early slice/data evidence; actual showcase/release acceptance |

All fourteen findings have a documented plan response. None is represented as behaviorally verified or independently reviewed. T001 written planning work is complete; G0 is document-ready in the [foundation specification](../engineering/FOUNDATION_SPEC.md), while G1-G3 remain unpassed. The adopted product choices do not settle the remaining broker/data/solver/license/release details in the decision register.
