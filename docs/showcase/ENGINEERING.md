# Building Prosper

Prosper is an independent software project exploring a practical investment-product question: how can a self-directed investor identify a useful tax-loss-harvesting decision, understand its portfolio consequences, and retain a clear record of the assumptions behind it?

The interesting engineering sits between the numerical calculation and the investor's decision. A plausible result is not enough if source data is incomplete, cash is unavailable, inputs changed during a calculation, or the saved worksheet cannot be retained as a historical record.

## One investor journey, explicit boundaries

The application follows **current holdings → input review → risk and candidate comparison → dated manual worksheet → refreshed holdings next session**. Execution remains external. Imported activity informs screening; it is not replayed into holdings or treated as proof that a proposed trade occurred.

The [workspace service](../../src/prosper/workspace.py) connects typed records, data coverage, the numerical core and saved outputs. The [React interface](../../frontend/src/review.tsx) exposes the same workflow through protected local APIs. Generated TypeScript contracts keep the browser and service aligned.

## Data quality is part of the product

Original source bytes, source dates, row references and unknown facts are retained. Import review and active selection are separate steps. A malformed replacement cannot silently turn a portfolio into an empty state.

[Polars-based input assembly](../../src/prosper/modeled_inputs.py) constructs the declared held/benchmark/candidate universe and diagnoses identity, quantity, price, taxonomy and history coverage. It does not quietly fill missing prices, truncate the universe, repair actions or substitute another model after a failure.

This separation makes partial diagnostics useful: an unknown basis can block one lot's loss calculation without erasing the rest of the source inventory.

## The quantitative pipeline

The selected IDR-DCC-NL implementation combines:

1. [OHLC-derived innovations](../../src/prosper/innovations.py), with explicit price/action conventions and ordered history.
2. [Univariate volatility estimation](../../src/prosper/volatility.py), with retained fitting diagnostics and refusal outcomes.
3. [Dynamic conditional correlation](../../src/prosper/dcc.py).
4. [Nonlinear covariance shrinkage](../../src/prosper/shrinkage.py).
5. A common [covariance representation](../../src/prosper/covariance.py) for portfolio risk and attribution.

For portfolio weights $w$, benchmark weights $b$ and annualized covariance $\Sigma$, the core tracking-error calculation is:

$$
\operatorname{TE}(w,b)=\sqrt{(w-b)^\mathsf{T}\Sigma(w-b)}
$$

The equation is compact. Making its inputs coherent—and communicating their limits—is a substantial part of the application. Model implementation, numerical reference checks, calibration and financial acceptance are distinct.

## Construction and validation are different jobs

The [candidate constructor](../../src/prosper/candidate_search.py) explores a bounded set of whole-share proposals. The [final validator](../../src/prosper/candidate_validation.py) independently recomputes financial feasibility from canonical inputs. An objective score cannot override a cash deficit, positive-gain restriction or enabled risk/cost limit.

The [tiny reference cases](../../tests/test_candidate_reference.py) include independently derived expected outcomes. Larger proposal searches retain their budgets and limitations rather than converting “no candidate found” into “no feasible portfolio exists.”

“Separate validation” means separation from the search implementation. It does not claim an independent external audit or professional model acceptance.

## State transitions deserve financial-level care

The [SQLite store](../../src/prosper/advisory_store.py) retains selected snapshots, revisions, settings, original inputs, run records and durable command receipts. A repeated command with identical content returns its original outcome; reuse with changed content is rejected. A result cannot become current after relevant inputs change.

Long-running work uses an [isolated worker](../../src/prosper/candidate_worker.py) with bounded resources and explicit cancellation/interruption outcomes. The worker does not write directly to the application database.

[Recovery](../../src/prosper/advisory_recovery.py) uses a consistent current-format backup and validates required records and sources before restoration. Unsupported, corrupt or populated destinations are refused; recovery does not silently wipe work or recalculate historical financial results.

## The deliverable is a decision record

The [worksheet service](../../src/prosper/worksheets.py) connects a checked candidate to a dated manual deliverable: account/security/lot references, whole shares, indicative marks, costs, cash, risk, assumptions and warnings. Quantity edits receive new final checks. Revisions create new records and preserve their parents.

This is the product boundary: the investor can understand and retain an estimate, then verify current broker facts before acting. The software does not submit an order, reserve funds, confirm a fill or reconstruct basis from assumed execution.

## Evidence and remaining work

Verification spans scalar financial cases, numerical references, API security, browser workflows, stale/interrupted work and current-format recovery. The [development checks](../../.github/workflows/checks.yml) run on Windows with locked dependencies and pinned GitHub Actions.

The application is a development prototype. The current UI and integration examples demonstrate the implemented workflow with fictional inputs; independent tax/model review, calibration, qualified financial inputs and investor release readiness remain open. The product roadmap emphasizes less preparation, standard defaults and clearer exception review before broader scope.

[Return to the project overview](../../README.md)
