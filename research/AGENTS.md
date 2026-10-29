# Research working agreement

This directory contains disposable, manually run experiments that consume Prosper. The root [working agreement](../AGENTS.md#research-exception) explicitly delegates research-only work to this lighter policy. Changes outside this directory follow the normal application policy.

## Start and scope

Read the owner's research question, [README](README.md) and the selected experiment's notes. Inspect Git status and only the core interfaces/contracts needed for that question. Research-only tasks do not require backlog selection, a NEXT_STEP assessment, STATUS updates or production task reports. A short execution sketch in the conversation is enough. Application `/next` does not select research experiments automatically.

Use the separate `research/.venv` and local editable Prosper dependency. Keep experiment-specific dependencies in this directory's `pyproject.toml`/`uv.lock`. Do not modify the application environment or add research dependencies to the root project. Research may import `prosper`; application code, tests, scripts and frontend must never depend on research. Internal Prosper interfaces may change without compatibility shims for experiments.

## Lightweight defaults

- Prefer direct scripts and optional notebooks. Duplication and local adapters are acceptable. Add shared helpers only after multiple experiments need them; no general experiment framework, service or registry is required.
- Type annotations, linting and automated tests are optional. There is no coverage target, strict mypy gate, production regression-suite requirement or ongoing maintenance promise for research code.
- Verify the conclusion's vulnerable assumptions with a small smoke run, assertions or hand-checkable examples as appropriate. Check ordering, dates/cutoffs, units, missing data and horizon/weight conventions when they matter. Do not build tests that merely restate the implementation.
- Run expensive studies deliberately. Do not invoke experiments, full model fits or notebooks from production pytest, browser tests, CI or application imports. Research-only changes normally need the selected experiment's cheap check and the root docs helper for changed authored text, not production Python/browser/package suites. Explicit owner-requested full checkpoints still apply.
- Keep one concise experiment README and useful machine-readable results. Record the Prosper revision and dirty scope, effective settings, seed, input identities/dates, evaluation windows, environment/dependencies and failed/unavailable counts. No evidence dossiers, whole-tree hashing, repeated replay or report family is required.
- Put generated data, caches, charts and run records under ignored `.local/research/<experiment>/<run>/` from the repository root. Private inputs stay outside source and still require explicit data-and-destination authority before AI access. Shared examples use fictitious inputs; never commit confidential or restricted data or notebook outputs containing it.

## Model and application boundary

Calls to the existing core retain its mathematical input checks, unavailable states and numerical diagnostics. Preserve unknowns and failures; do not monkey-patch or weaken production checks to make a study complete. Experimental estimators or variants may live here with explicit names and assumptions, without changing the adopted application method/settings or claiming acceptance.

For out-of-sample work, prevent future information from entering estimation or portfolio selection, state the portfolio/benchmark weight conventions and compare matching horizons/units. Distinguish generated weights on historical markets from simulated market paths. Record contrary and inconclusive results. Exploratory results do not establish independent review, calibrated financial bounds or financial-use authority.

If research reveals an application bug or a useful method, propose a separate scoped production change. Edits to `src/prosper/`, application configuration, tests or contracts require the root policy and appropriate affected verification; a research directory does not waive those requirements. Privacy, source rights, owner authority, no unsolicited external messages and no trading/publication remain governed by the root agreement. No subagents unless explicitly authorized.

## Finish and removal

Report what ran, the useful finding and unresolved limits in the conversation; update the selected experiment's notes when useful. Do not update production STATUS for each experiment. Obsolete experiments can be removed without preserving compatibility. Follow the README's removal instructions if retiring the entire area; never delete private inputs or unrelated runtime state.
