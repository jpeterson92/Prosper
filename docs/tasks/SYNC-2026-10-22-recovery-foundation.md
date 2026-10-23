# GitHub synchronization: import and recovery foundation

## Authority and source scope

On October 22, 2026 the owner explicitly asked, "Can you sync everything to GitHub?" This authorizes local main integration, committing sync documentation and uploading all accumulated authored changes/history to the configured [Prosper repository](https://github.com/jpeterson92/Prosper). It does not invoke the next application stage or authorize a release, deployment, tag, repository-settings change, broker/account access or real-data upload. Actual conversation title: **Prosper | Sync: recovery foundation to GitHub**.

The working tree was clean on `codex/t004.3.2.2-guarded-recovery` at `460ad8784844acdfc2959e73724ea2d42fc9b391`. Fresh `git fetch origin --prune` confirmed origin/main at `935a761cf506ba939acfab060f569c4140700993`. All local branch tips were ancestors of the candidate; the eight new commits form one linear descendant history. Fast-forwarding main includes their complete source/history without separately publishing redundant feature-branch names. No force push, history rewrite or branch deletion was used.

| Commit | Accumulated change |
| --- | --- |
| `7895996` | Bounded preview/atomic activation plan |
| `9043f84` | Remaining roadmap split into paired components |
| `3a19614` | Durable synthetic import previews and rejection |
| `10bc06a` | Atomic activation and original command receipts |
| `c4a4f10` | Consistent synthetic backup and verified isolated restore |
| `e93b030` | Bounded interrupted-recovery child plan |
| `47d9521` | Read-only interrupted-foundation inspection |
| `460ad87` | Guarded recovery and conservative orphan cleanup |

The [remaining work plan](REMAINING_WORK_PLAN.md), child reports, developer documentation, tests, synthetic fixtures and authored manifest are included. [Earlier synchronization evidence](SYNC-2026-10-22-github.md) remains historical. Ignored environments, tool caches, generated databases/evidence/logs, qualification scripts and wheels remain outside source control; source synchronization is not an investor-state backup. No credentials were printed or added; existing Git Credential Manager handled Git authentication.

## Prior hosted result and local qualification

Per the [authoritative sync protocol](../engineering/NEXT_STEP.md#github-synchronization-and-hosted-ci-handoff), the public GitHub Actions API was read at intake before upload. The preceding relevant **Development checks** [run 39895657790](https://github.com/jpeterson92/Prosper/actions/runs/39895657790) was **completed/success** for exact incoming remote revision `935a761cf506ba939acfab060f569c4140700993`. The returned main history contained no known unresolved failure; no diagnostic remediation was needed. This prior success is not attributed to new source.

| Actual check/action | Observed result |
| --- | --- |
| `scripts/dev.ps1 -Command check` | Offline locked sync, Ruff lint/format, strict mypy and **532 tests passed in 92.41s**, no skips; then 90 authored files, 55 Markdown files and 489 local links passed |
| `scripts/dev.ps1 -Command package` | Fresh offline wheel, isolated locked runtime/dependency compatibility, installed import and typing-marker checks passed |
| `git diff --check origin/main..HEAD` before integration | Passed across the eight accumulated commits |
| Main integration and source upload | `git switch main`, `git merge --ff-only codex/t004.3.2.2-guarded-recovery` and `git push origin main` succeeded without conflicts; main advanced from `935a761` to `460ad87` |
| Remote source verification | `git ls-remote origin refs/heads/main` exactly matched `460ad8784844acdfc2959e73724ea2d42fc9b391`; local main tracked origin/main with a clean working tree |

Fresh local wheel: `.local/package-check/c3a98c845d5c4349af440ac7a2ba7859/dist/prosper_local-0.0.0-py3-none-any.whl`. SHA-256: `1589ab6ffdd9cd871ad3454f7ba1d5e3b86a004d5b44fbaec4cdd4058e3d5e04`, equal to the preceding guarded-recovery build's wheel. The application implementation fingerprint remains `884849367fc952764abe79ad9f1d2d83b07602bd44122ddf5116ed67580666b5`; no application Python, tests, dependencies, workflow or build configuration changed during this sync.

The deeper installed-wheel cleanup/recovery scenarios and independently reasoned synthetic expected values remain evidence of [T004.3.2.2](T004.3.2.2-guarded-recovery.md); this sync repeated the full test suite and fresh-wheel helper, not those two separate manual scenarios. Passing these checks does not establish independent software/tax/risk review, investor installation/acceptance or financial readiness.

## Documentation follow-up and handoff

After the verified source upload, a documentation-only follow-up updates [STATUS](../STATUS.md), the [change log](../../CHANGELOG.md), this report and the [authored manifest](../PLANNING_MANIFEST.sha256). `scripts/check_project.py --write-manifest`, the read-only authored checker (**91 files, 56 Markdown files, 501 local links**), `git diff --check` and same-agent scope/authority review passed. The exact final commit/remote identity is reported in the handoff without a self-referential hash. No application test/package rerun is needed for these documentation-only edits. The final upload is verified against the remote ref.

New Actions results, including the source upload and final documentation checkpoint, are deliberately **unverified**. This task does not wait, poll, watch or create a monitor; the next authorized sync inspects the preceding relevant result and any known unresolved failure. No workflow or release gate was disabled. No unresolved local finding blocks source synchronization.

**Single next application candidate remains [T003.4.1: protected loopback runtime and session boundary](REMAINING_WORK_PLAN.md#t0034-local-typed-api)** after fresh dependency/sizing assessment. No API implementation or dependency qualification began. Independent review, target-scale/long-lock qualification, investor workflow/install/update/recovery, broker/data qualification, G1-G3 and release remain outstanding. Source sync does not change accepted policy or the open owner decisions.
