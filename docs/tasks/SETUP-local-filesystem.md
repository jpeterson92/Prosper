# Standard local filesystem setup evidence

Date: October 22, 2026. Authority: explicit owner request to revisit Google Drive-driven setup after moving to a normal local folder, install dependencies locally where appropriate, and prepare for future GitHub source backup/change control. [ADR-0003](../architecture/decisions/0003-adopt-standard-local-development.md) records the adopted decisions and audit. This is local setup, not a next-step feature invocation; T003.2 remains the next feature candidate.

## Baseline and changes

All 45 incoming manifest entries matched. Git was initialized on unborn `main` with no commit or remote. Observed prerequisite executables: `C:\Python312\python.exe` and Git 2.50.1.windows.1. Existing uv 0.13.5 was available only in the old temporary tools environment, so the documented bootstrap was exercised independently in ignored `.tools/uv`. Old external tools/environments were preserved and are no longer setup dependencies.

Replaced external `RuntimeRoot`/environment-name plumbing, source/sync-name rejection, eight forced environment/cache/temp overrides and non-editable daily installs with `.venv` editable development, normal caches, per-run ignored project-local pytest scratch and two restored process overrides. Added a separate offline wheel-install/import smoke check, authored-project checker, LF/editor attributes, generated/private ignore rules and prepared Windows GitHub CI. Updated active architecture, decision register, agent/contributor guidance and future task boundaries. Historical T003.1 execution observations remain labeled historical.

## Commands and observed evidence

- Incoming SHA-256 manifest verification: 45/45 matched before editing.
- `scripts/dev.ps1 -Command bootstrap`: created `.tools/uv` and `.venv`; public PyPI supplied the same pinned 19 external distributions plus editable Prosper (20 total). Managed network escalation was approved after a sandbox socket denial. Base Python/global settings unchanged.
- Direct Ruff lint initially found three long lines in the new checker; Ruff formatting remediated them. Subsequent lint passed. Strict mypy passed; pytest collected and passed all four bootstrap tests, including expected failing subprocesses.
- `scripts/dev.ps1 -Command package`: offline locked sync, wheel build, fresh isolated environment, wheel-only install and isolated import/typing-marker assertion passed. Output is ignored synthetic `.local/package-check/<unique-id>`. User-cache access required approved escalation after the sandbox denied the uv cache lock; this is a tool sandbox boundary, not a project filesystem limitation.

The first aggregate run exposed sandbox-owned pytest cache/scratch paths inaccessible to the normal Windows user. Removed only generated project caches from this run; a pre-existing shared OS pytest temp root was left untouched. The helper now uses a unique ignored `.local/pytest/<unique-id>` directory for each run, avoiding cross-project/run scratch collisions without redirecting process TEMP/TMP. An initial local-scratch attempt omitted its parent directory; explicit parent creation corrected it. Final aggregate/Git results are recorded below. A deliberately broken local heading was rejected, both process overrides and working directory were restored after an expected missing-uv failure, all 12 representative ignore paths were excluded, and D001-D037/shared instruction import/single-ready-child consistency checks passed. The commands above were actually exercised; hosted CI, independent review and investor installation were not.

## Review and limits

The audit found no Drive rationale for replacing typed Python, SQLite authority, modular local architecture, React/API contracts, staged analytics/research or conditional Tauri evaluation. Private-data separation and consistent SQLite backups remain necessary under source publication and application-lifecycle concerns. Standard local synthetic runtime directories are now permitted; no real data was accessed. No dependency upgrades, license selection, financial behavior, remote repository, upload or deployment occurred.

The GitHub workflow is prepared source configuration only. Official action SHAs were retrieved from the upstream release/commit pages; the first hosted Windows/Python bootstrap and workflow run still need observation after remote setup. No local result establishes hosted CI or other-machine compatibility. The exact Python patch remains the previously qualified version; upgrading it is separate qualification work.

## Final qualification and local identity

- `scripts/dev.ps1 -Command check` passed as the normal Windows user: locked offline sync, Ruff lint/format (six scoped Python files), strict mypy (three checked source files), **4/4 bootstrap tests**, and authored-project checks covering **50 authored files, 38 Markdown files and 221 local links**. Generated/ignored environment/cache/probe files are excluded from these counts; the manifest adds one versioned file.
- Local staging of 51 authored/manifest files and `git diff --cached --check` succeeded. `git ls-files --eol` showed LF in both index and working tree for all 51 files. Text/binary attribute checks passed. Existing author identity was available; no global Git/identity/signing change was made. No remote exists.
- `git checkout-index` into a new ignored local directory reproduced all 50 authored manifest hashes; staged whitespace checks also passed. This establishes a local Git checkout round trip, not another-machine installation or hosted CI.
- Same-agent review traced current agent/architecture/child-task guidance to ADR-0003 and retained the original baseline execution record as historical evidence. No subagents or independent-review claims.
- Lock SHA-256: `d7b66d2ed4a59a94ea694b4893c3465d0e3ba3cc1f26a134608aa501ed786be1`. Dependency versions/selection did not change. The final manifest is regenerated after evidence edits and identifies the authored tree without itself.

Candidate identity: initial local `main` checkpoint containing this evidence is created after final checks; its exact ID is in the task handoff (`git rev-parse HEAD`). A commit cannot embed its own hash, so this evidence describes the tree/checks rather than predicting its revision. No hosting, push or release follows from that local checkpoint. Next feature action: reassess T003.2 under the existing next-step protocol. Optional infrastructure action: owner-directed GitHub remote/visibility/upload, then observe CI and configure PR protection. No successor feature implementation occurred.

## Follow-up: owner-created GitHub repository

The owner subsequently supplied `https://github.com/jpeterson92/Prosper`. Read-only website and `git ls-remote` inspection found an empty repository with no branch refs. Connected local origin to `https://github.com/jpeterson92/Prosper.git`. `git push -u origin main` failed with GitHub's invalid-username/token response; nothing was uploaded and no upstream/hosted workflow run was established.

The existing global credential helper was `store`. No credential contents were read or printed. Configured only this repository with a helper-chain reset followed by `manager` and `credential.credentialStore=wincredman`, leaving global settings unchanged. Device login was attempted, produced no sign-in instructions in the managed session and was canceled. The owner needs to complete browser authentication in their own terminal using `git credential-manager github login --username jpeterson92 --browser` from this checkout. No passwords/tokens belong in source or chat.

Updated current status, source-host decision details, project/development/contribution guidance and README to reflect the connected remote and exact authentication blocker. Financial/application scope, next task, workflow and dependencies are unchanged. Checked authored local links/manifest and Git whitespace; no application/toolchain rerun is needed for this documentation-only continuation. Initial baseline is `234382dcf3f82b9b25eaeab7d27e453dcdbc185f`; follow-up local commit identity is reported in its handoff. GitHub authentication/upload, first hosted CI observation and branch protection remain unperformed. Repository visibility/settings and project license were not changed.
