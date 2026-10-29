# Experiments

No study is implemented yet. The [risk-model evaluation design](risk-model-evaluation/README.md) proposes staged historical calibration and harvesting experiments; it contains no runner or results. Start each study in a named directory here. Keep only the files needed for its question, usually `README.md`, `run.py` and optionally `analysis.ipynb`. Use the separate environment and commands in the [research guide](../README.md).

The experiment README should state:

- **Question:** what uncertainty would the result resolve?
- **Design:** inputs and dates, generated portfolio/path rules, estimator settings, evaluation windows, weight conventions and comparison metrics. Fix consequential evaluation choices before inspecting holdout outcomes.
- **Run:** the command, a cheap smoke size and the deliberate full study size. Put generated files under repository-root `.local/research/<name>/<run>/`.
- **Checks:** the few assertions or hand-checkable examples that protect this conclusion; no production test suite is required.
- **Finding:** result location, successes/failures, conclusion and limits. Record contrary and inconclusive outcomes too.

For a tracking-error study, fit only through each cutoff, freeze that forecast and evaluate subsequent active returns. Match horizon/annualization and constant-weight versus drifting buy-and-hold conventions. Keep failed/unavailable fits in the denominator and distinguish fixed portfolios from portfolios selected using the model. Generated weights evaluated on historical markets answer a different question from fully simulated market paths. Simulation requires coherent model inputs, including OHLC where required; do not fabricate missing inputs merely to pass core checks.

Start with one direct script and one useful output table. Add helpers, tests or notebooks only when they improve the experiment. See [research instructions](../AGENTS.md) for the lighter policy and the boundary around production code.
