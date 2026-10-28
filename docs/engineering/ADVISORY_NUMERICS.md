# Advisory numerical contract

Current numerical contract. The adopted Float64/small decimal boundary and material economic/source checks are defined directly here. Existing estimate components have local synthetic evidence; [STATUS](../STATUS.md) records actual scope. No old exact-result interface, stored format, source-code-bound backup or cross-version representation must be preserved.

## Representations and rounding

| Value/use | Contract |
| --- | --- |
| Imported lot quantity, adjusted total basis, entered cash/limits | Preserve supplied decimal value and units as a decimal string/Decimal, with null plus a reason for unknown. Original source bytes retain its spelling. Do not carry source quantum/token type as a universal downstream requirement. |
| Derived valuation, weights, returns, exposures, risk, candidate objective and estimated costs/loss | Float64 in Polars/NumPy/SciPy. Check units, finite results, required membership and missing inputs before accepting a total. A partial sum is labeled partial. No rational transport or exact unit-sum equality. |
| Partial-lot estimated basis | Compute `total supplied basis * proposed quantity / supplied lot quantity`; ordinary rounded Decimal arithmetic at the final trade check is sufficient. This is an estimate, not a broker allocation or an update to a remaining-basis ledger. Full disposal uses the supplied total basis. |
| Proposed order and availability | Whole-share integer proposal under existing policy. Compare to supplied decimal holdings without rounding available shares upward. Preserve fractional residual holdings. No tolerance may permit an unavailable share or ambiguous lot. |
| Decimal boundary | Use an explicit local Decimal context, initially the conventional 28 significant working digits with rounding allowed. Validate admitted operand ranges; increase local precision if needed to preserve a supplied quantity or a sign-critical check. This is not a 28-digit source rejection rule or an arbitrary-precision framework. |
| Input safety | Adapter-specific byte/row/field-length, finite/magnitude and unit checks remain. No universal 12-fractional-digit limit; supported scientific notation/formatting can normalize through the adapter. Unsupported data gets a located explanation, not silent truncation. |
| Display | Estimated USD normally to cents, weights/risk to readable percentages or basis points; show adequate quantity/price precision and data dates. Display rounding does not change inputs or proposed shares. |

## Tolerances and decision boundaries

Use small constants at their owning calculations, not a configurable precision framework. The initial engineering acceptance tolerance for **derived weight sums, active-weight reconciliation and grouped exposure reconciliation** is absolute `1e-10` in dimensionless weight units (`rel_tol=0`). It handles accumulation noise; verify it at the supported workload in T019.2. Tests that reveal an inadequate bound must document the cause and replacement; they must not weaken an economic limit to pass.

Other comparisons use their own units and justified bounds: return/forecast/reference tolerances belong to the existing model specifications; solver feasibility residuals belong to the solver/validator; broker/source reconciliation differences belong to that adapter. None inherits the weight tolerance or a universal one-cent allowance. Individual floating reference tests may use justified relative/absolute tolerances near zero. Investor risk/cost/gain/cash limits remain separate explicit settings.

Recompute final suggested quantities, basis estimate, costs, cash and risk independently of candidate construction. If floating error could flip a discrete or sign-critical decision, use the small decimal boundary for that check or report unavailable/review-required. A risk/constraint result too close to resolve under its justified numerical error bound must not be labeled comfortably within the limit. Missing inputs, a materially exceeded limit, or a positive-gain sale cannot be cleared by an epsilon. No undocumented constraint relaxation or extra investor safety buffer is adopted.

Normalize retained benchmark values by `E = sum(retained primary equity values)` only under D045. Source completeness, identities and exclusions must be accounted for before normalization. An incomplete source percentage sum is not a floating error and cannot be repaired by this tolerance.

For owner-adopted later-date benchmark use, compound each retained constituent's sourced simple total returns after the source close through the target close, multiply source weights by those gross factors and normalize the resulting proxy values. Use Float64 Polars grouping/alignment, require complete covered membership/session order and positive finite factors/denominator, and refuse nonzero underflow or overflow. The [dated-weight contract](../domain/BENCHMARK_INPUTS.md#total-return-drift-to-a-later-effective-date) owns provenance, reinvestment, cutoff and unknown/freshness rules. Independent endpoint-adjusted-close/Decimal expectations check the compounding path; no fitted-risk experiment is needed for this transformation.

## Written acceptance cases

| Case | Independently reasoned expected result |
| --- | --- |
| Three positions worth USD 1 each; selected cash 0 | NAV 3; stock weights approximate 1/3. Sum agrees with 1 within `1e-10`; no exact-ratio bridge required. |
| Same holdings, selected cash USD 1 | NAV 4; stock weights 0.25 each and cash weight 0.25. Untouched imported cash is outside this selected sleeve. |
| Benchmark values 60.00 and 30.000, both retained | E 90; approximate 2/3 and 1/3. Source spellings remain in the original file but are not economically distinct downstream. |
| Derived weight sum 0.9999999999999999 versus source percentage sum 0.9854 | First is numerical agreement; second has a 0.0146 coverage/rounding discrepancy needing its source disposition. It is not invented cash or silently rescaled. |
| Sector contains weights 1/3 and 1/6 | Exposure approximates 0.5 within the stated tolerance. Unknown classifications retain an unknown bucket; affected constrained exposure is unavailable. |
| Source quantity 3, total basis USD 1, proposed sale 1 share | Estimated allocated basis approximately 1/3; it may display USD 0.33. A later run starts from newly supplied basis/quantity, not a fabricated USD 0.67 book balance. |
| Source quantity 3.5; proposal 4 or 3 shares | Four is refused; three leaves 0.5 shares. Formatting/weight tolerance cannot round the source holding up. |
| Basis USD 100, reference sale value USD 100.0001 | This is an estimated positive gain and does not become loss-eligible through rounding/display to cents. Recheck the sign with source decimal quantities/mark at the final boundary. |
| Price loss exists but basis or identity is missing | Show the holding and reason; do not calculate a harvest loss for that lot or certify its sale. |
| Estimated final cash is USD -0.0001 | Do not turn it into funded cash with a one-cent tolerance. Decimal recheck or review-required/no-qualified-suggestion outcome; never borrow implicitly. |
| Missing middle history cell or nonfinite numerical result | Preserve available holdings/loss diagnostics; affected risk is unavailable, not zero/filled and not a validated risk-constrained suggestion. |

These are engineering expected outcomes, not adopted broker accounting/tax interpretations or evidence of return performance. Same inputs/settings/version should yield stable materially equivalent results and deterministic tie-breaking; bit-identical floating output across environments is not a product guarantee. Save historical outputs for viewing without rerunning current code.

## Current implementation boundary

New analytics use `basket.estimate`, `equity_benchmark.estimate` and `industry.estimate`, exercised by `scripts/qualify_advisory.py`. Current import/run records retain finite outputs without analytical replay. T019.6 integrated current API/UI/records/recovery; T019.4 replaced registry/frozen history assembly with current ordered retained inputs and removed the duplicate analytical exact-result/proof paths. Preserve accepted model equations and material financial/source/security tests; no old validators/wire-format compatibility or separate bridge/cleanup queue. The [record contract](../architecture/DATA_CONTRACTS.md#advisory-storage-and-clean-start-records) records current ownership.

The small decimal parser bounds input to 128 characters, exponent/scale magnitude to 512 and adjusted magnitude to 308, then refuses nonfinite or nonzero-underflowing Float64 conversions. These are computational/range guards, not broker scale qualification or a universal fractional-digit rule. Decimal discrete/sign checks work from supplied strings; estimate output must still be finite. Context precision is local and can expand for those bounded operands so caller rounding/traps do not change the result. Exposure limits never use weight reconciliation tolerance to excuse a computed breach; unresolved endpoints are labeled review-required. No investor buffer is silently added.
