# ADR-0008: Python implementation of the adopted DCC methodology

Date: October 24, 2026. Status: **Accepted implementation direction; numerical implementation and qualification pending**. Decision: D042. Approver: project owner, following the Python feasibility assessment: **Let's proceed with your suggestion**.

## Decision and authority

Deliver D041's IDR/OHLC-enhanced DCC-NL model as a maintained Python implementation in Prosper's shared numerical core. NumPy/SciPy is the intended numerical foundation; qualify and pin compatible versions before adding dependencies. Investor operation must not require MATLAB, Optimization Toolbox or MEX binaries. Preserve the selected methodology, full-universe/selected-cash scope and one covariance for tracking error and group attribution under [ADR-0007](0007-adopt-enhanced-dcc-nl-industry-risk.md).

The owner stated **Ignore rights issues. I have independently validated they aren't a concern**. Treat the reference-package rights concern as cleared by that owner validation for this implementation/reference work; do not request it again or retain it as a blocker. This records owner validation, not an agent-inspected additional grant. Prosper's own distribution license and unrelated data/provider permissions retain their existing decision owners.

The inspected MATLAB source may inform algorithm choices and supply validation references. Distinguish its actual QuEST-target DCC path from the intended analytical-target/IDR model. A runnable MATLAB reference is useful optional evidence, not a required investor runtime or the only validation route. Changing a target or porting source does not itself establish parity.

## Context and alternatives

The [reference inspection](../../tasks/T006.2.1-published-risk-contracts.md#reference-artifact-inspection-follow-up) pinned both author archives, found a manual/code mismatch and external runtime requirements, and identified an effective-history boundary. The supplement, complete conventions, independent outputs, stability and forecast calibration remain technical work.

Select maintained Python implementation over deploying the original package or adopting an unqualified DCC wrapper, for compatibility with the accepted Python architecture, inspectability, installation and diagnostics. `arch` is a candidate univariate reference/component, not a selected production dependency. Acceleration requires a measured bottleneck and later qualification; Numba/JAX is not selected. Broad model-family comparison remains v2.

## Implementation and acceptance

- Close published equations, units, centering/effective history, ordered inputs, OHLC/action transformations, GARCH/DCC likelihood/initialization/constraints, pair selection, shrinkage branches and forecast approximation before construction. Research settings are distinct from investor defaults.
- Qualify the Python stack and synthetic oracle route, then separately check analytical shrinkage and volatility/IDR components before DCC/forecast composition. Retain target/innovation/reference versions, failure states and source identities; no silent repair, zero fill, name deletion or fallback.
- Require independent fixed-parameter algebra/likelihood and executable reference outputs, simulated estimation behavior, singular/short/nonconverged cases, ordering and no future leakage. Same-author code/tests are not independent model review. Parameter recovery is statistical evidence, not exact equality or forecast calibration.
- Stream/selectively retain large covariance states. Measure CPU/peak memory on supported Windows hardware and universe sizes before capacity claims. Derived floating-point arrays have explicit conversion/tolerances; source and ledger decimals remain exact.
- Qualify one-day/multi-day covariance and TE on untouched forward observations, including fixed and optimizer-selected active portfolios. Application and research use the same qualified core; no notebook/reference library becomes a separate financial authority.

## Ownership, gates and reconsideration

The [T006.2 child plan](../../tasks/T006.2-dcc-industry-plan.md) owns specification, Python stack/reference, shrinkage, volatility/OHLC, DCC/forecasts, groups and calibration. T006.1 owns qualified frozen inputs; T017.1 retains current coverage/refresh work. ADR-0007 A01-A07/V56-V57, D012/D017 settings and required independent review remain binding. D043 permits local synthetic numerical qualification before G1 completion; unmet operational/input evidence blocks the features that depend on it. Selecting Python passes no financial gate. See the [owner-adopted sequencing](../../tasks/G1-evidence-proposal.md#owner-adopted-sequencing-and-behavior).

This adoption/decomposition changes documentation only. The original adoption left numerical children waiting. The subsequent D043 amendment makes T006.2.1.2 ready for fresh synthetic-only fit assessment after source/profile closure; other leaves retain actual component/reference dependencies. No qualified real inputs or G1 completion is inferred. No installation, executable fixture/test, numerical implementation, acquisition, integration, Git mutation or release begins here. STATUS retains the sole project pointer.

Reconsider the route if measured stability, supported scale or Windows packaging fails and bounded remediation is inadequate. A financial method/variant change requires a separate disposition; runtime convenience does not select another model.
