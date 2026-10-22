# ADR-0003: Standard local development and GitHub readiness

Date: October 22, 2026. Status: **Accepted**. Approver: project owner in the explicit filesystem migration/setup request.

## Question and authority

Which restrictions were consequences of developing inside Google Drive, and what should replace them now that every developer and investor is assumed to use a standard local filesystem folder?

The owner moved Prosper to `C:\Users\jpete\Documents\Projects\Prosper`, asked to redo decisions driven by Drive, authorized better project-local dependency installation, and identified GitHub as the intended future source backup/change-control host. This authorizes local setup changes and preparation of CI configuration. Remote creation, upload, visibility, publication and application feature implementation remain separate actions.

## Decision

1. Treat each checkout as a normal local working directory. Use its ignored `.venv` for Python dependencies and editable installation of `src/prosper`. A developer without uv can bootstrap the already pinned version in ignored `.tools/uv`; an existing compatible uv installation is also usable. Keep dependency metadata and `uv.lock` in Git.
2. Use ordinary tool behavior: uv's reusable per-user cache, project-local Ruff/mypy/pytest/Hypothesis caches and bytecode, and ignored project-local pytest scratch files isolated per run. Other temporary-file use retains normal OS behavior. Remove the external `RuntimeRoot`/named-environment protocol, sync-provider name detection, forced temp/cache redirection and prohibition on source-relative generated tooling. Other checkouts have their own `.venv`; do not move or copy environments between checkout paths.
3. Permit synthetic development databases, logs, browser results, package probes and other generated evidence in ignored `.local`/artifact directories. Keep real portfolio data, credentials and private backups outside the repository. The future installed application's per-user data directory remains separate from source and dependencies for privacy, lifecycle and recovery reasons; it is not a Google Drive workaround. Final application path/override behavior is still unimplemented.
4. Use UTF-8, LF text, `.editorconfig` and Git text/binary attributes. The old blanket `* -text` byte-preservation setting is superseded. Normalize existing authored text once and regenerate the hash manifest. Git commits become the primary source identity when available; the manifest remains a supplemental authored-tree check/fallback and excludes generated/ignored files and itself.
5. Prepare a Windows x64 GitHub Actions workflow using the same bootstrap/check/package commands, read-only repository permissions, SHA-pinned official actions and no publishing/deployment step. A local wheel smoke check uses a fresh environment to verify ordinary package installation separately from editable development. Hosted execution and branch protection must be verified after the owner connects the remote.

## Audit and alternatives

| Prior choice | Drive dependency | Result |
| --- | --- | --- |
| Temporary external environments/caches and source path rejection | Direct workaround for synchronized source | Superseded by local `.venv`, normal caches and ignored generated artifacts |
| Non-editable install on every normal development check | Not inherently required by Drive, but coupled to the external/stale-code workflow | Use editable development plus a separate fresh wheel installation check |
| Disabled bytecode/Ruff/pytest caches and forced scratch redirection | Direct source-artifact avoidance | Restore ordinary caches; isolate pytest scratch per checkout/run without process TEMP/TMP redirection |
| Byte-preserving Git attributes/hash-only candidate identity | Earlier no-commit fallback, not a cloud requirement | Normalize text; prepare normal Git history; retain supplemental manifest |
| Local single-user modular architecture and SQLite | Investor privacy, local operation and transactional authority | Retain; folder relocation does not justify hosted state/microservices |
| Python/React/FastAPI, analytical/research tools and staged Tauri evaluation | Financial ecosystem, contracts, product and learning goals | Retain accepted choices/qualification conditions |
| Private user data outside source and consistent SQLite backup | Source publication privacy, install lifecycle and transactional recovery | Retain with filesystem-neutral rationale; GitHub source backup is separate from investor-data backup |

Keeping external environments would add manual path coordination without a present requirement. Vendoring installed dependencies would bloat source history and embed machine-specific binaries. A container, Conda migration, global configuration changes or installing the entire future stack has no demonstrated benefit for this bounded baseline. No dependency versions or license commitments change.

## Consequences and evidence

This supersedes the filesystem-specific parts of D007, ADR-0001 and T003.1's original procedure; their original execution reports remain historical evidence. D037 records the new adopted setup; D018 now records the GitHub preference while visibility, remote and release details stay open. Existing financial/tax/data/release gates and T003.2's position as the next feature task are unchanged.

See the [development guide](../../engineering/DEVELOPMENT.md) for commands and [setup evidence](../../tasks/SETUP-local-filesystem.md) for actual observations, Git identity and unrun checks. Official references: [uv editable/locked syncing](https://docs.astral.sh/uv/concepts/projects/sync/), [uv cache behavior](https://docs.astral.sh/uv/concepts/cache/), [Git text attributes](https://git-scm.com/docs/gitattributes), and [GitHub Python CI](https://docs.github.com/en/actions/tutorials/build-and-test-code/python). Workflow pins come from official [checkout](https://github.com/actions/checkout/commit/3d3c42e5aac5ba805825da76410c181273ba90b1) and [setup-python](https://github.com/actions/setup-python/commit/6d4fd22b20465ccc0f7354476588e8df7c9ca0e0) commits. This is local engineering qualification, not hosted CI, independent review or investor installation acceptance.

Reconsider when supported platforms, reproducibility measurements, private-data requirements or actual packaging evidence change. Do not restore sync-provider restrictions without a concrete new requirement.
