# Current status and handoff

Updated October 25, 2026 PDT (October 25 UTC). This is the compact live handoff. Task reports own detailed evidence; the [dated history](STATUS-2026-10-24-history.md) retains prior status verbatim and is not required intake.

## Current task and authority

**D047 policy/backlog alignment complete, documentation only**, explicit owner instruction that the application has never been released and future work need not preserve previous implementations. [ADR-0013](architecture/decisions/0013-adopt-unreleased-clean-break-development.md), root agent policy, contracts/templates and the [T019 sequence](tasks/T019-advisory-remediation.md) now remove old-reader, dual-API, schema-migration/export-bridge and old-backup support obligations. Update current callers/fixtures and retain meaningful financial/security tests; use a scoped fresh development runtime/reimport when a breaking change needs it. Current-format saved reports, transactions/retries and backup/restore remain required. No silent runtime wipe or unrelated/private-data deletion is authorized.

Added **T019.3.1** to remove the compatibility-only checkpoint bridge introduced in .3 and establish clean-start normalized records. Revised .4 history/assembly, .5 current-format recovery, .6 current API/UI and .7 residual code/test/tooling cleanup. Historical reports remain evidence for their original candidates, not preservation obligations. [Policy execution evidence](tasks/T019-advisory-remediation.md#d047-policy-and-backlog-alignment) records scope, review, checks and limitations. Final `./scripts/dev.ps1 -Command docs` passed authored-text/link/manifest and diff checks. No application/test/fixture/dependency mutation, runtime deletion, new source acquisition, Git mutation or successor implementation occurred in this policy turn.

Prior T019.3 remains implemented and locally verified at its original service boundary: **662 selected tests**, lint/format/strict typing/project checks and isolated package/source/run/worksheet round trips. [Original execution evidence](tasks/T019-advisory-remediation.md#t0193-execution) and `.local/t019.3/verification.json` identify that candidate. This is reused historical evidence, not fresh application verification of this documentation turn. Its `advisory_legacy.py` bridge and parallel old-reader obligations are now explicitly obsolete, with removal queued; no runtime cleanup is claimed complete. Current legacy backups still omit the advisory database; .5 must provide current-format recovery before .6 UI adoption, without supporting old backups. Independent financial/model review, G1-G3 and release qualification remain open.

## Next task and remaining gates

**Single next candidate: T019.3.1, remove the unreleased checkpoint bridge**, fresh assessment using its [bounded brief](tasks/T019-advisory-remediation.md#t01931-remove-the-unreleased-checkpoint-bridge) and the [current record contract](architecture/DATA_CONTRACTS.md#advisory-storage-and-clean-start-records). Remove `advisory_legacy.py` and compatibility-only mapper/export tests/examples, exercise the current normalized import/run workflow from clean synthetic state, and keep material source/unknown/quantity/retry checks. No replacement shim, old-schema loader, migration/export qualification or dual-write period is required. T019.4-.7 wait on their revised predecessors; other features remain held behind T019. No cleanup implementation began in this policy turn.

Active gates and constraints:

- **Independent financial/model review and G1-G3 remain open.** Q03 independent review is unresolved; analytical shrinkage equality is unsupported. Q04 forward calibration and Q05 complete qualified real inputs retain their owners. Engineering checks do not imply financial acceptance or release.
- **Real-input integration:** source identity, calendar, compatible OHLC/returns/actions/vintages and full usable coverage must be qualified before use. D043 permits isolated synthetic qualification while G1 is open. Preserve the T017.1.3 research artifacts, all 2,448 membership rows, original 98.54 percentage-point rounded weight sum and all errors/ambiguities/short-invalid histories; no guessed mappings or silent rescaling; D045 permits explicit retained-equity value rescaling; D046 implements approximate analytical weights with source/exclusion facts preserved.
- **Broker/funding/workflow:** retail Fidelity and full/partial specific-lot sales are settled development assumptions, not qualified confirmation/correction/funding capability. E01-E04 and the owner-observed paper walkthrough retain their evidence owners and block dependent operational features. No account access, real portfolio processing or trading is authorized here.
- **Open owner decisions:** D010 broker workflow; D012 risk/settings/discrete method/investor limits; D014 license; D016 distribution/service; D017 supported years/freshness; D018 release/name/support; D027 first experiment. See the [decision register](DECISIONS.md), including adopted D038-D045; do not reopen settled decisions without new evidence.

## What exists

The synthetic import foundation covers exact-value parsing/inspection, evidence/SQLite, previews/activation, guarded recovery, typed local API and browser review. Fictional Fidelity/assembled-input diagnostics are separate from persisted broker integration. The Python numerical stack, synthetic OHLC innovations/scalar volatility fits and [analytical target](tasks/T006.2.2.2.1-analytical-target.md), DCC pair fitting, composed covariance forecasts and industry diagnostics have local synthetic component evidence; qualified real integration, calibrated TE and actionable plans remain pending. Navigate by [subsystem](engineering/AGENT_WORKFLOW.md#task-navigation); follow the owning report for exact scope.

## Current evidence and limits

Use affected checks during ordinary work; full Python/package and browser suites run sequentially at authorized checkpoints. The prior [sync](tasks/SYNC-2026-10-24.md) recorded 687 Python tests and 33 browser tests at its named candidate; later changes invalidate any assumption that this is the current full result. [Analytical-target evidence](tasks/T006.2.2.2.1-analytical-target.md) records 51 affected tests and [browser tooling evidence](tasks/BROWSER_TEST_WORKFLOW.md) its actual scope. Do not rerun these unrelated checks merely to update status. Current task results, failed attempts and unrun checks belong to its owning audit. Hosted CI after the last sync remains unverified here; check the prior relevant run on the next authorized sync.

## Prior task handoffs

[Prior task handoffs](STATUS-2026-10-24-history.md#prior-task-handoffs) and [historical verification details](STATUS-2026-10-24-history.md#current-evidence-and-limits) remain available on demand. Replace the current task summary at handoff; put substantial new evidence in its task report. Archive superseded summaries when they would obscure the next action, rather than appending a running transcript here.

## Identity and historical evidence

HEAD `1fa1bc5bc076fb00b19368efbfdce5a9c7745dc8`, branch main at intake; changes are uncommitted. No commit/push/merge or GitHub sync is authorized by this task. The [authored manifest](PLANNING_MANIFEST.sha256) identifies the combined live tree, not an accepted/released candidate. [Historical identities](STATUS-2026-10-24-history.md#identity-and-historical-evidence) retain their original scope.

## Human-readable remaining roadmap

The [remaining roadmap](REMAINING_ROADMAP.md), [component dependency plan](tasks/REMAINING_WORK_PLAN.md) and [project plan](PROJECT_PLAN.md) provide broader sequencing when needed. They are navigation, not an execution queue; this file owns the sole next candidate.
