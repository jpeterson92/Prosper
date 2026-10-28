# Portfolio-construction framework

Status: adopted methodology direction, not an implemented optimizer or validated investment process. Use the current [product](../product/SPEC.md), [market inputs](BENCHMARK_INPUTS.md), [risk](RISK_MODEL.md) and [numerics](../engineering/ADVISORY_NUMERICS.md) contracts; no ADR reading is required. Data, estimator settings, discrete solver/candidate method and investor-specific limits still require qualification.

The [current product workflow](../product/SPEC.md) and [numerical contract](../engineering/ADVISORY_NUMERICS.md) define advisory precision/lifecycle. This is adopted methodology, not runtime acceptance. The objective, economic limits and selected risk method below remain required.

## What must be optimized

Choose which specific stock lots to sell and how to reinvest while staying within the investor's benchmark-relative risk, cash, cost, gain and operational limits. Tax eligibility is a constraint. Investment similarity is a risk-model question. Neither can be substituted for the other.

The initial approach is deliberately bounded: maintain an existing long-only stock sleeve, realize no gains by default, and generate a manageable manual worksheet. An investor starting entirely from cash or selling an appreciated ETF needs a separate transition problem. Avoid implying that v1 solves that transition.

## Benchmark and portfolio state

Use a dated, versioned equity-only benchmark with qualified source rights, identity, USD units and complete retained-universe inputs. Under D045, explicitly exclude unsupported/unmapped source holdings and derive retained-equity numerical weights summing approximately to one under the numerical contract; preserve the complete source and exclusion ledger. Never silently repair included facts or rescale rounded source percentages. A custom basket is not automatically a named commercial index.

The owner adopts best-effort evidence-backed mapping: retain accurately mapped supported cash equities and explicitly exclude unsupported or inaccurately mapped securities, including otherwise equity-like rows whose identity is unresolved. Stable identifiers are useful but not mandatory for straightforward dated mappings. Accurately mapped names without adequate required market history are also excluded before finalizing the modeled universe. Apply the [mapping policy](BENCHMARK_INPUTS.md#best-effort-security-mapping-and-explicit-exclusions) without repeated routine per-security approval. Preserve every excluded source row, reason and known/unknown value; exclusion changes the modeled sleeve, not the original portfolio facts. Complete required inputs remain mandatory for the resulting retained universe. Highlight exclusions strictly above **10 bps per name** or **100 bps in aggregate** against the affected pre-exclusion portfolio/benchmark reference-value total; these are warnings, with unknown coverage explicit, not automatic refusal thresholds.

The [market-input contract](BENCHMARK_INPUTS.md) directly specifies explicit fund/provider/reporting-date selection, full original source and primary/alternate accounting, supported mapped-equity exclusions, Float64 marketValue/E weights, no basket/source/date fallback and the optional secondary-file route. Excluded values never create modeled cash. An equity risk mapping does not qualify tax eligibility; excluded observations still inform applicable household/recent-name restrictions and unbounded effects on included holdings remain blockers.

Optimize/report **stock-sleeve risk**: reference-valued included stocks plus the user's selected additional-cash budget. Final weights use final holdings and residual sleeve cash under the same final NAV denominator. Untouched cash and unsupported/unmapped holdings stay outside this modeled sleeve, with explicit source/exclusion diagnostics. An unknown whole-account balance stays unknown; do not imply complete account/household risk.

The default replacement-stock pool includes **all stocks in the selected underlying benchmark**, subject to supported cash-equity scope, accurate mapping, adequate required history and the same tax/restriction/funding/risk checks as any other candidate. No manually curated buy list or arbitrary top-N eligibility truncation is required. A bounded search may examine proposals without proving a global optimum, but its search limits do not silently redefine which benchmark stocks are eligible. Being a benchmark constituent grants replacement-pool membership, not tax clearance or permission to waive a hard limit. Retained held stocks outside the benchmark can still be analyzed; benchmark membership is not an automatic liquidation instruction.

Current holdings preparation can link an original Fidelity-shaped snapshot to retained selected IVV stock evidence from the same date. It compares supported ticker/name facts, preserving supplied identities and tax classifications rather than replacing them. Unmatched/ambiguous/unsupported/user-excluded source holdings receive explicit modeled-stock exclusions; source rows, known/unknown reported values, cash treatments and applicable activity/restrictions remain. The original selected-account reported portfolio value, including recognized cash, is the pre-exclusion coverage denominator; independent-position and lot values are reconciled rather than added. No reported value becomes modeled funding. Matching does not qualify tax eligibility or cross-date/provider history aliases. Only exact same-source/account adapter acquisitions can receive the matched local identity; independently supplied facts remain independent.

## Risk measurement

For security weights w, benchmark weights b and annualized covariance matrix Sigma, model ex-ante tracking error as:

`TE = sqrt((w - b)' Sigma (w - b))`.

Record annualization, return definition, frequency, lookback, shrinkage/factor method, missing-history handling, corporate-action adjustment, data as-of and model version. Compare like units; monthly covariance cannot be presented as annual without conversion. Validate symmetry, finite entries and positive semidefiniteness. Cash handling must be consistent across weights and covariance.

The [risk contract](RISK_MODEL.md#selected-method-and-implementation) selects enhanced DCC-NL, targeting IDR-DCC-NL with qualified OHLC and analytical nonlinear shrinkage. Standard DCC-NL is the named qualification reference. Validate the selected variant, fit constraints, published recursions, coherent source/return/proxy units and forward horizons before calling a plan risk-constrained. A failed fit or unavailable input cannot silently switch models. Detailed settings, source coverage and actual TE calibration remain qualification work.

The adopted risk direction is enhanced DCC-NL/industry risk. Focused marimo and CVXPY/Clarabel continuous references are optional tools for a concrete numerical question, not MVP delivery gates; the [technology comparison](../architecture/ARCHITECTURE.md#shape-and-boundaries) records the reasoning. A hard TE cap and integer shares/order indicators require a suitable mixed-integer nonlinear/conic formulation or a documented candidate/repair method. Clarabel alone does not solve that complete discrete problem. SCIP and other appropriate backends remain qualification candidates; separate MIP and QP support must not be mistaken for support of their combination.

Active weights and sector differences are useful diagnostics but are not tracking error. A missing or invalid covariance model blocks a TE-constrained actionable plan. There is no silent fallback to sector similarity. Historical realized tracking error, if later reported, is a separate backward-looking statistic with dates and data coverage.

## Sector and industry risk

Use versioned sector/industry mappings to show portfolio, benchmark and active weights and validate explicitly selected absolute/active exposure limits. Unknown/reclassified names retain their source/effective/known-time evidence and scoped constraint blockers. No taxonomy or threshold is invented.

For the same horizon covariance `C` used for TE and active weights `a`, signed security Euler contribution is `a[i] * (C a)[i] / sqrt(a' C a)` when TE is positive. Group contributions sum their securities and reconcile to total TE; negative contributions represent risk offsets. Define zero-TE/percentage behavior without division by zero. Standalone group risks and cross-group terms are separate, non-additive diagnostics; sector and nested industry views are not added. These are covariance-based group contributions, not estimated causal sector factors or another covariance to add to total risk.

Pin daily versus review-horizon forecasts and the annualization/fixed-weight approximation from [RISK_MODEL](RISK_MODEL.md#one-covariance-scope-and-horizons). The same stock-sleeve-plus-selected-cash denominator, complete universe and qualified benchmark/cash treatment apply to baseline, candidate and group metrics. T007 independently rechecks final TE and group limits after rounding/costs.

## Adopted first objective

Initially maximize **eligible price/basis loss dollars at reference marks** under independently checked hard constraints. Report ST and LT losses separately. This is a transparent loss-harvesting objective, not a full tax-utility optimizer. If the owner wants tax-dollar optimization instead, define scenario inputs, capital netting and objective semantics in a new decision before changing behavior.

The primary objective is eligible **price/basis loss measured at reference prices**, with transaction costs excluded from the objective reward. Indicative tax P&L using net proceeds is a separate amount. Feasibility alone does not establish economic attractiveness; apply the explicit budgets and optional investor economic screens below. Lower modeled cost, then fewer orders, then stable identifiers break ties in the primary objective. This remains loss harvesting under constraints, not a personalized tax-utility optimizer.

## Objective, cost and cash semantics

For a sold lot portion, let `B` be its supported allocated adjusted basis, `q` its quantity, and `m` the frozen reference mark. Its objective contribution is `max(B - q*m, 0)`, only after eligibility checks. Sum these contributions across sales and keep ST/LT reporting separate. Reference-positive-gain sales are excluded by the zero-positive-gain policy; estimated net-proceeds gains must also pass that policy. Do not sell a reference-gain lot solely because fees might turn it into a modeled loss. A harvest candidate must have positive total eligible price loss; no-trade remains the baseline.

Indicative execution prices incorporate the declared spread/impact assumptions: conservative sell `p_sell <= m`, buy `p_buy >= m`. Net sell proceeds are `q*p_sell - explicit_sell_fees`; indicative tax P&L is net proceeds minus `B`. Acquisition fees contribute to modeled replacement basis when appropriate, but only actual qualified source evidence establishes authoritative executed basis.

For the modeled sleeve, cash is `cash_to_invest + gross_indicative_sell_proceeds - sell_fees - gross_indicative_buy_principal - buy_fees`, with explicit modeled funding assumptions and a final cash check. `cash_to_invest` is the user's reviewed maximum additional-cash budget, allowing zero, not a claim that total account cash is zero. Broker cash import is optional. Show imported/reported cash separately when supplied, always allow the run budget to be edited, and never overwrite source balances with that selection. Default an unset selection to visible zero, not the full imported balance. Sales can fund replacements even at zero additional budget; whole shares/costs may leave residual cash. Do not add a hidden spending reward or force exact budget consumption. Modeled cost is the reference-to-indicative spread/impact difference plus explicit fees on both sides. Embedded spreads and fees are not double counted. Use final reference-valued holdings plus residual sleeve cash for final NAV/risk; require a fresh account snapshot after external changes.

The client may explicitly mark an unmapped personal position **Cash** or **Cash equivalent** in holdings review, for example a money-market fund. This supplied classification resolves the need for an equity identifier/history for that position and keeps it outside stock trades. Preserve the original position/source classification and the dated user treatment, with supported amount/currency facts and unknowns separate. Show recognized cash and cash-equivalent value as such rather than as an unresolved equity-mapping failure; retain full source/coverage accounting and applicable known restrictions. The treatment is editable/reversible and does not by itself prove settled/redeemable buying power, redeem a fund or increase `cash_to_invest`. Only the selected investment budget enters modeled funding; avoid double counting the same original value as both a position and a cash observation. This is holdings treatment, not an automatic benchmark classification rule or an LLM financial decision.

Current review implements this on selected unmapped/unsupported holdings, with change/undo and supported reported values. Reported lot values are summed at the supplied-amount boundary; corroborating independent-position values are reconciled rather than added. Incomplete/contradictory values remain unknown. Treated lots retain source rows with stock metrics inapplicable; they are omitted from held-stock/history requirements and cannot receive positive stock-sale bounds or replacement buys. Original screening records remain retained: only unknown adapter-derived acquisitions for those exact user-treated cash rows leave equity screening. Known identities, independent activity, conflicts and restrictions remain. Frozen current treatment takes precedence over older views of the same original source/account, and historical calculations retain their own frozen state. No investor limit or funding amount changes.

D045 adds an optional explicit final cash balance target, separate from imported cash and the initial funding budget. Raising cash retains eligible net sale proceeds; reinvesting cash uses only selected available funding. Save enabled state, entered target/currency and explicit investor tolerance/constraint treatment, separate from numerical tolerance. Final cash remains in final sleeve NAV/risk against the 100% equity benchmark. Whole-share/cost/gain/risk/funding constraints still apply; report an unmet target or no qualified candidate without silently relaxing it. No default final target, positive-gain permission, forced spending or borrowing is adopted.

Loss opportunity/solver validity, wash-sale verification and operational funding are separate states. D038 permits conditional optimization with incomplete history and explicit warnings/manual restrictions, without certifying deductible loss. Known conflicts, unsupported tax facts, missing affected-lot basis, contradictory holdings, invalid risk inputs and unfunded orders remain scoped blockers. The primary objective is unchanged; positive extra cash affects feasible replacement holdings/weights rather than directly rewarding harvested loss.

An actionable profile explicitly supplies risk/cash limits, maximum cost, maximum turnover/orders and minimum order notional. Optional minimum price-loss, maximum cost-to-price-loss ratio and illustrative scenario-value screens record enabled/disabled state and their investor-entered values. There are no implicit personalized dollar/rate defaults; missing required settings blocks actionable generation. A cost-to-loss ratio compares cost with loss dollars, not with tax savings. A tax-value screen is available only under an explicit user-supplied loss-utilization scenario; never infer immediate tax value or permanent savings.

Declare estimated fee/basis allocation and rounding under the [advisory numerical contract](../engineering/ADVISORY_NUMERICS.md). Prorating source basis estimates a proposed partial sale; it does not update an authoritative remaining-basis ledger or claim broker allocation equivalence. No basis-maintenance ledger or old allocation-format compatibility is required.

Generate a few feasible points across owner-approved harvest/risk/cost budgets rather than an uncalibrated single score combining dollars, variance and turnover. Keep a no-trade baseline. Optional later formulations can minimize TE for a specified loss target. Do not mix units with arbitrary unexplained penalty coefficients.

## Hard constraints

| Constraint | Adopted treatment |
| --- | --- |
| Lot availability | Sell quantities cannot exceed supplied eligible shares in unambiguously identified lots; decimal/integer final check prevents overselling |
| Wash-sale restrictions | Exclude known-conflict sales, prohibited buys and unresolved affected identities; account for outstanding restrictions |
| No simultaneous churn | No buy and sell of the same security in a plan; new suggestions after external activity require fresh holdings; no cross-plan reservation service |
| Cash | Final cash follows the explicit cash-flow equation, modeled funding floor and any enabled reviewed final cash target/tolerance; independent validation includes costs and whole shares; no borrowing or silent target relaxation |
| Gain budget | Zero gross realized positive gains initially, checked per sold lot rather than allowing losses to hide gains |
| Risk | Post-trade TE <= approved cap, plus security, sector and other accepted exposure bounds |
| Trading | Whole-share orders initially, minimum notional, maximum orders and turnover, restricted/no-buy/no-sell names |
| Universe | Only explicitly eligible candidates with reviewed identity and complete required risk inputs |
| Prices | Dated and fresh enough for the plan; stale/inconsistent inputs invalidate actionability |
| Operational funding | State modeled sell/buy sequence and funding assumptions; investor verifies availability at the broker, and known inadequate funding cannot be ignored |

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

Manual sell/buy legs are not atomic. Show indicative costs, modeled funding/sequence, data freshness and low order-count constraints. Do not promise settlement availability, fills or execution-time risk. After external trading, require refreshed holdings/lots and screening facts for a new suggestion rather than retrying an old worksheet as if its intended trades occurred.

Reservations, order/submission tracking, actual-fill reconciliation, basis accounting and forward monitoring are deferred under D046. Relevant known restrictions/recent activity still inform screening, including applicable cross-year dates. A reminder to review later activity is not a monitoring service or tax clearance. Any later re-entry is a new decision using refreshed facts, not an automatic buyback.

## Research and economic evaluation

Backtesting is a later research capability, not the first product. When introduced, use point-in-time universes, delisted names, realistic actions/prices/spreads, flows, dividends, restrictions and tax scenarios. Compare with a defined tax-unaware maintenance policy and a no-harvest benchmark; match pre-tax risk and costs. Report terminal tax assumptions, loss utilization, turnover and implementation shortfall. Do not use today's constituents for a historical survivorship-free claim, or present a backtested loss total as incremental after-tax return.

The [validation plan](../engineering/VALIDATION.md) specifies reference expectations and failure cases required before this methodology is accepted.
