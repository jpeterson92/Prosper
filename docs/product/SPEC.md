# Product specification

Status: adopted product-planning baseline, October 22, 2026. See [decisions](../DECISIONS.md) and [ADR-0001](../architecture/decisions/0001-adopt-project-architecture.md). Requirements are accepted direction, not evidence of implemented or qualified behavior.

## User and job

The primary user is a sophisticated individual investor who understands taxable investing, chooses a benchmark and risk budget, and can place specific-lot stock trades. The product should let that investor operate a repeatable process without programming or hiring a portfolio manager. An accountant may review exported evidence but is not assumed to operate the software.

The first job is maintaining an existing direct-indexing sleeve. The investor already owns individual stocks, wants to realize selected losses, and wants to understand the cost and risk of the resulting holdings relative to their benchmark. The product does not choose their financial goals or determine suitability.

D031 adopts an initial pilot who already owns a qualified stock sleeve and can provide supported lot and household evidence. Demand, acceptable manual burden and usability remain unvalidated; ETF/cash onboarding is deferred. Before a broad workflow build, walk through representative synthetic broker/lot/confirmation evidence and record setup, review, execution and recovery effort.

## First-release scope

| Area | Included in adopted initial-release scope | Deferred or blocked |
| --- | --- | --- |
| Traded assets | Long-only USD U.S.-listed ordinary domestic-corporation common equity with qualified tax evidence, plus explicit cash | Options, shorts, margin borrowing, funds as replacement holdings, ADR/foreign tax issues, crypto, preferred/convertible securities |
| Accounts | One taxable account for orders; other relevant accounts tracked for conflicts | Coordinated multi-account trade optimization; uncertain ownership relationships require review |
| Lots | Identified open lots with authoritative adjusted basis and holding-period evidence | Unknown basis, unresolved transfers, average-cost ambiguity, unsupported corporate actions |
| Quantities | Decimal ingestion preserves all shares; whole-share proposed orders initially, with fractional residuals retained | Fractional order generation until a selected broker workflow is qualified |
| Portfolio | Existing stock sleeve, supplied benchmark, explicit restrictions and risk limits | ETF liquidation, concentrated-position transitions, leverage, complex funding and withdrawal optimization |
| Connectivity | Generic files, one qualified broker-specific workflow when selected | Credentials, scraping, order APIs, unattended trading |
| Taxes | Federal loss economics and conservative conflict screening for supported cases | Tax filing, complete household tax return, state calculations, legal clearance of every security relationship |
| Access | Local single-user review and reports | Multi-user hosted service, advisor platform, remote sharing |

Unsupported assets in other accounts may still affect the traded sleeve. The product must capture their existence and block affected recommendations when their relevance cannot be assessed. Excluding options from order generation does not make their wash-sale implications disappear.

D034 adopts qualified ordinary domestic-corporation common equity cases. REIT/RIC/BDC, partnership, ADR/foreign and uncertain classifications are excluded from actionable generation initially; unsupported distributions, corporate actions or holding-period events block affected recommendations. Preserve their quantities, NAV and diagnostics. Unbounded dependency impact blocks the account-level plan. See the [tax policy](../domain/TAX_POLICY.md); a ticker or acquisition date cannot replace required classification, adjusted basis or holding-period evidence.

## Investor workflow

### 1. Establish a portfolio profile

Choose the traded account, benchmark, candidate universe, restricted names, cash floor, security/sector limits, tracking-error budget, trade-count limit, turnover and transaction-cost assumptions. Record federal jurisdiction/tax-year assumptions and household monitoring scope. The default realized-gain budget is zero; enabling gains is an explicit change with separate acceptance.

The application displays what information it requires and why. It distinguishes a real imported portfolio from the synthetic demonstration portfolio. It does not prefill unverified tax rates or present tax estimates as personalized liabilities.

### 2. Import and reconcile

Preview holdings, lots, activity, cash, benchmark and market data before committing an import. Show source dates, import dates, rejected rows and duplicate/correction handling. Reconcile quantities, basis scope and cash to source snapshots. Show gaps in activity coverage and automatic purchases, including reinvestments and employee-plan activity.

The investor must see an explicit readiness status. Missing data permits exploratory diagnostics labeled as incomplete, but blocks an actionable plan. A repeated snapshot cannot add another copy of the same holdings or trades.

### 3. Inspect opportunities and baseline risk

Show loss opportunities by exact lot, short/long-term status or unknown, economic amount, tax screening status and reason. Display the no-trade portfolio's active security and sector weights, modeled tracking error and existing limit breaches. Distinguish negative unrealized P&L from a loss currently eligible for a proposed harvest.

Show household coverage by account and time range. User attestations can document activity in an unconnected account but are dated assumptions with a defined scope, not permanent declarations that the household is clear.

### 4. Compare plans

Present the no-trade baseline and a small set of harvest candidates. Each candidate shows exact lots sold, purchases, estimated cash after costs, ST/LT losses, modeled allowable losses, estimated cost, trade count and before/after risk. Show which restrictions bind and why a higher-loss plan was rejected.

A replacement can be a basket of stocks. A sector peer is a portfolio choice subject to risk validation and tax-identity review; the software must not invent a universally safe one-for-one replacement. The optimizer cannot clear its own output without an independent deterministic validator.

The headline is a loss/risk/cost tradeoff. A tax-dollar scenario is optional and visibly conditional. It does not imply an immediate refund, permanent savings or validated tax alpha.

D033 adopts eligible price/basis loss at frozen reference marks as the objective; costs cannot increase the reward. Report indicative net-proceeds P&L, modeled costs and cash separately. Require explicit cost/turnover/order/notional budgets and explicit enabled/disabled choices for optional minimum-loss, cost-to-loss and illustrative utilization screens; no invented investor defaults. The [portfolio contract](../domain/PORTFOLIO_CONSTRUCTION.md) defines the equations. D032 retains strict risk caps and zero positive gains for the first pilot; explain unavailable candidates and existing breaches. Do not silently relax constraints to make the demo produce trades.

### 5. Review and execute manually

Approve a named immutable plan version. The worksheet shows account alias, security identifiers, side, quantity, exact sell-lot references and quantities, expected prices/timestamps, restrictions, expiry, and the user's chosen execution assumptions. It instructs the investor to verify specific-lot selection and broker confirmation. It is labeled **manual execution worksheet**, not an executable broker order file.

Plans expire on material input changes and a short configured freshness horizon. The application requires updated data/revalidation after expiry. The precise quote/plan horizon and trade-count limit are decisions to calibrate through observed paper workflows.

Recommendation expiry does not cancel an external order or prove available shares/cash. If the investor may have submitted a worksheet, show execution status as unknown and retain the corresponding commitment until reconciled. A locally approved plan is conditional guidance under stated data/price assumptions; the application cannot prevent separate brokerage activity or guarantee fill-time risk limits.

The investor may reject or alter a plan. Editing quantities creates a new candidate that must pass all validations; an approved plan is not modified in place.

### 6. Reconcile and monitor

Import fills, cancellations, broker-confirmed lot allocations and new account snapshots. Record deviations from proposed prices/quantities; do not treat an approved worksheet as an executed transaction. Partial or failed replacement purchases create an explicit risk/cash review item. Lot-allocation mismatches block completed reconciliation.

Track the actual sold securities and dates through the forward wash window. Imported new activity can revise previously provisional outcomes. A local application cannot monitor while closed; it must show the last review and required next check, with an optional calendar export considered later. No background notification capability is assumed.

After the window closes, label results as reconciled under the documented coverage and assumptions. The product does not certify the user's return. Year-end reconciliation compares available broker records and flags differences; it does not write tax forms in the first release.

## Readiness and failure behavior

| Condition | User-visible result |
| --- | --- |
| Missing basis or ambiguous lot identity | Affected lot cannot be proposed for sale |
| Position/lots disagree | Block account-level actionable plan until reconciled |
| Missing relevant household activity | Show unknown coverage and block affected actionable plan |
| Recent known conflicting acquisition | Explain conflict; conservative initial policy excludes affected security from harvest |
| Unknown tax identity relation | Block affected replacement/candidate relationship pending review |
| Missing/invalid risk model or benchmark | Show available diagnostics; block risk-constrained actionable plans |
| No feasible plan | Explain binding constraints and return no action; no silent relaxation |
| Limited search found no candidate | State that no qualified candidate was found under that search; do not claim proof of infeasibility |
| Stale/late analysis result | Preserve diagnostic evidence, require fresh analysis before approval, and do not reuse old reservations |
| Existing portfolio outside risk limits | Show the breach; only propose a candidate satisfying the strict caps and zero-gain policy; otherwise return an honest no-action/search outcome |
| Partial fills, new trades or revised data | Reconcile actual state and invalidate dependent outstanding candidates |

## Concrete success case

Use synthetic stocks SAAA, SBBB and SCCC and a synthetic benchmark. An old lot of 100 SAAA shares has total adjusted basis $10,000 and price $80, giving $2,000 unrealized loss before costs. Its recent activity is clear under declared coverage. A valid candidate sells this lot and allocates proceeds to permitted SBBB/SCCC quantities while meeting all risk, cash and trade constraints. The report preserves the actual lot identity, records the conditional loss, and compares the resulting risk with no action.

Changing one fact must change the result: a recent SAAA reinvestment blocks that harvest under the initial conservative policy; a stale quote invalidates the worksheet; a broker fill assigned to another lot prevents completed reconciliation. These outcomes are required even if the apparent headline loss becomes less attractive.

## User acceptance questions

- Can a new user establish data readiness and understand every unresolved item?
- Can the user explain why each sale/replacement was selected and how benchmark risk changed?
- Can the user execute the small worksheet in the selected broker's paper/manual workflow and confirm the intended lots?
- Can the user reconcile partial fills and discover a later conflicting purchase?
- Can the user recover local state and produce useful diagnostics without exposing holdings?

Observed paper sessions and independent case review are required before claims of usability or financial reliability. No such acceptance has occurred.

Record input-assembly time, unresolved-data count, blocked-candidate causes, order/lot-selection burden, review/reconciliation time and exception recovery. Windows x64 is the first release target under D035. Qualify exact supported OS/browser/runtime versions and document installation/recovery. Use the provisional targets in the [measurement charter](../engineering/VALIDATION.md) during early paper qualification, then revise them from evidence; none have been measured. A five-minute synthetic interview demo is distinct from an investor completing the workflow. See the [critical review](../reviews/2026-10-22-pre-implementation-review.md) for staged readiness checkpoints and open decisions.
