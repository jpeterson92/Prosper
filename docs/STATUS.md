# Current status and handoff

Updated October 22, 2026.

## Authorization and current result

Latest task: **standard local filesystem development setup**, explicitly requested by the owner after moving Prosper to `C:\Users\jpete\Documents\Projects\Prosper`. The owner authorized revisiting Google Drive-driven decisions and better local dependency placement, with GitHub intended for future source backup/change control. This task changes development configuration, documentation and local verification only. It does not invoke `/next` or begin T003.2/application features. [ADR-0003](architecture/decisions/0003-adopt-standard-local-development.md) and D037 adopt the new setup; [setup evidence](tasks/SETUP-local-filesystem.md) records commands/results and remaining limitations.

The core typed Python/SQLite, React/TypeScript/Vite, FastAPI/Pydantic, analytical/research and conditional desktop choices retain their product/financial rationale. They did not depend on Google Drive. Private investor data remains outside the source repository for publication privacy and lifecycle/recovery reasons. Synthetic development artifacts may use ignored local folders.

## What exists

- Adopted product plan, sourced domain/reference specifications, architecture and conceptual contracts, roadmap/readiness gates, review dispositions, shared agent policy and bounded child briefs.
- Minimal typed `prosper` package with pinned `pyproject.toml`/`uv.lock`, CPython 3.12.4 x64, uv 0.13.5, Ruff 0.17.2, strict mypy 2.4.0, pytest 9.1.1, Hypothesis 6.170.5 and Hatchling 1.32.4. No new dependency versions or license commitments were selected by this setup task.
- Project-local `.venv` editable development with 20 locked distributions including Prosper; ignored `.tools/uv` bootstrap, normal user uv cache and project-local checker/test caches. The old external temporary environments are no longer required or referenced by active setup commands and were left untouched.
- `scripts/dev.ps1` bootstrap/sync/check/package operations, four toolchain qualification tests, separate fresh wheel installation/import smoke check, and `scripts/check_project.py` for authored text/local links/manifest validation.
- UTF-8/LF editor/Git conventions, expanded generated/private-file ignore rules, and a prepared SHA-pinned read-only Windows GitHub Actions workflow. Hosted execution remains unperformed.
- A local Git repository, with no remote. See candidate identity below for the current commit/permission result. The supplemental [manifest](PLANNING_MANIFEST.sha256) identifies authored content and excludes itself, Git internals and ignored generated/private state.

## What does not exist

No financial/application behavior, exact-value primitives, tax/risk engine, optimizer, broker adapter, database, API/UI, investor installer or released application. No real portfolios/accounts, trades, public repository, remote upload, selected project software license or deployment. No independent software/tax/legal review, investor acceptance, fresh-agent instruction-loading check or hosted CI pass has occurred. The four tests qualify the toolchain only and cover none of V01-V47's financial/application scenarios.

## Local setup verification

The incoming 45 authored-file manifest entries matched before editing. The local checkout is a normal filesystem folder, and the old Git repository still had no commits or remote. Python/Git prerequisite versions were observed; the earlier T003.1 host report remains historical evidence, not a newly certified Windows support matrix.

The new bootstrap downloaded the existing pinned dependencies from public PyPI and installed 20 distributions into `.venv` with editable Prosper. Base Python, global PATH and global Git settings were unchanged. The managed sandbox denied initial network access and ordinary user-cache writes; approved shell escalation allowed bootstrap and the offline package check. These are execution-sandbox restrictions, not a reason to restore Google Drive-specific project paths.

Initial direct Ruff checks found three long lines in the new checker; Ruff formatting corrected them. Strict mypy and all four bootstrap tests passed on the migrated checkout. The offline wheel build/install check passed in a newly created ignored environment and imported the package and `py.typed` from that environment's site-packages with isolated Python. The final helper check passed Ruff lint/format, strict mypy, all four tests and authored-project checks (50 authored files, 38 Markdown files, 221 local links). Negative probes, ignore/decision/instruction/progression checks and staged LF/whitespace checks also passed. A sandbox-owned shared pytest scratch root was left untouched; the helper now uses unique ignored project-local scratch per run. Exact Git and checkout evidence is in the setup record.

Same-agent source/configuration and policy-consistency review completed. Independent review, other-machine/OS/interpreter checks, hosted workflow/branch protection, financial/application checks, investor installation/acceptance and release remain unrun. No tax/risk/data/release policy changed. G0 remains document-ready for application work; G1-G3 remain unpassed.

## Candidate identity

Local staging and `git diff --cached --check` succeeded using the existing author identity; all 51 staged files have LF working/index text. This setup is being recorded as the initial local `main` checkpoint after final checks. Its exact commit ID is reported in the task handoff and can be read with `git rev-parse HEAD`; the evidence file in that commit describes its tree without embedding a self-referential commit hash. No remote, push or public release is implied. The [setup evidence](tasks/SETUP-local-filesystem.md) and supplemental authored-tree manifest record verification limits; neither is a release signature.

## Next task and remaining gates

**Single next feature candidate: [T003.2: exact-value primitives](tasks/T003-T004-foundation-plan.md#t0032-exact-value-primitives)**. T003.1 remains locally qualified with its procedure superseded by ADR-0003. The next invocation must reassess fit and may execute only T003.2 under the [next-step protocol](engineering/NEXT_STEP.md). This setup request did not authorize its successor.

T002/T017 must obtain early G1 evidence for a supported broker/manual workflow and permitted benchmark/quote/history inputs before substantial broker-facing/quantitative work. T018 carries written state/recovery requirements into future slices. G2/G3 still require model, specialist and investor evidence before financial use. Ready means ready to attempt, not accepted/released.

The decision register has **25 accepted, 5 confirmed and 7 open** entries (37 total). Open: D010 broker/workflow; D012 risk data/settings, discrete method and investor limits; D014 license; D016 distribution/service legal qualification; D017 supported tax year/freshness; D018 remote visibility/setup, name/release/support details (GitHub preference now confirmed within its rationale); D027 first experiment. No previously accepted product choice needs repeated approval solely because the folder changed.

The next optional infrastructure action is owner-directed GitHub repository/visibility selection, remote connection and initial upload, followed by an observed hosted workflow run and appropriate branch protection. GitHub source backup does not cover ignored files/private investor state, which needs its own future application backup/recovery flow.

## Historical evidence

[T003.1's original execution report](tasks/T003.1-development-baseline.md) preserves the two external-environment qualification, exact dependency inventory, original four tests and earlier denied staging/no-commit fallback. Its Drive-specific procedure is superseded. The [foundation child plan](tasks/T003-T004-foundation-plan.md) preserves the earlier planning-only decomposition and serial progression; current shared/future boundaries now reference ADR-0003. The [pre-implementation review](reviews/2026-10-22-pre-implementation-review.md) preserves findings, readiness checkpoints and action dispositions. Original counts and unrun checks in those historical reports describe those runs, not current totals.

Sources/domain requirements and the synthetic reference arithmetic were checked during the earlier planning/review work; this setup task does not renew those financial/legal checks. Accepted baseline scope and review actions remain [ADR-0001](architecture/decisions/0001-adopt-project-architecture.md) and [ADR-0002](architecture/decisions/0002-adopt-critical-review-actions.md).
