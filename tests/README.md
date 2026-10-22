# Verification suites

`test_bootstrap.py` contains four locally exercised toolchain qualification tests: editable package import from an unrelated working directory, negative Ruff/type-check probes and positive/negative pytest/Hypothesis execution. They create synthetic probe files in fresh ignored project-local scratch directories when run through the helper and validate no financial behavior. Use the [development guide](../docs/engineering/DEVELOPMENT.md) and `scripts/dev.ps1 -Command check`; no empty test collection is treated as passing.

The [validation plan](../docs/engineering/VALIDATION.md) and [written reference portfolio](../docs/domain/REFERENCE_PORTFOLIO.md) still define unimplemented financial/application expectations.

`test_exact.py` exercises T003.2 parsing, source preservation, sign/precision rejection, explicit unknowns, exact arithmetic, ambient-context isolation and synthetic diagnostic allocations. Independent integer/Fraction expectations cover ties, fractional/extreme inputs, residual conservation and the 0.33/0.34/0.33 example. These checks cover V45's primitive example and limited portions of V25/V37; complete persistence/transport, fee/tax accounting and qualified broker allocation remain untested. [Task evidence](../docs/tasks/T003.2-exact-values.md) records actual results and limitations.

Introduce suites during authorized implementation for source-linked golden cases, domain behavior, invariants, adapter contracts, independent plan feasibility and complete workflows. Keep fixtures synthetic. Separate tax diagnostic cases from capabilities supported by the planner. Do not report tests, CI or financial correctness as verified merely because these directories exist.

`test_bundle.py` adds 82 synthetic parser cases: strict shape/scalars, value/reason facts, malformed/resource rejection, duplicate keys/IDs, immutability and identity. Two deterministic property tests cover record/key/whitespace permutations and arbitrary bytes. F002/F003/F004/F009 can be structurally parsed while explicitly unvalidated; this suite does not qualify their financial reconciliation/readiness behavior. See [T004.1.1 evidence](../docs/tasks/T004.1.1-synthetic-bundle-parsing.md).

`test_checkpoint.py` exercises independent F000/F001 expectations and incomplete/contradictory references, inclusion, history, quantities, cash, valuation and coverage. Property cases vary quantities/marks and ordering. See [execution evidence](../docs/tasks/T004.1.2-checkpoint-reconciliation.md); this does not qualify broker/tax correctness or import mutation.
