# Product specification

Status: adopted product-planning baseline, October 22, 2026, amended by the owner's October 23 [holdings-first and selected-cash direction](../architecture/decisions/0004-adopt-holdings-first-inputs.md) (D038-D039). See [decisions](../DECISIONS.md) and [ADR-0001](../architecture/decisions/0001-adopt-project-architecture.md). Requirements are accepted direction, not evidence of implemented or qualified behavior.

Current first-release contract: [D046/ADR-0012](../architecture/decisions/0012-adopt-proportional-advisory-scope.md). Estimated suggestions end at save/manual export; execution tracking, reconciliation and monitoring are deferred. See [numeric](../engineering/ADVISORY_NUMERICS.md) and [record](../architecture/DATA_CONTRACTS.md) contracts. T019 changes requirements before runtime remediation; implemented behavior remains in STATUS.

## User and job

The application has never been released. [D047](../architecture/decisions/0013-adopt-unreleased-clean-break-development.md) removes backward compatibility with previous implementations from every future feature's scope. Current-format saved results, financial correctness, privacy and recovery retain their user purpose; old schemas/APIs/readers/backups need not be supported or migrated.

The primary user is a sophisticated individual investor who understands taxable investing, chooses a benchmark and risk budget, and can place specific-lot stock trades. The product should let that investor operate a repeatable process without programming or hiring a portfolio manager. An accountant may review exported evidence but is not assumed to operate the software.

The first job is maintaining an existing direct-indexing sleeve. The investor already owns individual stocks, wants to realize selected losses, and wants to understand the cost and risk of the resulting holdings relative to their benchmark. The product does not choose their financial goals or determine suitability.

D031 adopts an initial pilot who already owns a qualified stock sleeve and can provide supported lot and household evidence. Demand, acceptable manual burden and usability remain unvalidated; ETF/cash onboarding is deferred. Before a broad workflow build, walk through representative synthetic broker/lot/confirmation evidence and record setup, review, execution and recovery effort.

## First-release scope

| Area | Included in adopted initial-release scope | Deferred or blocked |
| --- | --- | --- |
| Traded assets | Long-only USD U.S.-listed ordinary domestic-corporation common equity with qualified tax evidence, plus explicit cash | Options, shorts, margin borrowing, funds as replacement holdings, ADR/foreign tax issues, crypto, preferred/convertible securities |
| Accounts | One taxable account for orders; relevant other-account facts supplied for conflict screening | Coordinated multi-account trade optimization; uncertain ownership relationships require review |
| Lots | Distinguishable open lots with source-reported total basis as a disclosed starting assumption; preserve supplied holding-period evidence | Unknown/disputed basis, ambiguous sale lots, unresolved transfers, average-cost ambiguity, unsupported corporate actions; unknown term stays unknown |
| Quantities | Decimal ingestion preserves all shares; whole-share proposed orders initially, with fractional residuals retained | Fractional order generation until a selected broker workflow is qualified |
| Portfolio | Existing equity sleeve with an equity-only benchmark, explicit exclusions/restrictions/risk limits, initial cash budget and optional final cash target | ETFs, bonds and other unsupported instruments as modeled holdings; ETF liquidation/transitions, leverage and complex funding/withdrawal optimization |
| Connectivity | Generic files, one qualified broker-specific workflow when selected | Credentials, scraping, order APIs, unattended trading |
| Taxes | Estimated federal loss economics and conservative conflict screening for supported cases | Tax filing, complete household tax return, state calculations, legal clearance of every security relationship |
| Access | Local single-user review and reports | Multi-user hosted service, advisor platform, remote sharing |

Unsupported assets in other accounts may still affect the traded sleeve. The product must capture their existence and block affected recommendations when their relevance cannot be assessed. Excluding options from order generation does not make their wash-sale implications disappear.

D034 adopts qualified ordinary domestic-corporation common equity cases. REIT/RIC/BDC, partnership, ADR/foreign and uncertain classifications are excluded from actionable generation initially; unsupported distributions, corporate actions or holding-period events block affected recommendations. Preserve their quantities and diagnostic observations; D045 excludes unsupported/unmapped rows from the modeled sleeve. Unbounded dependency impact blocks the account-level plan. See the [tax policy](../domain/TAX_POLICY.md); a ticker or acquisition date cannot replace required classification, adjusted basis or holding-period evidence.

## Investor workflow

### 1. Establish a portfolio profile

Choose the traded account, benchmark, candidate universe, restricted names, cash floor, security/sector limits, tracking-error budget, trade-count limit, turnover and transaction-cost assumptions. Record federal jurisdiction/tax-year assumptions and the scope of supplied household screening facts. The default realized-gain budget is zero; enabling gains is an explicit change with separate acceptance.

The standard benchmark flow selects a supported Vanguard ETF and its actual reported full-portfolio date through the local backend. Preserve all source rows/unknowns and reconcile duplicate/alternate representations, then show retained mapped equities and explicit unsupported/unmapped exclusions with counts, reasons and known values/unknowns. Under [D045/ADR-0011](../architecture/decisions/0011-adopt-equity-only-scope-and-final-cash-target.md), the modeled benchmark is the retained equity subset rescaled by retained market values to approximately 100% under the numerical contract. Label it an equity-only disclosed-holdings proxy. No fund is preselected; creation/redemption baskets and silent source/date fallback are forbidden. Preview/review precedes frozen activation; refresh preserves old versions. Manual/custom files remain explicit secondary routes. Source-controlled demonstrations/tests remain invented and offline; selector/activation qualification is still pending.

D045 retains E, the sum of supported mapped primary equity values, as the marketValue/E denominator. D046 uses Float64 derived weights with tested tolerances, preserving original source/exclusion information without universal rational/token proofs. Missing/contradictory included facts or nonpositive E block the dependent result. Excluded instruments require no modeled returns and create no inferred cash. Existing [synthetic exact-ratio evidence](../tasks/T006.1.8.2-source-qualification.md#october-25-synthetic-equity-only-transformation-execution) remains evidence of that older implementation, not the new numeric acceptance criterion.

The application displays what information it requires and why. It distinguishes a real imported portfolio from the synthetic demonstration portfolio. It does not prefill unverified tax rates or present tax estimates as personalized liabilities.

### 2. Import and reconcile

Accept a lot-level holdings file as the normal entry point. Preview supplied holdings, lots, activity and cash, with source/import dates, rejected rows and duplicate/correction handling. Form a derived holdings view from lots when no separate position export exists; label it as derived. Compare independent snapshots when supplied and preserve genuine disagreements. Supplement the broker file with account/currency/as-of confirmation, supported security resolution, permitted application market/benchmark/risk data and user settings. Full transaction history, a separate position file, durable broker lot IDs and account cash are not mandatory broker-file fields.

Show separate readiness for financial/risk feasibility, wash-sale verification and execution funding. Missing basis, unresolved identity, contradictory holdings or invalid risk inputs block their affected scope. Missing history permits conditional optimization with a persistent unverified-wash-sale warning; it does not prove a clean household. Offer an optional list of recently traded/restricted names. Names alone conservatively exclude that resolved security from both sales and replacement buys for the run; dates, direction and account details are optional refinements. Preserve known conflicts even when omitted from the list. An empty list never validates history. Show gaps in automatic and household activity, including reinvestments. A repeated snapshot cannot add another copy of the same holdings or trades.

Before every optimization, show the optional imported cash fact and a separate editable **additional cash to invest** field. Start an unset selection visibly at zero; let the user select none, part or another supported amount regardless of the imported balance. Preserve the original balance and label manually supplied funding assumptions. The selection is a spending cap, so costs/whole shares may leave a residual. Zero selected cash still permits replacements funded by net sale proceeds. Risk and benchmark comparisons cover the **stock sleeve plus selected cash**, with untouched account cash outside that scope. Report expected deployment, residual cash, costs and funding uncertainty before approval; do not promise that unverified or unsettled funds are available.

Also offer an optional **final cash balance target**, separately from the initial additional-cash budget and imported balance. It can request raising cash from eligible sales or reinvesting selected available cash. Review/freeze target enabled state, exact amount/currency and explicit tolerance/constraint treatment; show expected final cash and any mismatch. Costs, whole shares, zero-positive-gain, risk and funding constraints still apply; an unattainable target does not authorize relaxed caps or gain sales. No implicit final target or instruction to spend the entire account balance is adopted. Unsupported/unmapped holdings remain visible as excluded observations and retain applicable tax/conflict effects; D034 actionable eligibility remains separate. These are future controls, not existing UI behavior.

### 3. Inspect opportunities and baseline risk

Use the [D041 enhanced DCC-NL direction](../architecture/decisions/0007-adopt-enhanced-dcc-nl-industry-risk.md), with qualified OHLC enhancement and an integrated sector/industry framework. Show the model variant, data cutoff, forecast horizon and quality; missing/failed fits remain unavailable. Display portfolio/benchmark/active sector and industry weights, selected limit breaches and signed contributions to total tracking error from that same risk estimate. Explain risk-reducing contributions and distinguish standalone group risk from additive contributions. Sector/industry names and dates retain their source/version; unknown classifications cannot silently disappear. Investors choose explicit limits; no default risk caps or automatic relaxation are adopted. These are accepted requirements, not implemented controls.

Reuse previously downloaded market history across portfolio reviews and application restarts. When the user returns later or changes portfolios, download the missing dates/new securities needed for the requested risk window, with the qualified source-revision checks, and recompute risk from the combined frozen history. Display last usable history date, last successful refresh and unresolved coverage. Complete eligible cached inputs can be used offline with their cutoff visible; stale or missing required inputs retain their risk/freshness blockers. History refresh does not replace current reference-quote qualification. [ADR-0006](../architecture/decisions/0006-adopt-persistent-market-history-cache.md) records this adopted engineering feature; the persistent cache and UI are future implementation.

Offer manual refresh of selected/all required securities and reuse compatible history with gap/overlap/revision checks. Show last usable date, last refresh and unresolved quality issues. Background validation scheduling and persistent scheduling/dispatch controls are deferred under D046; manual refresh never implies that unfetched past revisions have been detected.

Show loss opportunities by exact lot, short/long-term status or unknown, economic amount, tax screening status and reason. Display the no-trade portfolio's active security and sector weights, modeled tracking error and existing limit breaches. Distinguish negative unrealized P&L from a loss currently eligible for a proposed harvest.

Show household coverage by account and time range. User attestations can document activity in an unconnected account but are dated assumptions with a defined scope, not permanent declarations that the household is clear.

### 4. Compare plans

Present the no-trade baseline and a small set of harvest candidates on the same stock-sleeve scope. Each candidate shows exact lots sold, purchases, selected/used/residual cash after costs, ST/LT or unknown-term losses, history-verification status, estimated cost, trade count and before/after risk. Only label modeled allowable losses where evidence supports that calculation; conditional history results remain unverified and never become confirmed deductible losses. Show which restrictions bind and why a higher-loss plan was rejected. Unknown term need not prevent the unweighted loss-dollar objective when ordinary supported basis/identity facts are sufficient; do not invent holding classification.

A replacement can be a basket of stocks. A sector peer is a portfolio choice subject to risk validation and tax-identity review; the software must not invent a universally safe one-for-one replacement. The optimizer cannot clear its own output without an independent deterministic validator.

The headline is a loss/risk/cost tradeoff. A tax-dollar scenario is optional and visibly conditional. It does not imply an immediate refund, permanent savings or validated tax alpha.

D033 adopts eligible price/basis loss at frozen reference marks as the objective; costs cannot increase the reward. Report indicative net-proceeds P&L, modeled costs and cash separately. Require explicit cost/turnover/order/notional budgets and explicit enabled/disabled choices for optional minimum-loss, cost-to-loss and illustrative utilization screens; no invented investor defaults. The [portfolio contract](../domain/PORTFOLIO_CONSTRUCTION.md) defines the equations. D032 retains strict risk caps and zero positive gains for the first pilot; explain unavailable candidates and existing breaches. Do not silently relax constraints to make the demo produce trades.

### 5. Review and execute manually

Review and save/export a dated suggestion, with account alias, security/lot identifiers, whole-share quantities, indicative prices/costs/loss/risk/cash, restrictions, data dates and assumptions. Independently validate final orders before calling the suggestion valid. Editing quantities produces a new checked result. Label it a manual execution worksheet; no executable broker orders or execution status are produced.

A saved/exported result does not reserve shares/cash or imply submission/fills. Changed inputs/settings or stale reference data require fresh analysis for reuse; saved historical outputs remain readable. The investor checks current prices, lot selection and funding at the broker. No claim is made that modeled estimates will hold at fill time.

### 6. Reconcile and monitor

Deferred from the first release: fill/order reconciliation, account/basis reconstruction and forward monitoring. V1 does not infer execution from a worksheet, maintain reservations or certify future wash-window completion. User-facing reminders can describe required external review without claiming to perform it.

After external trading or other account changes, import a fresh holdings/lot snapshot and relevant screening facts before another suggestion. This is a new starting snapshot, not replay of intended trades. Imported source facts and old suggestions remain available for explanation; no authoritative tax ledger is maintained.

## Readiness and failure behavior

| Condition | User-visible result |
| --- | --- |
| Missing basis or ambiguous lot identity | Affected lot cannot be proposed for sale |
| Position/lots disagree | Explain the discrepancy; block dependent suggestions if its impact cannot be bounded, while retaining available diagnostics |
| Missing relevant household activity/history | Persistent unverified-wash-sale warning; allow conditional optimization under disclosed assumptions and optional manual restrictions; never claim clearance |
| Unknown holding period without a known unsupported event | Preserve unknown term; allow supported loss-dollar calculation without ST/LT or tax-dollar claims |
| No account cash supplied | Keep observed cash unknown; review selected additional cash budget, including zero, separately |
| Recent known conflicting acquisition | Explain conflict; conservative initial policy excludes affected security from harvest |
| Unknown tax identity relation | Block affected replacement/candidate relationship pending review |
| Missing/invalid risk model or benchmark | Show available diagnostics; block risk-constrained actionable plans |
| No feasible plan | Explain binding constraints and return no action; no silent relaxation |
| Limited search found no candidate | State that no qualified candidate was found under that search; do not claim proof of infeasibility |
| Stale/late analysis result | Retain the historical estimate, require fresh analysis before reuse, and do not let a late result replace newer inputs |
| Existing portfolio outside risk limits | Show the breach; only propose a candidate satisfying the strict caps and zero-gain policy; otherwise return an honest no-action/search outcome |
| Partial fills, new trades or revised data | Require a refreshed snapshot and analysis; keep old suggestions historical |

## Concrete success case

Use synthetic stocks SAAA, SBBB and SCCC and a synthetic benchmark. An old lot of 100 SAAA shares has total adjusted basis $10,000 and price $80, giving $2,000 unrealized loss before costs. Its recent activity is clear under declared coverage. A valid candidate sells this lot and allocates proceeds to permitted SBBB/SCCC quantities while meeting all risk, cash and trade constraints. The report preserves the actual lot identity, records the conditional loss, and compares the resulting risk with no action.

Changing one fact must change the result: a recent SAAA reinvestment blocks that harvest under the initial conservative policy; a stale quote invalidates the worksheet; a new holdings snapshot requires a new analysis rather than treating an old worksheet as executed state. These outcomes are required even if the apparent headline loss becomes less attractive.

## User acceptance questions

- Can a new user establish data readiness and understand every unresolved item?
- Can the user explain why each sale/replacement was selected and how benchmark risk changed?
- Can the user execute the small worksheet in the selected broker's paper/manual workflow and confirm the intended lots?
- Can the user refresh holdings and relevant screening facts after activity without replaying a previous worksheet?
- Can the user recover local state and produce useful diagnostics without exposing holdings?

Observed paper sessions and independent case review are required before claims of usability or financial reliability. No such acceptance has occurred.

Record input-assembly time, unresolved-data count, blocked-candidate causes, order/lot-selection burden, review/refresh time and recovery of saved results. Windows x64 is the first release target under D035. Qualify exact supported OS/browser/runtime versions and document installation/recovery. Use the provisional targets in the [measurement charter](../engineering/VALIDATION.md) during early paper qualification, then revise them from evidence; none have been measured. A five-minute synthetic interview demo is distinct from an investor completing the workflow. See the [critical review](../reviews/2026-10-22-pre-implementation-review.md) for staged readiness checkpoints and open decisions.
