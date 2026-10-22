# Current status and handoff

Updated October 22, 2026.

## Authorization and current result

Current task: **Plan T004.1: split checkpoint validation**, selected after the owner's direct `/next` and fresh sizing assessment. The combined task needs decomposition at bounded changes and completion margin: untrusted JSON/schema/identity work and cross-record financial reconciliation/readiness introduce separate new failure surfaces. The [T004.1 child plan](tasks/T004.1-checkpoint-validation-plan.md) records all six findings and two bounded briefs. **This invocation is planning only; no child implementation began.** Current conversation: **Prosper | Plan T004.1: split checkpoint validation**.

Previous completed build: **T003.2 exact-value primitives**, implemented and locally verified at `8410af4fe625096ed7b7a2ee4cfa69938ce0198a` on `codex/t003.2-exact-values`. [Task evidence](tasks/T003.2-exact-values.md) records its scoped authority, 60-test/wheel results and limits. Its changes remain local and unmerged.

Previous completed infrastructure task: **connect the owner-created GitHub repository**. The owner supplied [jpeterson92/Prosper](https://github.com/jpeterson92/Prosper) after the local setup handoff. The repository was empty when inspected; origin is now connected over HTTPS. After the owner completed GitHub browser sign-in, the retry uploaded commit `ae0360c2d3e93cd276f26f1466619beff3346fdc` and established local main tracking origin/main. [The first hosted workflow](https://github.com/jpeterson92/Prosper/actions/runs/39865871731) completed successfully for that exact commit. Repository-local Git Credential Manager configuration uses Windows Credential Manager; global Git settings and repository visibility are unchanged. GitHub API reports public visibility and default branch main. The existing owner-selected visibility/settings were not changed. This infrastructure continuation does not invoke `/next` or authorize a successor feature.

Previous completed task: **standard local filesystem development setup**, explicitly requested by the owner after moving Prosper to `C:\Users\jpete\Documents\Projects\Prosper`. The owner authorized revisiting Google Drive-driven decisions and better local dependency placement, with GitHub intended for future source backup/change control. This task changes development configuration, documentation and local verification only. It does not invoke `/next` or begin T003.2/application features. [ADR-0003](architecture/decisions/0003-adopt-standard-local-development.md) and D037 adopt the new setup; [setup evidence](tasks/SETUP-local-filesystem.md) records commands/results and remaining limitations.

The core typed Python/SQLite, React/TypeScript/Vite, FastAPI/Pydantic, analytical/research and conditional desktop choices retain their product/financial rationale. They did not depend on Google Drive. Private investor data remains outside the source repository for publication privacy and lifecycle/recovery reasons. Synthetic development artifacts may use ignored local folders.

## What exists

- Exact decimal primitives in `src/prosper/exact.py`: fixed-point strings, canonical zero, source spelling/quantum, explicit unknown reasons, field sign rules, 28-significant/12-fractional source bounds and isolated precision-80 arithmetic. Synthetic HALF_EVEN allocation preserves residuals and consumes the remaining basis on full disposal; this is not qualified broker accounting.
- 56 exact-value unit/property cases in addition to the four bootstrap cases. Four deterministic property tests use independent integer/Fraction expectations and are configured for 800 generated examples.
- Adopted product plan, sourced domain/reference specifications, architecture and conceptual contracts, roadmap/readiness gates, review dispositions, shared agent policy and bounded child briefs.
- Documentation-only T004.1 decomposition: T004.1.1 strict synthetic bundle parsing is ready to attempt; T004.1.2 checkpoint reconciliation/readiness waits on it. Neither child is implemented or verified. The parser resource limits and structural mapping in the brief are planned engineering bounds, not measured capability or financial defaults.
- Minimal typed `prosper` package with pinned `pyproject.toml`/`uv.lock`, CPython 3.12.4 x64, uv 0.13.5, Ruff 0.17.2, strict mypy 2.4.0, pytest 9.1.1, Hypothesis 6.170.5 and Hatchling 1.32.4. No new dependency versions or license commitments were selected by this setup task.
- Project-local `.venv` editable development with 20 locked distributions including Prosper; ignored `.tools/uv` bootstrap, normal user uv cache and project-local checker/test caches. The old external temporary environments are no longer required or referenced by active setup commands and were left untouched.
- `scripts/dev.ps1` bootstrap/sync/check/package operations, four toolchain qualification tests, separate fresh wheel installation/import smoke check, and `scripts/check_project.py` for authored text/local links/manifest validation.
- UTF-8/LF editor/Git conventions, expanded generated/private-file ignore rules, and a SHA-pinned read-only Windows GitHub Actions workflow with its first hosted Windows run passed.
- A local Git repository with origin `https://github.com/jpeterson92/Prosper.git`; the prior main baseline is uploaded and tracks origin/main. T003.2 remains on local branch `codex/t003.2-exact-values`; this documentation continuation is on `codex/plan-t004.1-checkpoint-validation`, based on that exact build, without upload or merge. See candidate identity below. The supplemental [manifest](PLANNING_MANIFEST.sha256) identifies authored content and excludes itself, Git internals and ignored generated/private state.

## What does not exist

No checkpoint importer, tax/risk engine, optimizer, broker adapter, database, API/UI, investor installer or released application. No real portfolios/accounts, trades, selected project software license or deployment. No independent software/tax/legal review, investor acceptance or fresh-agent instruction-loading check has occurred. Current primitive tests exercise V45's synthetic example and only limited portions of V25/V37; they establish neither full round trips nor tax/broker correctness. Hosted CI below applies to the previous uploaded baseline, not T003.2.

## T004.1 planning verification

Read-only inspection checked actual source/dependencies, prior evidence, accepted requirements and the incoming manifest. The existing `scripts/check_project.py --write-manifest` followed by its normal check passed: 54 authored files excluding the manifest, 40 Markdown files, 261 local links. `git diff --check` passed; an explicit comparison against `8410af4` returned no changes to source/tests/examples/scripts, dependency/build inputs, workflow or agent instructions. Same-agent review mapped every parent obligation to a child, confirmed the parsed-bundle versus validated-checkpoint distinction and unchanged authority/actionability boundaries, and retained each child's own tests/stop. Review clarified that F001's stipulated cash-bucket equality is not a general broker funding rule. The [plan's verification record](tasks/T004.1-checkpoint-validation-plan.md#planning-verification-and-handoff) has the exact commands and limitations; final revision is reported in the handoff.

No application, executable fixture/test, dependency/lock or workflow changes were made. Application tests, schema-library qualification, packaging, hosted CI, independent review and fresh-session child execution were not run in this planning invocation. The following T003.2 checks are prior-task evidence, not new results for checkpoint validation.

## T003.2 local verification (prior build)

Ruff lint/format, strict mypy, 60 tests (56 primitive cases plus four bootstrap cases), authored text/local-link/manifest checks, and the offline fresh-wheel build/install/import check passed using the project-local environment. An additional isolated wheel smoke check imports the new module from wheel site-packages and reproduces the diagnostic allocation. Exact command and artifact details are in [task evidence](tasks/T003.2-exact-values.md). No dependencies or lock versions changed.

Same-agent review addressed source precision, known contradictions alongside unknowns, residual bounds, context isolation and production-allocation exclusions. Independent integer/Fraction expected values are a separate calculation method, not independent human/agent review. Initial verification found a test annotation error and managed-sandbox access failures at an existing pytest cache and normal uv cache; the annotation was fixed, a targeted primitive check used ignored task-local cache, and the standard helper checks/package subsequently passed with approved cache access. No policy or global cache configuration was changed.

Full import/storage/API/browser round trips, fee/broker/tax accounting, independent specialist review, G1-G3, investor acceptance and release remain unrun. No current-task push, hosted CI, merge or deployment occurred.

## Local setup verification (prior task)

The incoming 45 authored-file manifest entries matched before editing. The local checkout is a normal filesystem folder, and the old Git repository still had no commits or remote. Python/Git prerequisite versions were observed; the earlier T003.1 host report remains historical evidence, not a newly certified Windows support matrix.

The new bootstrap downloaded the existing pinned dependencies from public PyPI and installed 20 distributions into `.venv` with editable Prosper. Base Python, global PATH and global Git settings were unchanged. The managed sandbox denied initial network access and ordinary user-cache writes; approved shell escalation allowed bootstrap and the offline package check. These are execution-sandbox restrictions, not a reason to restore Google Drive-specific project paths.

Initial direct Ruff checks found three long lines in the new checker; Ruff formatting corrected them. Strict mypy and all four bootstrap tests passed on the migrated checkout. The offline wheel build/install check passed in a newly created ignored environment and imported the package and `py.typed` from that environment's site-packages with isolated Python. The final helper check passed Ruff lint/format, strict mypy, all four tests and authored-project checks (50 authored files, 38 Markdown files, 221 local links). Negative probes, ignore/decision/instruction/progression checks and staged LF/whitespace checks also passed. A sandbox-owned shared pytest scratch root was left untouched; the helper now uses unique ignored project-local scratch per run. Exact Git and checkout evidence is in the setup record.

Same-agent source/configuration and policy-consistency review completed. Independent review, broader OS/interpreter qualification, branch protection, financial/application checks, investor installation/acceptance and release remain unrun. The hosted Windows developer baseline is separate evidence below; it does not qualify an investor installer or other platforms. No tax/risk/data/release policy changed. G0 remains document-ready for application work; G1-G3 remain unpassed.

## Hosted GitHub verification

After owner-completed authentication, `git push -u origin main` succeeded and `git ls-remote origin refs/heads/main` matched `ae0360c2d3e93cd276f26f1466619beff3346fdc`. GitHub reports public visibility, default branch main and `protected=false`; no visibility or branch-protection settings were changed.

[Run 39865871731](https://github.com/jpeterson92/Prosper/actions/runs/39865871731) / [Windows job 120127797046](https://github.com/jpeterson92/Prosper/actions/runs/39865871731/job/120127797046) completed **successfully** for that uploaded commit. Observed successful steps: checkout, exact Python setup, locked dependency bootstrap, lint/format/strict typing/four bootstrap tests/authored-project checks, and fresh wheel build/install/import. This is an observed clean hosted developer setup in addition to the local results. It establishes no financial/application correctness, independent review, investor installation or release acceptance.

The handoff documentation is checked, committed and pushed after recording that baseline result. Its exact revision and latest workflow outcome are reported in the final handoff, avoiding a self-referential commit/run identity in its own content.

## Candidate identity

This planning invocation started from clean `codex/t003.2-exact-values` at `8410af4fe625096ed7b7a2ee4cfa69938ce0198a`. Its documentation candidate is on `codex/plan-t004.1-checkpoint-validation`; the exact final local commit is reported in the handoff and resolved by `git rev-parse HEAD`, avoiding a self-referential commit hash in its own content. The refreshed [authored manifest](PLANNING_MANIFEST.sha256) fingerprints current source, tests and docs. Source/tests/runtime metadata/lock/workflow remain identical to the incoming build. Prior hosted runs establish no CI result for this local candidate. No upload, merge, repository-setting change or financial-use release is included.

## Next task and remaining gates

**Single next candidate: [T004.1.1: strict synthetic bundle parsing](tasks/T004.1-checkpoint-validation-plan.md#t00411-strict-synthetic-bundle-parsing)**. T003.1 and T003.2 are locally verified; T004.1 is now a parent scope. T004.1.1 is ready to attempt after a fresh fit/dependency assessment under the [next-step protocol](engineering/NEXT_STEP.md); library qualification, exact fixture/schema mapping and parser checks belong to that later execution. T004.1.2 waits on T004.1.1; T003.3 persistence still waits on completed T004.1. No child implementation began in this planning run.

T002/T017 must obtain early G1 evidence for a supported broker/manual workflow and permitted benchmark/quote/history inputs before substantial broker-facing/quantitative work. T018 carries written state/recovery requirements into future slices. G2/G3 still require model, specialist and investor evidence before financial use. Ready means ready to attempt, not accepted/released.

The decision register has **25 accepted, 5 confirmed and 7 open** entries (37 total). Open: D010 broker/workflow; D012 risk data/settings, discrete method and investor limits; D014 license; D016 distribution/service legal qualification; D017 supported tax year/freshness; D018 name/public distribution/release/support details (owner-created GitHub repository and connected origin now recorded); D027 first experiment. No previously accepted product choice needs repeated approval solely because the folder changed.

The source connection, initial upload and first hosted CI qualification are complete. Main currently has no branch protection; requiring the Development checks workflow before merges is a separate owner-directed repository-setting action. No visibility or repository-setting changes were made. GitHub source backup does not cover ignored files/private investor state, which needs its own future application backup/recovery flow.

## Historical evidence

[T003.1's original execution report](tasks/T003.1-development-baseline.md) preserves the two external-environment qualification, exact dependency inventory, original four tests and earlier denied staging/no-commit fallback. Its Drive-specific procedure is superseded. The [foundation child plan](tasks/T003-T004-foundation-plan.md) preserves the earlier planning-only decomposition and serial progression; current shared/future boundaries now reference ADR-0003. The [pre-implementation review](reviews/2026-10-22-pre-implementation-review.md) preserves findings, readiness checkpoints and action dispositions. Original counts and unrun checks in those historical reports describe those runs, not current totals.

Sources/domain requirements and the synthetic reference arithmetic were checked during the earlier planning/review work; this setup task does not renew those financial/legal checks. Accepted baseline scope and review actions remain [ADR-0001](architecture/decisions/0001-adopt-project-architecture.md) and [ADR-0002](architecture/decisions/0002-adopt-critical-review-actions.md).
