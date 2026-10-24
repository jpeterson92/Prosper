# Fictional paper portfolios and large-cap benchmark

Created October 23, 2026 at the owner's explicit request for plausible development inputs for clients holding approximately 20-200 U.S. stocks. All names, account facts, quantities, basis, marks and lot dates are invented. These are development examples, not observed client portfolios or actionable plans. [T017.1](../../../docs/tasks/T017.1-pilot-data-feasibility.md) owns scope, source calibration, verification and remaining G1 gaps.

| File | Use |
| --- | --- |
| [holdings-20.csv](holdings-20.csv) | Concentrated sleeve, 20 stocks and 60 lots |
| [holdings-100.csv](holdings-100.csv) | Core development sleeve, 100 stocks and 300 lots |
| [holdings-200.csv](holdings-200.csv) | Broader sleeve, 200 stocks and 600 lots |
| [benchmark-500.csv](benchmark-500.csv) | FICTIONAL-US-LARGE-500, 500 fictional securities, weights and reference marks |
| [scenarios.json](scenarios.json) | Assumed profile/as-of facts, separate selected cash, restrictions, explicit missing inputs, exact totals and CSV hashes |

The holdings CSVs preserve the established 15-column combined Fidelity-shaped format. They use UTF-8 BOM, CRLF and source-style text fields. No original per-security download is supplied: `Source file` and row numbers are invented provenance labels, not verified downloads. Source collection time differs from the separate **assumed** effective cutoff in the scenario file. Account names and security descriptions do not prove tax eligibility. The current browser imports foundation JSON, not these CSVs or this companion scenario format. The existing bytes-only lot inspector can inspect the holdings files; it still reports false planning/checkpoint readiness. There is no new application adapter, benchmark loader or scenario loader.

## Benchmark assumptions

The owner supplied a representative U.S. total-market weight workbook, described as October 22, 2026 data. Its original bytes and a text-preserving normalized copy are retained under the ignored project folder `.local/reference-data/us-total-market-2026-10-22/`. Redistribution rights and the source provider/effective timestamp are unverified. The workbook is outside authored source. Its largest 500 positive-weight U.S./USD equity rows inform rounded concentration assumptions only; no real identifiers, names, prices, quantities or exact constituent weights are copied into these fictional CSVs.

This is a **stylized large-cap U.S. basket**, not the S&P 500 or a reconstructed index. The fictional top ten sum to 37%, led by weights of 8%, 7.5% and 5.5%. The eleven sector targets are Technology 38%, Financials 12%, Health Care 10%, Consumer Discretionary 9%, Communication Services 9%, Industrials 8%, Consumer Staples 5%, Energy 4%, Utilities 2%, Materials 2% and Real Estate 1%. These are rounded development assumptions, not current index facts. All fictional securities, including Real Estate sector names, are stipulated ordinary domestic-corporation common equity, not REITs or a classification of actual source constituents.

Ten invented leaders receive fixed weights. Remaining names cycle through the eleven sectors. Within each remaining sector, declining integer scores `2 * member_count - local_rank`, with local rank starting at zero, allocate its residual weight. Largest-remainder allocation at eight decimal places makes every sector total exact and all 500 weights sum to **1.00000000**. Equal remainders use row order. Reference marks are invented positive multiples of eight cents, not market/execution observations. Benchmark cash weight is explicitly zero. Future modeled sleeve cash must still enter its own portfolio denominator under D039.

## Portfolio and run assumptions

Each sleeve holds half its names from the largest fictional benchmark weights and half from a dispersed selection of the 500-name universe. Relative benchmark weights receive deterministic 0.80-1.20 tilts, normalized to illustrative stock-value targets of $250,000, $1,000,000 and $2,000,000. Share truncation and a three-share minimum mean actual holdings values differ from those targets. These capital amounts are fixture-design choices, not pilot eligibility thresholds. Each security has three distinct lots, mixed gain/loss basis and acquisition ages. Selected residual lots have 0.125 shares. Two/ten/twenty lots respectively have recent acquisition dates to support known-conflict screening exercises, without declaring any sale eligible. Display percentages truncate toward zero at three decimal places; source-style total basis remains authoritative for these invented observations.

Imported account cash is **unknown**, not zero. Separate additional-cash selections are stipulated as $0/$10,000/$25,000 for the three sleeves. Those are scenario choices, not default investor budgets, settled cash or verified buying power. History is not supplied and each scenario retains the persistent unverified-wash-sale warning. One resolved fictional name per scenario is manually restricted on both sale and replacement-buy legs. Empty or absent history never clears known recent-lot evidence.

Risk-market history, covariance/model settings, investor risk limits, costs, actual execution/lot confirmations and household facts are not fabricated. These files support import and future paper workflow development. They do not establish tracking error, a feasible zero-gain/whole-share harvest, deductible loss, a valid funding sequence, a functioning optimizer or G1-G3 acceptance. Realistic return/correlation histories and executable plan qualification remain later scoped work.

## Exact controls

| Sleeve | Quantity | Reported basis | Holdings value | Display P&L | Selected additional cash | Modeled sleeve value before costs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 20 stocks | 7,227.375 | 238,107.44 | 249,642.12 | 11,534.68 | 0.00 | 249,642.12 |
| 100 stocks | 26,336.875 | 951,285.22 | 997,386.18 | 46,100.96 | 10,000.00 | 1,007,386.18 |
| 200 stocks | 49,608.625 | 1,902,765.07 | 1,994,595.58 | 91,830.51 | 25,000.00 | 2,019,595.58 |

These are exact source-observation and stipulated modeled-scope controls, not independently reconciled broker NAV. Fixture checks recompute arithmetic with rational numbers, match holdings to the fictional benchmark, preserve exact source text/byte identity and inspect all three CSVs with the actual read-only inspector. The report records checks actually run; no passing tax/optimizer/browser result is inferred from fixture arithmetic.
