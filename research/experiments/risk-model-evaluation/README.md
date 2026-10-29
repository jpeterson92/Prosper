# Risk-model evaluation and harvesting research design

Status: proposed design only. No runner, data acquisition, model fit or backtest has been implemented or executed. Follow the [research agreement](../../AGENTS.md). This proposal does not change application methodology, presets, investor limits or acceptance gates.

## Question and intended decisions

Does Prosper's risk model predict the out-of-sample benchmark-relative risk of portfolios that its harvesting search actually selects, and what harvesting opportunity, investment divergence and operational burden accompany different tracking-error budgets?

Answer four separate questions:

1. **Calibration:** does a stated amount of predicted active variance correspond to the subsequent variability of active returns?
2. **Selection:** does calibration deteriorate when the harvesting search chooses the portfolio, particularly near the risk limit?
3. **Economic tradeoff:** how much additional eligible loss does each larger risk budget obtain, at what realized investment divergence, cost and concentration?
4. **Scope:** which starting portfolios, market conditions and input exclusions make the result unreliable or unavailable?

The first useful result is a paired historical experiment: identical starting holdings and lots, several TE caps, the current core search and final checks, then untouched subsequent returns. Random basis and missing-stock portfolios are controlled scenarios; they are not evidence that the scenarios represent actual investor accounts.

## Current application boundary

The current [risk contract](../../../docs/domain/RISK_MODEL.md) specifies Standard R1 (`standard-r1-v1`): IDR-DCC-NL, 1,260 sessions, a 21-session projection and 252-session annualization. One-session projection is also supported. Read the then-current contract before implementation; the design was prepared at revision `e26257d` with substantial pre-existing application edits.

Reuse [risk input assembly](../../../src/prosper/risk_inputs.py), [covariance fitting](../../../src/prosper/covariance.py), [candidate workflow](../../../src/prosper/candidate_workflow.py) and the separate [final validator](../../../src/prosper/candidate_validation.py). Fit on the complete retained held/benchmark/replacement union, with source/history exclusions determined before fitting. Do not shorten history, invent OHLC, remove difficult names after a failed fit or silently substitute an estimator.

The present [candidate search](../../../src/prosper/candidate_search.py) is a bounded deterministic loss-prefix/repair heuristic. Its checked incumbents do not prove optimality, and failure to find a candidate does not prove infeasibility. The [exhaustive reference](../../../src/prosper/candidate_reference.py) is useful only for tiny declared share domains. Report the search method and stopping reason; describe results as the current search's achieved tradeoff. Keep search quality distinct from risk-model quality.

The objective remains eligible price/basis loss dollars, with costs and ST/LT amounts reported separately, under the [portfolio contract](../../../docs/domain/PORTFOLIO_CONSTRUCTION.md). Gross harvested losses are not tax savings or investment alpha. Any illustrative tax-value overlay is a separately declared scenario, consistent with the [tax contract](../../../docs/domain/TAX_POLICY.md).

## Common historical design

### Inputs and information timing

- Select a named permitted U.S. equity benchmark and its historical constituents/weights, stable security identities, coherent raw OHLC/total returns/actions, dated classifications and session calendar. A provider fund's stock basket is its own benchmark approximation; do not silently call it the official index. Research data access/rights and an adequate source have not been selected.
- Use facts available by each formation cutoff, including the publication lag of holdings and classifications. Distinguish event date, effective date and known time. Present-day constituents tested backward create a survivor-conditioned study; label that narrower study if historical membership is unavailable. Never present it as a point-in-time index backtest.
- Require the current 1,260-session history for every retained name. Track IPO/short-history, mapping and instrument exclusions, original versus modeled benchmark weight, held value and unknown coverage. Missing future observations and delistings need an explicit source-backed outcome; never drop a future failure or fill it with zero. No complete-case filter based on future survival may determine formation portfolios.
- Primary model-calibration returns are mathematical exposures fixed at cutoff `t`, evaluated on sessions `t+1` through `t+21`. They do not claim a fill at a close whose information was needed for estimation. A separate implementation-timing scenario executes at the next declared tradable mark and accounts for the intervening untraded interval, costs and forecast aging.
- Start with nonoverlapping 21-session evaluation blocks, on a schedule fixed before seeing results. Choose chronological development and locked evaluation periods after the data inventory establishes feasible coverage. Fit using only prior observations at each cutoff; historical estimation may roll forward through already observed returns, while choices of method/settings remain locked. Purge development outcomes that extend into the evaluation period.
- A final chronological holdout stays untouched while designing scenarios, reference settings, scoring and practical acceptance thresholds. Historical periods already examined while developing Prosper are exploratory evidence, even if refitted without look-ahead. A later forward paper cohort is the cleanest additional test after the design is frozen.

### Starting portfolios and lot construction

Use one disclosed hypothetical account size initially, with whole-share holdings, residual cash and basis at the supplied-amount boundary. A market-cap target will generally differ slightly from its integer realization; record the actual baseline TE. Initially use zero additional cash and a fixed declared cost/order/turnover/sector policy across caps. These are research scenario settings, not product defaults or recommended investor limits.

| Family | Construction | What it isolates |
| --- | --- | --- |
| Benchmark-like | Historical benchmark target, realized into whole shares | Departures introduced by harvesting from a near-index starting point |
| Random missing names | Remove sampled names and redistribute their weight proportionally over retained names | Broad incomplete replication without deliberate sector bets |
| Structured missing names | Remove a sector/industry cluster or a set of large names | Systematic gaps hidden by a simple random-deletion average |
| Concentrated/tilted | Add declared single-name or sector overweights, with offsetting underweights | Legacy portfolios whose initial risk can already exceed a chosen cap |
| Locked appreciated positions | Preserve large embedded-gain positions and restrict sales | Whether harvesting can coexist with inherited portfolio constraints |

For omissions, record both the fraction of names and the fraction of benchmark capitalization removed. Compare random omissions with clustered omissions at similar removed capital weight; removing many tiny positions is unlike removing one major constituent. Keep the original benchmark fixed when changing the investor portfolio. Redistributing removed weight is a declared generator rule; a separate cash-retention scenario answers a different question. All eligible benchmark names remain in the replacement pool unless a separately declared restriction excludes them.

Use two complementary lot generators:

1. **Controlled basis:** hold shares and market values fixed; randomize unrealized price/basis ratios and supplied acquisition dates using a predeclared distribution. For example generate `g = log(price / basis_per_share)`, then `basis_per_share = price * exp(-g)`. Vary the loss-name fraction and loss depth separately, as well as appreciated versus near-cost portfolios. Retain exact generated basis amounts and seed; holdings and marks must not change when only basis changes. Permute the same set of gain/loss ratios across names as a particularly clean selection test.
2. **Purchase-history lots:** choose acquisition dates and purchases using information available then, carry shares/actions and declared distributions/cash flows forward to formation, and derive basis from those purchases. Vary account age, contribution pattern and single versus multiple lots. This preserves the link between past winners/losers and harvest eligibility that independent random basis deliberately removes. Use split/action-aware price/basis accounting; a total-return-adjusted historical price is not automatically a tax purchase basis.

Use identical initial holdings, lots and seeds for every cap/model comparison within an episode. Generated activity/restrictions must be internally coherent, with explicit household assumptions. Unknown tax term, basis or identity remains unknown and blocks its dependent claim; do not invent a clean screen from an empty activity list.

### Risk budgets and comparators

Proposed research cap grid: **50, 100, 200, 300 and 500 bps annualized TE**, plus no trade. These are experimental settings only; the pilot may show the useful grid is narrower or baseline risk makes some caps unattainable. Keep absolute post-trade TE as the primary limit. Report baseline TE, final TE and their change separately. No trade remains a performance counterfactual even when it breaches a cap; it is not a feasible cap-compliant recommendation in that case.

Primary estimator: unchanged current IDR-DCC-NL preset. Named methodological comparator: returns-only DCC-NL. Simple comparator: one predeclared regularized covariance estimator, such as linear shrinkage, with estimation/horizon conventions fixed on development data. These are research implementations if not currently supported by the core, never application fallbacks. Compare the same assets, cutoffs, return units, horizon and non-risk constraints; state any deliberate training/model differences. Do not launch a broad estimator or parameter tournament.

Separate two comparisons:

- **Same portfolio, different forecasts:** score every available model on a common frozen set of baseline, independently generated and search-selected portfolios. This measures forecast quality without confounding it with different decisions.
- **Each model selects its portfolio:** rerun the same search/budgets using each model's covariance, then evaluate the selected portfolios on the same future market. Cross-score the portfolios under the other models too. This measures the combined method/search outcome, without claiming identical predicted caps imply equal actual risk.

The first pilot can use the adopted estimator plus the simple reference; the full comparison includes the named DCC-NL reference before a superiority conclusion. Record unsupported reference inputs and model-specific failures, alongside paired common-support comparisons and their coverage. A secondary harvest-versus-realized-risk frontier compares achieved risk levels without selecting a live decision using future outcomes.

## Experiment sequence

| Study | Procedure | Main result and decision |
| --- | --- | --- |
| 0. Data and measurement feasibility | Inventory permitted history, benchmark vintages, actions/delistings, usable dates and full-union dimensions; hand-check weights, units, return timing and baseline accounting | Establish what can be studied honestly; identify whether a historical-index claim is supportable |
| 1. Fixed-portfolio calibration | Before using the search, forecast benchmark-like, omitted-name and fixed sector/single-name perturbations across historical cutoffs | Does calibration fail even without optimizer selection? Separate general model/input problems from selection problems |
| 2. One-shot harvesting frontier | Use controlled random basis; run paired cap sweeps from identical accounts and evaluate the next 21 sessions | Direct answer to the owner's proposed experiment: additional losses versus predicted/realized risk, costs and divergence |
| 3. Investor-shape and lot sensitivity | Extend study 2 to purchase-history lots, clustered omissions, concentration and locked gains; vary one feature at a time before selected interactions | Determine where results generalize and where starting risk or portfolio structure dominates |
| 4. Repeated harvesting and aging | Carry lots/cash/restrictions forward through repeated simulated trades; compare no trade, matched non-TLH rebalancing and TLH on common market paths | Does cumulative benefit survive declining basis, costs, restrictions, recurring contributions and manual burden? |
| 5. Stress and method diagnostics | Predeclare volatile/reversal/correlation-shift periods; inspect errors, exclusions and failures; run targeted model/reference/horizon sensitivities | Identify specific failure conditions and whether the enhanced method earns its complexity |
| 6. Locked forward paper evaluation | Freeze decisions and record dated recommendations before outcomes exist; measure later returns and hypothetical implementability | Check that historical findings persist with truly untouched information |

Begin with studies 0-2. Study 4 is a later, deliberately separate extension: it needs a research-only lot/cash/activity simulator, not just repeated optimizer calls. The production application does not reconstruct execution or maintain an authoritative tax ledger. Do not reset basis randomly every rebalance, replenish sold loss lots, clear restrictions or reset the account to benchmark weights. No real trading is proposed.

Useful targeted extensions after the initial result include account sizes (share granularity), realistic mark delays/cost assumptions, stricter order budgets, monthly versus less frequent review, inflows versus no inflows and missing-history exclusions. Any alternative lookback or estimator parameter outside the core's supported profile stays an explicitly experimental research implementation. Run extensions to explain an observed uncertainty, not a full Cartesian sweep.

For study 5, scenario labels may describe realized stress retrospectively, but those labels cannot influence earlier portfolio decisions. Named historical crises are diagnostic subsets, not independent replications or an untouched holdout. A deliberately misspecified factor/jump simulation can later isolate correlation breaks or tail behavior; simulation from the fitted model alone mainly tests internal consistency. Fully simulated OHLC requires a coherent, separately specified price/action process. Resampling historical daily returns without compatible OHLC does not supply the enhanced model's inputs.

## Measurement: what counts as working

### Match the forecast's mathematical object

At formation let `a = w - b` for the retained modeled sleeve, including its disclosed cash convention. Let `H[t+h|t]` be the daily covariance forecasts. Define:

```text
V_pred = sum(h=1..21) a' H[t+h|t] a
TE_pred = sqrt((252 / 21) * V_pred)
x[h] = a' r[t+h]                       # fixed-exposure active simple return
RV = sum(h=1..21) x[h]^2
Z = sum(h=1..21) x[h] / sqrt(V_pred)   # where V_pred > 0
```

`RV` is a noisy realized second-moment proxy for the forecast target under the model's zero-mean/cross-day assumptions, not an observed conditional covariance truth. Primary calibration summaries are `sum(RV) / sum(V_pred)` and mean episode-level `RV / V_pred`, with weighting stated. Their square roots are volatility-scale summaries; retain both because pooling can hide errors in low-risk episodes. Aggregate seeds within formation date for the primary summary so more generated portfolios do not give that month more weight.

Report QLIKE-style loss `log(V_pred) + RV / V_pred` for positive forecasts, compared on identical portfolios/observations and in consistent units. Its usefulness depends on the proxy/mean assumptions; inspect active-return mean and serial dependence separately. Exact zero-risk exposures use a separate zero-risk check; no arbitrary epsilon should create a log score. A positive forecast with zero realized movement is valid, while nonzero realized movement at an exact predicted zero needs investigation.

Report the usual annualized sample standard deviation of active daily returns as a familiar descriptive realized TE, alongside the second-moment diagnostics. A 21-session sample is noisy and demeaning changes the quantity; do not demand equality episode by episode or silently score a variance forecast against a different object. Include active mean, standardized-return mean/dispersion and the distribution of `Z`; nonzero expected active returns or cross-day dependence can affect the latter.

Also calculate exact drifting buy-and-hold portfolio and benchmark wealth paths, with consistent dividend/cash treatment, and report terminal active return, adverse relative drawdown and pre-/post-cost results. Freeze the benchmark's initial basket in the primary 21-session exposure test; a dated live/reconstituting benchmark and ETF comparator are separately labeled practical sensitivities. Fixed-weight diagnostic returns and buy-and-hold performance answer different questions. Separate the approximation gap, benchmark drift, execution timing and cost effects from estimator error.

**A TE cap is a volatility budget.** It is not a bound on terminal loss, a 95% interval or a promise that every realized 21-session TE will remain below it. Report the empirical frequency/size of high realized risk and large relative losses descriptively. Any interval/tail-coverage test needs an additional predeclared distributional assumption; evaluate that assumption separately rather than attributing it to covariance alone.

### Primary scorecard

| Dimension | Record |
| --- | --- |
| Calibration | Predicted versus realized risk bins; pooled/equal-date variance ratios and uncertainty; QLIKE differences; fixed versus search-selected error |
| Selection effect | Cap utilization, selected-portfolio calibration gap, cross-model disagreement, single-name/sector concentrations and offsets |
| Harvesting | Eligible price/basis loss dollars and percent initial NAV; ST/LT/unknown; fraction of available eligible loss harvested; marginal loss per cap increment |
| Investment outcome | Pre-/post-cost active returns, descriptive realized TE, terminal wealth difference, adverse relative drawdown and outcome quantiles |
| Burden and search | Sell/buy/order counts, turnover, residual cash, elapsed fit/search time, evaluated states and search stopping reason |
| Coverage | Attempted cutoffs/accounts/caps; unavailable fits; exclusions and excluded value/weight; invalid inputs; no-candidate cases; missing forward outcomes |

Use gross eligible-loss accounting for the optimizer question. Optional economic scenarios may value usable losses using supplied offset assumptions, retain unused losses separately and compare both pre-liquidation and terminal-liquidation wealth. A later lower basis, changed tax rates, ST/LT mix and timing of loss use can change the result. Do not call harvested loss times a tax rate lifetime tax alpha. No personal tax assumptions are needed for studies 0-3.

### Controls that isolate attribution

- No trade from the identical starting state measures the entire decision's incremental effect.
- A matched non-TLH rebalancing control, with the same starting holdings, risk and order policy, helps distinguish ordinary risk repair from loss harvesting when starting TE is high.
- Random feasible portfolios and same-portfolio cross-scoring separate ordinary forecast error from search selection.
- Tiny-domain exhaustive checks identify search-quality gaps on tractable examples. An optional continuous relaxation is a separate research bound only where genuinely comparable; it is not an executable whole-share solution.
- Keep costs, restrictions, candidate universe and non-risk budgets constant across primary cap/model comparisons. Attribute differences that remain rather than changing several controls together.

Failure counts are part of the result. An unavailable risk estimate is not a zero-TE observation; no candidate is not necessarily infeasibility. For an explicit end-to-end policy simulation, a declared no-trade response to an unavailable proposal may be modeled, while retaining the failure status and separating its policy performance from successful-proposal calibration. Never improve headline results by conditioning silently on successes.

## Inference, interpretation and decision rules

Thousands of generated portfolios on the same market month are not thousands of independent market experiments. Pair comparisons by date, initial account and seed. Use date-block uncertainty that keeps all portfolios/models/caps from a date together and preserves serial dependence across dates; set the block rule on development data and report sensitivity if the conclusion depends on it. Nonoverlapping evaluation reduces mechanical overlap but does not remove market dependence. Distinguish scenario variability from uncertainty about future market performance.

Predeclare the primary fixed-versus-selected calibration contrast and model comparison. Treat the many portfolio/cap/stress slices as descriptive unless a multiplicity-aware confirmatory analysis was specified. Do not choose the best cap/model on the final holdout and report that same period as unbiased validation. If inputs cannot support enough independent time blocks, report imprecision and inconclusive comparisons.

Before opening the locked evaluation period, specify the practically material variance-understatement band, acceptable availability/excluded-weight coverage, minimum economic improvement after costs and the conditions under which a method is too unstable to use. These thresholds are unresolved owner/review choices; this document invents no investor loss tolerance or financial acceptance rule. Development-period uncertainty can establish whether the proposed history has power to distinguish useful differences. A finite point estimate near one or a non-significant model difference is not proof of calibration or equivalence.

The resulting decisions should be concrete:

- Fixed and selected portfolios both understate risk: investigate source/units/horizon and general forecast calibration first.
- Fixed portfolios calibrate but selected portfolios do not: investigate estimation uncertainty, search-selected exposures and cap utilization; any cap adjustment is a new proposal, not an automatic safety factor.
- Higher caps add little loss but much divergence/cost: narrow the economically useful research range; recommend no production default without a separate disposition.
- Random omissions look sound but clustered/legacy portfolios do not: state the restricted evidence scope and investigate those exposures.
- Enhanced estimates do not improve on simpler/named references, or fail more often: record that result and propose an evidence-backed method/settings review.
- Uncertainty or input coverage is inadequate: identify the missing data/market observations rather than treating the experiment as passed.

Exploratory findings do not close independent model/tax review, qualified-input, calibrated-bound or financial-use gates in the [validation contract](../../../docs/engineering/VALIDATION.md).

## Smallest useful implementation, once authorized

1. Inventory data and freeze a short protocol: source, universe, windows, benchmark/return conventions, generators, cap grid, comparator settings, primary score and evaluation split. No large data purchase is assumed.
2. Build one direct script with a small research adapter to the current core. A cheap correctness smoke uses two development cutoffs, three seeds, two portfolio families and two caps. Check the same-weights zero-active-return case, a hand-computed two-name quadratic form, forecast/realized units, no future observations, lot/share/cash conservation and retained failure records. Fit only the necessary supported full union; do not shrink history to make a smoke fit cheaper.
3. Proposed pilot: 12 development cutoffs, 20 seeds, three families (benchmark-like, random omissions, clustered omissions), five caps and no trade. That is 3,600 harvesting searches per model, not 3,600 independent market periods. With one common frozen union per date, fit once per model/date and reuse the covariance across lots/caps; avoid calling the integrated fitting wrapper for every search. Measure one full-union fit and representative searches before committing to that budget. Reduce search repetitions first if compute is excessive; do not multiply costly fits unnecessarily.
4. Produce one useful result table and the plots below. Resolve data/convention failures before broadening the study. Select the chronological locked evaluation only after feasibility/power assessment, and freeze choices before inspecting its outcomes. Proceed to long-run stateful simulation only if its additional question remains material.

Suggested plots: predicted versus realized risk with uncertainty and a 45-degree reference; harvested-loss frontier against predicted and achieved risk; distribution of terminal active returns by cap; calibration split by fixed/search-selected and portfolio family; availability/excluded-weight panels. Show uncertainty and failed-run coverage alongside attractive frontiers.

Use `research/.venv` and keep any added dependencies in the research project. Keep generated data/results under `.local/research/risk-model-evaluation/<run>/`. A minimal run record contains Prosper revision plus relevant dirty edits, script/settings, dependencies, seed, source identities/vintages, cutoffs/evaluation windows, actual weights/lot assumptions, forecasts, chosen orders and outcome/failure counts. Keep generated or restricted data out of committed notes. No general experiment framework, production tests, provider acquisition or runner is part of this planning change.

## Methodological reading

- [De Nard, Engle, Ledoit and Wolf (2022)](https://www.econ.uzh.ch/dam/jcr%3A5ee13ed0-14df-4562-9beb-086a2d76738f/jbf_2022.pdf) motivates the adopted OHLC-enhanced covariance method and discusses averaging forecasts over a 21-session holding horizon. It does not establish Prosper's calibration.
- [De Nard, Ledoit and Wolf (2025)](https://www.econ.uzh.ch/dam/jcr%3A8f7e20cf-e9a7-4fde-87cb-aef82de26404/jpm_2025.pdf) studies benchmark-relative covariance estimation. The abstract was accessible during design; the complete PDF fetch timed out, so this design does not claim to reproduce its empirical protocol.
- [Patton (2011)](https://public.econ.duke.edu/~ap172/Patton_vol_proxies_JoE_2011.pdf) studies forecast scoring with imperfect volatility proxies; it motivates careful loss/proxy choices, subject to their assumptions.
- [Ledoit and Wolf (2008)](https://www.ledoit.net/Robust_Sharpe_2008.pdf) motivates accounting for time dependence in performance comparisons. The proposed date-block analysis here is a study-specific design, not a claim to reproduce their Sharpe-ratio test.

## Finding

None yet. All study sizes, scenario values and sequence above are proposals. Data feasibility, empirical calibration, economic outcomes and acceptance thresholds remain unmeasured or undecided.
