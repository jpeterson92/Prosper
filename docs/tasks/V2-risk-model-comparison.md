# V2 research: broad equity risk-model comparison

Date: October 23 PDT / October 24, 2026 UTC. Status: **deferred to v2 preparation by the owner; not a v1 delivery dependency or implementation task**.

## Authority and purpose

The owner explicitly requested saving the broader comparison of risk-model approaches for research in preparation for Prosper v2. Preserve the [literature memo](../research/RETURNS_RISK_MODELS.md), its sixteen reference groups, evidence qualifications and proposed experiments. This decision changes comparison scope/timing; it does not select a production risk model, waive v1 model qualification or start experiments. The owner subsequently adopted [D041 enhanced DCC-NL/industry risk](../domain/RISK_MODEL.md#selected-method-and-implementation) for v1. Its standard DCC-NL/IDR parity and targeted forward calibration are required v1 work in the [bounded child plan](T006.2-dcc-industry-plan.md), not the broad comparison deferred here. Detailed settings and actual financial qualification remain open.

## Research question and candidates

After an identified v1 risk baseline and investor workflow exist, determine whether greater model complexity materially improves risk calibration and useful constrained portfolios. Compare on identical permitted, versioned history, memberships, benchmark scope, return conventions, cutoffs and outer test periods:

- Linear shrinkage targets and the v1 covariance estimator as references.
- Static nonlinear shrinkage, including analytical and quadratic-inverse approaches.
- Dynamic nonlinear shrinkage/DCC-NL and EWA-CV alternatives.
- Parsimonious market/latent-factor models with regularized residual covariance, including POET and double-shrinkage variants.
- Industry-informed and heterotic models, with qualified taxonomy granularity, group sizes and historical classification handling.
- Additional OHLC/proxy/volatility or factor combinations beyond the qualified D041 baseline, where source consistency and a coherent published specification permit. The selected IDR enhancement itself is v1 work.

These are alternatives to size and select before execution, not a commitment to implement every method. Country/currency and additional style descriptors are conditional extensions of supported scope, not additions to the current domestic-equity v1 baseline. Algorithm/dependency/license selection remains separate.

## Dependencies, acceptance and stop

Requires a named locally qualified v1 reference, permitted data/retention, consistent frozen histories and classifications, actual universe/scale evidence, predeclared settings/forecast horizons and bounded experiment authority. Reassess and split by concrete acceptance surfaces when scheduled. No automatic scheduling after the current task and no second ready queue: STATUS owns the next-task pointer.

Evaluate projected variance/TE calibration for fixed and optimizer-selected portfolios, same-industry replacements, concentrated active baskets, stress underprediction, forecast uncertainty, turnover/stability, coverage/failure handling and runtime. Use forward outer tests and training-only parameter selection; report uncertainty, survivorship/classification/revision limitations and the cost of complexity. Minimum-variance or intraday-alpha success alone cannot establish Prosper TE accuracy. Adoption needs an explicit methodology decision and required independent review.

Completion is a reproducible comparison and recommendation against the identified baseline, including negative/inconclusive findings. It does not authorize trading, distribution, private-data access or changing v1 risk limits. Narrow v1 reference/calibration checks, solver enumeration and independent validation in T006/T003.5/T012 remain required and are not deferred by this brief.
