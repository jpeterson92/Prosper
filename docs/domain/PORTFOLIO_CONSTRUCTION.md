# Portfolio-construction framework

Status: adopted methodology direction, not an implemented optimizer or validated investment process. See [DECISIONS.md](../DECISIONS.md). Data, estimator settings, discrete solver/candidate method and investor-specific limits still require qualification.

## What must be optimized

Choose which specific stock lots to sell and how to reinvest while staying within the investor's benchmark-relative risk, cash, cost, gain and operational limits. Tax eligibility is a constraint. Investment similarity is a risk-model question. Neither can be substituted for the other.

The initial approach is deliberately bounded: maintain an existing long-only stock sleeve, realize no gains by default, and generate a manageable manual worksheet. An investor starting entirely from cash or selling an appreciated ETF needs a separate transition problem. Avoid implying that v1 solves that transition.

## Benchmark and portfolio state

Use a dated, versioned weighted basket of securities supplied under appropriate data rights. Development uses a synthetic basket. Validate nonnegative weights, identifier resolution, currency, cash treatment, complete coverage and a sum of one within a documented tolerance. Never silently renormalize missing constituents. A supplied custom basket is not automatically equivalent to a named commercial index.

Under D039/[ADR-0004](../architecture/decisions/0004-adopt-holdings-first-inputs.md), optimize and report risk for the **stock sleeve plus the user's selected additional cash budget**. Initial modeled sleeve value is reference-valued included stocks plus that budget. Untouched cash stays outside this denominator, and an unknown whole-account balance stays unknown. Final weights include residual modeled sleeve cash using a common final NAV denominator. Label results stock-sleeve risk, not whole-account/household risk. Outside holdings still inform restrictions and optional diagnostics; they do not silently enter the optimized benchmark or cash budget.

## Risk measurement

For security weights w, benchmark weights b and annualized covariance matrix Sigma, model ex-ante tracking error as:

`TE = sqrt((w - b)' Sigma (w - b))`.

Record annualization, return definition, frequency, lookback, shrinkage/factor method, missing-history handling, corporate-action adjustment, data as-of and model version. Compare like units; monthly covariance cannot be presented as annual without conversion. Validate symmetry, finite entries and positive semidefiniteness. Cash handling must be consistent across weights and covariance.

[D041/ADR-0007](../architecture/decisions/0007-adopt-enhanced-dcc-nl-industry-risk.md) selects enhanced DCC-NL, targeting IDR-DCC-NL with qualified OHLC and analytical nonlinear shrinkage. Standard DCC-NL is the named qualification reference. Validate the selected variant, fit constraints, published recursions, coherent source/return/proxy units and forward horizons before calling a plan risk-constrained. A failed fit or unavailable input cannot silently switch models. Detailed settings, source coverage and actual TE calibration remain qualification work.

The adopted direction is enhanced DCC-NL/industry risk, focused marimo qualification and CVXPY/Clarabel for continuous reference/relaxation problems; the [technology comparison](../architecture/TECHNOLOGY_TRADEOFFS.md) records the reasoning. A hard TE cap and integer shares/order indicators require a suitable mixed-integer nonlinear/conic formulation or a documented candidate/repair method. Clarabel alone does not solve that complete discrete problem. SCIP and other appropriate backends remain qualification candidates; separate MIP and QP support must not be mistaken for support of their combination.

Active weights and sector differences are useful diagnostics but are not tracking error. A missing or invalid covariance model blocks a TE-constrained actionable plan. There is no silent fallback to sector similarity. Historical realized tracking error, if later reported, is a separate backward-looking statistic with dates and data coverage.

## Sector and industry risk

Use versioned sector/industry mappings to show portfolio, benchmark and active weights and validate explicitly selected absolute/active exposure limits. Unknown/reclassified names retain their source/effective/known-time evidence and scoped constraint blockers. No taxonomy or threshold is invented.

For the same horizon covariance `C` used for TE and active weights `a`, signed security Euler contribution is `a[i] * (C a)[i] / sqrt(a' C a)` when TE is positive. Group contributions sum their securities and reconcile to total TE; negative contributions represent risk offsets. Define zero-TE/percentage behavior without division by zero. Standalone group risks and cross-group terms are separate, non-additive diagnostics; sector and nested industry views are not added. These are covariance-based group contributions, not estimated causal sector factors or another covariance to add to total risk.

Pin daily versus review-horizon forecasts and the annualization/fixed-weight approximation from ADR-0007. The same stock-sleeve-plus-selected-cash denominator, complete universe and qualified benchmark/cash treatment apply to baseline, candidate and group metrics. T007 independently rechecks final TE and group limits after rounding/costs.

## Adopted first objective

Initially maximize **eligible price/basis loss dollars at reference marks** under independently checked hard constraints. Report ST and LT losses separately. This is a transparent loss-harvesting objective, not a full tax-utility optimizer. If the owner wants tax-dollar optimization instead, define scenario inputs, capital netting and objective semantics in a new decision before changing behavior.

The critical review's D033 recommendation is now adopted. The primary objective is eligible **price/basis loss measured at reference prices**, with transaction costs excluded from the objective reward. Indicative tax P&L using net proceeds is a separate amount. Feasibility alone does not establish economic attractiveness; apply the explicit budgets and optional investor economic screens below. Lower modeled cost, then fewer orders, then stable identifiers break ties in the primary objective. This remains loss harvesting under constraints, not a personalized tax-utility optimizer.

## Objective, cost and cash semantics

For a sold lot portion, let `B` be its supported allocated adjusted basis, `q` its quantity, and `m` the frozen reference mark. Its objective contribution is `max(B - q*m, 0)`, only after eligibility checks. Sum these contributions across sales and keep ST/LT reporting separate. Reference-positive-gain sales are excluded by the zero-positive-gain policy; estimated net-proceeds gains must also pass that policy. Do not sell a reference-gain lot solely because fees might turn it into a modeled loss. A harvest candidate must have positive total eligible price loss; no-trade remains the baseline.

Indicative execution prices incorporate the declared spread/impact assumptions: conservative sell `p_sell <= m`, buy `p_buy >= m`. Net sell proceeds are `q*p_sell - explicit_sell_fees`; indicative tax P&L is net proceeds minus `B`. Acquisition fees contribute to modeled replacement basis when appropriate, but only actual qualified source evidence establishes authoritative executed basis.

For the modeled sleeve, cash is `cash_to_invest + gross_indicative_sell_proceeds - sell_fees - gross_indicative_buy_principal - buy_fees`, with separate reservation/funding checks. `cash_to_invest` is the user's reviewed maximum additional-cash budget, allowing zero, not a claim that total account cash is zero. Broker cash import is optional. Show imported/reported cash separately when supplied, always allow the run budget to be edited, and never overwrite source balances with that selection. Default an unset selection to visible zero, not the full imported balance. Sales can fund replacements even at zero additional budget; whole shares/costs may leave residual cash. Do not add a hidden spending reward or force exact budget consumption. Modeled cost is the reference-to-indicative spread/impact difference plus explicit fees on both sides. Embedded spreads and fees are not double counted. Use final reference-valued holdings plus residual sleeve cash for final NAV/risk; report actual account reconciliation separately.

Loss opportunity/solver validity, wash-sale verification and operational funding are separate states. D038 permits conditional optimization with incomplete history and explicit warnings/manual restrictions, without certifying deductible loss. Known conflicts, unsupported tax facts, missing affected-lot basis, contradictory holdings, invalid risk inputs and unfunded orders remain scoped blockers. The primary objective is unchanged; positive extra cash affects feasible replacement holdings/weights rather than directly rewarding harvested loss.

An actionable profile explicitly supplies risk/cash limits, maximum cost, maximum turnover/orders and minimum order notional. Optional minimum price-loss, maximum cost-to-price-loss ratio and illustrative scenario-value screens record enabled/disabled state and their investor-entered values. There are no implicit personalized dollar/rate defaults; missing required settings blocks actionable generation. A cost-to-loss ratio compares cost with loss dollars, not with tax savings. A tax-value screen is available only under an explicit user-supplied loss-utilization scenario; never infer immediate tax value or permanent savings.

Declare the modeled fee-allocation and exact-value method before financial use and reconcile it with the qualified broker/reviewed tax rules. The [foundation numeric contract](../engineering/FOUNDATION_SPEC.md) defines the first schema's engineering precision and a synthetic diagnostic allocation rule; it is not a universal tax/broker convention.

Generate a few feasible points across owner-approved harvest/risk/cost budgets rather than an uncalibrated single score combining dollars, variance and turnover. Keep a no-trade baseline. Optional later formulations can minimize TE for a specified loss target. Do not mix units with arbitrary unexplained penalty coefficients.

## Hard constraints

| Constraint | Adopted treatment |
| --- | --- |
| Lot availability | Sell quantities cannot exceed unreserved eligible shares in exact identified lots |
| Wash-sale restrictions | Exclude known-conflict sales, prohibited buys and unresolved affected identities; account for outstanding restrictions |
| No simultaneous churn | No buy and sell of the same security in a plan; cross-plan reservations prevent duplicate use |
| Cash | Final cash follows the explicit indicative cash-flow equation and stays above the configured floor after reservations; do not count embedded costs twice; no borrowing |
| Gain budget | Zero gross realized positive gains initially, checked per sold lot rather than allowing losses to hide gains |
| Risk | Post-trade TE <= approved cap, plus security, sector and other accepted exposure bounds |
| Trading | Whole-share orders initially, minimum notional, maximum orders and turnover, restricted/no-buy/no-sell names |
| Universe | Only explicitly eligible candidates with reviewed identity and complete required risk inputs |
| Prices | Dated and fresh enough for the plan; stale/inconsistent inputs invalidate actionability |
| Operational funding | Respect specified sell/buy sequence and available/settled-cash evidence for selected broker/account |

All numerical investor limits must be explicit settings and copied into the plan. Examples in documentation are not production defaults. If the existing portfolio breaches a limit, report it. D032 permits only candidates satisfying the strict adopted caps and zero-positive-gain policy; otherwise return the appropriate no-qualified-candidate or evidenced infeasibility result. Do not present the breached no-trade baseline as feasible or introduce an automatic remediation policy.

## Solver strategy and independent validation

1. Build a tiny reference problem with known PSD covariance, reviewed eligible lots and enumerable whole-share outcomes. Establish expected best/feasible results before selecting a production solver.
2. Separate security allocation from lot selection where appropriate, recognizing that whole shares, lot tax economics and max-order constraints make the full problem discrete. A continuous convex solution is only a relaxation, not an executable plan.
3. Evaluate a transparent deterministic heuristic or a suitable discrete solver at the target scale. Record status, runtime, seed/tie-breaking, tolerances and optimality gap where available. Do not claim global optimality for a heuristic.
4. Round/repair into valid whole-share orders and repeat all checks. A plan that passed before rounding can fail afterward.
5. Pass the result through an independent validator that recomputes lots, cash/costs, gain budget, restrictions, exposures and TE from canonical inputs. Do not accept the solver's feasibility flag as sufficient evidence.
6. On timeout, invalid numeric output, infeasibility or material residuals, return a diagnostic/non-actionable result. A feasible incumbent can be shown only if the independent validator passes and the incomplete search is disclosed.

No candidate found by a heuristic/limited search is a different outcome from proven infeasibility. Record the exact model, method, status, stopping condition and residuals. A valid no-trade baseline is different from a baseline that already breaches a limit. Recompute final cash, fees, NAV, weights and TE from final whole-share/lot orders; a fixed-NAV or continuous approximation cannot certify the final state. Input asset ordering and every referenced version must match the validator's data.

Before production formulation, compare assumptions with the primary research summaries for [tax-aware convex portfolio construction](https://web.stanford.edu/~boyd/papers/tax_aware_portfolio.html) and [separable portfolio optimization](https://stanford.edu/~boyd/papers/portf_constr_lcso.html). Their approaches are research references, not adopted algorithms or evidence of Prosper's compliance/performance. Do not copy a monthly-trading/no-simultaneous-buy-sell assumption as a complete household wash-sale rule.

The reference validator should not reuse the same constraint-building functions whose errors it is intended to catch. Shared basic decimal/identifier primitives are acceptable, while independently computed expected outputs remain necessary.

## Execution assumptions

Manual sell/buy legs are not atomic. Use costs and cash reserves, explicit dependency ordering, quote/plan expiry and low order-count constraints. Do not assume unsettled sale proceeds are always available or safe to reuse; qualify the selected account's funding workflow. A sell that fills without its replacement leaves exposure and cash that require review. Generate a new candidate from actual reconciled state, not an automatic retry of the original worksheet.

Initial monitoring does not force a buyback after the wash window. Re-entry into the original name must be a new portfolio/tax decision using updated lots and restrictions. Cross-year windows remain open across December/January.

## Research and economic evaluation

Backtesting is a later research capability, not the first product. When introduced, use point-in-time universes, delisted names, realistic actions/prices/spreads, flows, dividends, restrictions and tax scenarios. Compare with a defined tax-unaware maintenance policy and a no-harvest benchmark; match pre-tax risk and costs. Report terminal tax assumptions, loss utilization, turnover and implementation shortfall. Do not use today's constituents for a historical survivorship-free claim, or present a backtested loss total as incremental after-tax return.

The [validation plan](../engineering/VALIDATION.md) specifies reference expectations and failure cases required before this methodology is accepted.
