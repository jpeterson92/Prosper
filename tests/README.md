# Future verification suites

`test_bootstrap.py` contains four locally exercised toolchain qualification tests: editable package import from an unrelated working directory, negative Ruff/type-check probes and positive/negative pytest/Hypothesis execution. They create synthetic probe files in fresh ignored project-local scratch directories when run through the helper and validate no financial behavior. Use the [development guide](../docs/engineering/DEVELOPMENT.md) and `scripts/dev.ps1 -Command check`; no empty test collection is treated as passing.

The [validation plan](../docs/engineering/VALIDATION.md) and [written reference portfolio](../docs/domain/REFERENCE_PORTFOLIO.md) still define unimplemented financial/application expectations.

Introduce suites during authorized implementation for source-linked golden cases, domain behavior, invariants, adapter contracts, independent plan feasibility and complete workflows. Keep fixtures synthetic. Separate tax diagnostic cases from capabilities supported by the planner. Do not report tests, CI or financial correctness as verified merely because these directories exist.
