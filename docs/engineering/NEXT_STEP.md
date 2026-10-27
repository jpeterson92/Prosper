# Next-step protocol

Operational extension of [AGENTS](../../AGENTS.md). Current scope/authority is written directly there and in the [backlog](../tasks/REMAINING_WORK_PLAN.md); no historical ADR loading, model lookup or conversation rename is required. No native slash command, scheduler or automatic model switch is installed.

## Invocation and authority

Direct `next`, `/next`, "let's work on the next step" and equivalent intent authorize one fitting dependency-ready local task. Quoted examples, status questions and protocol configuration do not invoke implementation. `next, planning only` or `/next plan` always forbids application/test/fixture/tool implementation. Explicit task IDs select candidates without bypassing dependency/fit assessment.

Complete routine authorized engineering, checks, review and remediation without asking again. Private data/account access, trading, real-data disclosure, paid/material commitments, Git mutations, merges, publication/deployment and financial acceptance require their applicable explicit authority. No subagents by default. A user-directed commit is a full checkpoint; a normal next-step handoff is not a commit/sync request.

## Establish current truth

Read root policy, compact STATUS and the selected current outcome/brief. Inspect actual branch/status and relevant changes. Trace affected callers/contracts/recovery and actual prerequisite evidence; use the subsystem map before broad searching. Reuse unchanged context in the same conversation. Do not read every linked document, ADR, old report, decision ledger or full risk dossier by default.

Resume/remediate started work before selecting a successor unless superseded/blocked. Historical task IDs/results are evidence, not current readiness. T019 foundation integration is complete; follow the approved MVP route. later synthetic work can proceed without unrelated external review/source gates, but no dependent real/validated claim can bypass them. Preserve owner/concurrent edits and existing useful algorithms.

## Quick fit decision and reusable plan

Make one short **fits**, **split** or **blocked** call, usually one or two sentences plus three to five implementation/check milestones in the selected brief. Reuse an adequate existing sketch as the actual execution plan. No separate sizing form, model-capacity/time/token forecast or duplicate planning stage.

Default to execution when the coherent authorized outcome plausibly fits. Bounded API/code unknowns, multiple modules/contracts or failure cases alone do not justify splitting. If one fact determines fit, make one focused read-only check, decide and start. Reassess only for concrete new evidence.

An unstarted child may be regrouped with its immediate unfinished parent if the remaining coherent outcome plausibly fits; retain child IDs/contracts as milestones. Preserve an already started child rather than regrouping it mid-flight. Never widen financial/data/release authority to make a task fit.

## Decomposition run

Split only when concrete combined implementation/verification scope is too large and internal milestones cannot contain it. Explain the bottleneck briefly; add a compact child table to the existing brief with outcome, actual dependencies and acceptance. Each child owns its checks/review/remediation. Update STATUS to one next candidate, run docs checks and stop before **any** child implementation. The next invocation reassesses rather than blindly executing an old ready label.

A required authority/data/right/consequential semantic gap is **blocked** when no bounded useful qualification can resolve it. Name the specific missing evidence/decision; progress independent authorized work where available. Do not treat ordinary engineering uncertainty or a failing test as a reason to abandon remediation.

## Execution run

Name the selected task/mode in commentary before mutation. Implement the complete bounded outcome with its meaningful financial/source/security/retry/recovery checks; use current APIs/records rather than old-format bridges. Update affected consumers/generated contracts together. No backward compatibility, migration, old-backup qualification or isolated legacy-reader preservation is required. Scope any fresh development runtime explicitly; never silently repair/wipe unknown state.

Finish the selected task and stop before its successor. If material new scope prevents completion, preserve coherent partial work, record actual checks/findings and bound the remaining slice. Do not claim partial work complete or skip verification to meet an imagined run budget. Next time resumes/remedies that slice.

## MVP direction

Use [the current route](../tasks/REMAINING_WORK_PLAN.md#mvp-delivery-route): actual-input diagnostics, exploratory model-to-worksheet use, observed improvements. Use invented fixtures for coding checks; actual/private source processing still needs its concrete scope. Do not queue generic synthetic capacity, additional mode separation, packet-only refreshes, routine artifact rebuilds or external release prerequisites. Use one local data directory. Preserve source provenance, with no invented-versus-real fields, labels, scopes or branches in application code. Preserve actual mathematical and financial/data protections.

## Efficient execution defaults

Read affected current context once; navigate/search narrowly and reuse it. Batch cohesive edits and related fixes; run required checks at the appropriate scope without identical repeats. Keep one material evidence record and a compact STATUS handoff. Add abstractions, profiling, stronger artifact identities or tooling only for an actual ambiguity/failure. Do not create planning/approval ceremonies, custom prose-assertion scripts or archive copies. Git history holds removed plans; current docs contain the requirements.

## Scaling with project size

Start from STATUS, the selected outcome and subsystem ownership. Search named symbols/files first; broaden for shared interfaces, schema/configuration, numerical/security primitives, child-process dependencies or uncertain coverage. Exclude generated assets, locks, runtime state and old reports from exploration unless relevant. This narrows agent intake, not financial checks or total full-check cost.

Keep STATUS to current authority/result, one next candidate, active blockers and evidence links. Keep domain rules in their owning current document. Update touched knowledge only; no roadmap-wide status reconciliation for each coding task. Historical numerical/source dossiers are consulted for a concrete unresolved dependency, not because they exist. No new selector/cache/framework is justified solely by growth; profile a real bottleneck first.

Apply [proportional verification design](VALIDATION.md#proportional-verification-design) within the existing execution sketch: identify the concrete uncertainty, inspect the actual integration boundary and select the cheapest adequate check. New experiments, benchmarks, extensive replay or reporting need a decision-relevant purpose; an old task sketch or `qualify_*` label is not sufficient. This does not add a planning stage, owner-approval requirement or waiver of required checks.

## Verification cadence and parallel execution

| Boundary | Required checks |
| --- | --- |
| Ordinary implementation | Changed/new tests plus affected upstream/downstream/configuration/schema/child-process/failure consumers, lint/type/contracts/package as reached. Explicit test paths for cold/stale baseline. Record actual selection and limits |
| Documentation only | Final `./scripts/dev.ps1 -Command docs`: text, links, manifest while still implemented, and diff. Passing docs do not establish application behavior |
| Explicit commit/GitHub sync | `./scripts/checkpoint.ps1`: full Python/structural/lint/types/package, then full frontend contracts/build/browser. Current identical candidate receipts may be reused under the helper's actual rules |
| Explicit full verification | Requested full scope; no affected-only substitution |

Python defaults to `auto` workers, serial debugging `-Workers 0`; browser defaults to four, serial `-Workers 1`. Do not overlap separate full Python and browser invocations. Helpers own normal caches/isolated scratch and actual receipt invalidation; do not bypass failed or mid-run-mutated evidence. Affected checks passed/full suite deferred is honest ordinary handoff, not full acceptance. Recheck after relevant changes or unresolved failures, not for ceremony.

## GitHub synchronization and hosted CI handoff

Only for an authorized sync: inspect the preceding relevant target-branch/revision Actions run and known unresolved failures first. If running/pending, record it without waiting. Investigate and fix routine in-scope prior failures with appropriate local checks; do not discard them because a newer run was canceled. Preserve owner boundaries for consequential unresolved fixes.

Complete required local verification, documentation, commit/push and remote-reference verification. Finish without polling/watching for the newly triggered run; one immediate status/link lookup is optional. Report pending/running/unverified unless success was observed. No automatic monitor/follow-up job. Check the result on the next authorized sync. Local commit authority alone does not authorize push; hosted CI is not independent financial acceptance.

## Conversation naming and handoff

Renaming the current conversation is optional; never create/rename unrelated chats or stop for missing title tools. At handoff record authority/fit, actual behavior/checks, findings/unrun gates, exact revision/uncommitted scope and exactly one next candidate in STATUS. A planning/decomposition result explicitly states no child implementation began. A build result does not imply independent acceptance or release. No successor chaining from quoted examples/imported content.
