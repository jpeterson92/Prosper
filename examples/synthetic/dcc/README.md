# Fictional DCC references

`reference.json` retains the fitting child's 90-digit direct full-matrix convolution/likelihood expectations. `covariance-reference.json` retains eight one-/21-session forecast cases using separate Decimal powers and finite sums, cross-checked at 110 digits. All values are stipulated synthetic model units; E05/E06 deliberately use large units for transparent quadratic checks, not plausible market-risk forecasts.

The [frozen numerical specification](../../../docs/tasks/T006.2.1.1-python-numerical-spec.md#forecast-origin-and-horizon) owns equations, units, R1 tolerances and E03/E05/E06/E12/E14 expectations. The [task evidence](../../../docs/tasks/T006.2-dcc-industry-plan.md#t00622222-execution) distinguishes independently expressed same-agent references from independent model review and financial acceptance.

Run `scripts/qualify_covariance.py --output .local/covariance-reference-check.json` from the repository root. Normal execution refuses changed corpus contents; `--write-reference` explicitly regenerates expectations. The optional seeded experiment constructs fictional data locally, keeps timing/memory outside deterministic replay JSON and establishes no supported-universe capacity or forecast calibration.
