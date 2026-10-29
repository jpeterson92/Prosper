# Local research

Disposable experiments that use Prosper's calculation core, with a separate environment and a lighter [working agreement](AGENTS.md). The dependency runs one way: research imports `prosper`; the application never imports research. This directory is outside the application wheel, production test discovery, Ruff and strict mypy scopes. Commits changing only `research/` skip automatic push/PR CI; manual CI and mixed application changes retain the normal checks. The root text/link checker still checks authored research files.

## Setup and use

Run from the repository root in PowerShell. If the project-local uv/Python environment is missing, first run `./scripts/dev.ps1 -Command bootstrap` as described in the [development guide](../docs/engineering/DEVELOPMENT.md). Use a shell without a `UV_PROJECT_ENVIRONMENT` override; uv must create `research/.venv`, not target the application environment. Do not use `--active`.

```powershell
$researchPython = (Resolve-Path ./.venv/Scripts/python.exe).Path
./.tools/uv/Scripts/uv.exe sync --project research --locked --python $researchPython

# Import smoke check; this does not fit or evaluate a model.
./research/.venv/Scripts/python.exe -c "from prosper.covariance import fit_covariance; print(fit_covariance.__module__)"
```

The expected smoke output is `prosper.covariance`. Prosper is installed editable from the parent checkout, so subsequent core source edits are visible to research without copying code. Its internal APIs have no research compatibility guarantee. Prefer a small local adapter over a new production research API. Useful starting points include [covariance fitting](../src/prosper/covariance.py), [risk input assembly](../src/prosper/risk_inputs.py) and the [risk contract](../docs/domain/RISK_MODEL.md).

Add plotting/notebook tools only when an experiment needs them. For example, `./.tools/uv/Scripts/uv.exe add --project research <package>` changes research dependencies and its lock only. After intentionally changing the parent application's dependencies, refresh `research/uv.lock` with `./.tools/uv/Scripts/uv.exe lock --project research` and sync again. Ordinary setup uses `--locked` so a stale lock fails visibly. The application dev dependency group is not installed transitively. Build constraints match the parent's current build tooling for local editable installation; no delivery artifact is required for routine research.

## Add an experiment

Create one directory under `experiments/` with a short README and a direct `run.py`; add a notebook only if useful. See the [experiment notes](experiments/README.md) for a minimal outline. Execute from the repository root using `./research/.venv/Scripts/python.exe research/experiments/<name>/run.py`. Keep dependencies here and outputs under `.local/research/<name>/<run>/`. Environments and notebook checkpoints are ignored. Keep committed notebooks free of generated outputs and embedded private/source data.

Do not create a shared helper package until experiments actually need one. Scripts do not need full typing, test coverage, compatibility layers or production abstractions. A small smoke run and checks that protect the conclusion are sufficient. Expensive experiments are manually invoked and stay out of application CI/tests. Research-only authored text changes can use `./scripts/dev.ps1 -Command docs`; production edits and explicit full checkpoints follow the root policy.

At each useful run, retain settings, seed, source identities/dates, evaluation windows, successes/failures and a concise result note alongside the results. Record `git rev-parse HEAD` and relevant `git status --short`/diff details if the checkout is dirty; a commit alone does not identify uncommitted model edits. The installed dependency versions can be recorded with `./.tools/uv/Scripts/uv.exe pip freeze --python ./research/.venv/Scripts/python.exe`. Record local script changes too when needed to reproduce a result. No general provenance framework is required.

## Retire or promote

Promote useful findings through a separate application change with the normal checks and any applicable model review. A research result does not automatically change model settings or acceptance claims.

To retire all research, remove this directory, its root AGENTS exception, README/navigation/development/validation references and the two `research/**` CI path exclusions. Generated output under `.local/research/` can be removed separately when deliberately chosen; leave private inputs and unrelated workspaces untouched. The application has no dependency to unwind. Root notebook-checkpoint ignore rules may remain useful or be removed when unused.
