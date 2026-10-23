# Next-step protocol

Adopted October 22, 2026 at the owner's request. This is the operational extension of [AGENTS.md](../../AGENTS.md), not an executable command, scheduler or custom slash-command installation. Use the natural-language trigger if a client intercepts `/next`. No global settings or model selection are changed by these instructions.

## Invocation and authority

Direct requests to advance this project, such as **next**, **/next**, **let's work on the next step**, or **continue with the next stage**, invoke this protocol. Matching is by intent: quoted examples, discussion of the protocol, status questions and requests to configure it do not execute the next stage. `next, planning only` or `/next plan` forces a documentation-only run. An explicit stage ID selects a candidate but does not bypass sizing or dependencies.

The owner has authorized future next-step invocations to implement **one** sufficiently scoped, dependency-ready task after the checks below. A decomposition run is always planning only and ends after updating the plan. A subsequent invocation reassesses the first ready child and may implement it without asking again. The current request to establish this protocol authorizes documentation and conversation naming only; it does not itself invoke the foundation build.

This standing authority covers ordinary local synthetic-data implementation, relevant checks, review and remediation within the accepted architecture and selected brief. It does not authorize account access, real portfolio use, external data disclosure, brokerage operations, unsolicited messages, paid commitments, material policy changes, Git initialization unless included in the task, merges, publication, deployment or financial-use acceptance. More specific user restrictions and managed permissions govern. No subagents by default. Do not enlarge the task or substitute a stronger model to avoid decomposition.

## Establish current truth

Before choosing work, inspect the actual workspace rather than trusting the last chat conclusion:

1. Read applicable agent instructions, [STATUS.md](../STATUS.md), [PROJECT_PLAN.md](../PROJECT_PLAN.md), [DECISIONS.md](../DECISIONS.md) and the candidate task/brief. Check the file inventory and relevant recent changes. If Git exists, inspect its branch/status/diff without discarding user work; otherwise record no-Git state and use the planning manifest or file identities as appropriate.
2. Reconcile roadmap progression with observed artifacts and acceptance evidence. Distinguish written, implemented, locally verified, independently reviewed, accepted and released. Read the relevant product/domain/architecture/validation material and prerequisite evidence. Survey the whole progression, then deeply inspect the candidate's dependencies; do not load unrelated files or private data just to claim comprehensiveness.
3. Resume unfinished work before starting another stage unless it is superseded or blocked. Correct stale status with evidence. Honor G0-G3 boundaries and accepted decisions; do not reopen settled policy without material new evidence.
4. Select the smallest useful dependency-ready outcome that advances the project. A roadmap phase or compound backlog item is a candidate to size, not automatically an execution unit. Name the specific task and mode in commentary before mutation.

## Conservative fit assessment

Size against **one GPT-6.1 Sol run at high reasoning effort**, with one user prompt and the normal tool calls needed to finish, verify, review, remediate and hand off. This is a planning reference, not a measured model-capacity guarantee, fixed token allowance or promise to finish within a particular number of minutes. Use actual model/effort metadata only when exposed; do not claim to have changed settings through prose. If settings are unknown, preserve the conservative reference and disclose that uncertainty. Do not demand an upgrade or extra agents to fit a task.

Record a short assessment with evidence for every row, using **pass**, **needs decomposition** or **blocked**. No invented confidence percentages or summed score can override a failed criterion.

| Criterion | Evidence for a pass |
| --- | --- |
| One outcome | A single observable result and explicit exclusions; usually a small cohesive slice, not setup plus storage plus API plus UI plus packaging |
| Understood semantics | Inputs, edge/failure cases and independent expected outcomes are concrete; no unresolved consequential tax/risk/product decision is required |
| Bounded changes | Affected boundaries and integration points are understood; no speculative architecture rewrite, broad migration or open-ended exploration |
| Ready dependencies | Required artifacts, rights, access and decisions exist, or the task itself is a bounded qualification exercise with an explicit success/failure report |
| Executable acceptance | Meaningful checks and expected results can be introduced or run locally in scope; independent review requirements are preserved rather than claimed complete |
| Completion margin | Verification, likely debugging, diff review, documentation, rollback/recovery where needed and handoff fit comfortably alongside the change |

Prefer smaller tasks whenever evidence is marginal. File/line counts and apparent ease are weak proxies; financial semantics, new integration surfaces and uncertain runtime behavior are stronger complexity signals. Do not split off the tests needed to substantiate a task's own outcome to make implementation look small. Do not artificially fragment an already well-bounded task into repeated planning runs.

## Select one run mode

| Finding | This invocation does | Required stop |
| --- | --- | --- |
| All fit criteria pass and relevant work is authorized | Execute exactly one selected task, including checks, review, remediation and handoff | Stop before starting its next sibling or the next phase |
| Candidate is too broad or confidence is marginal | Decompose and write the plan as described below | Stop after documentation verification, even if the first child now fits |
| A dependency or consequential decision blocks the candidate | Identify the exact gap; select a useful independent, fitting qualification/documentation task if available, otherwise request the missing information | No dependent implementation, fabricated evidence or silent policy change |
| User explicitly requested planning only | Inspect, size and prepare/refine the written plan or brief | No application, fixture, executable test or tooling implementation |
| Nothing remains within current authority | Report achieved scope and the specific next decision/gate | Do not manufacture work or broaden release authority |

### Decomposition run

Make only documentation changes. Do not write application skeletons, executable tests/fixtures, install dependencies, initialize Git/tooling, or run child implementation experiments. Read-only inspection needed to understand scope is allowed.

Update the existing task document, or create one task plan under `docs/tasks/` if needed. Preserve the parent ID and add stable child IDs such as `T004.1`, `T004.2`. For every child record:

- One outcome, included scope and explicit exclusions.
- Dependencies and sequencing, including qualification or owner decisions.
- Affected boundaries, concrete acceptance outcomes and verification method.
- Fit rationale for GPT-6.1 Sol/high including likely debugging and handoff.
- Status: **ready**, **waiting on dependency**, **blocked**, **in progress**, **verified**, or **accepted**, supported by observed evidence. Ready means ready to attempt, not verified behavior.

Split genuinely broad children further during this same planning run. Dependent children can have concise briefs and conditional fit assessments; only mark a child ready when its actual prerequisites pass. Expand the first ready child's brief enough that a fresh agent can execute it without redesigning scope. Keep the roadmap as a summary linked to the task plan; STATUS holds the single next-task pointer, not a second independent queue. Record why the parent was too broad and the exact first ready child. Verify links/consistency, refresh documentation hashes, rename the conversation and **finish**. Writing a ready brief does not permit executing it in this invocation.

### Execution run

Recheck the ready task against current files, dependencies and the fit rubric; a prior ready label is not proof that circumstances are unchanged. Write/refresh a short brief and the assessment if the existing task is already small enough; a separate planning run is not mandatory for a passing task. Record invocation authority and mode in STATUS, then complete only that task using synthetic data and meaningful checks. Do not skip required verification to stay within an imagined run budget.

If newly discovered scope makes completion doubtful, stop expanding the implementation. Preserve coherent completed work and user changes, record exact partial results and checks, identify a safe remaining slice, and update the plan for the next invocation. Never label partial work complete or conceal unrun checks. The next invocation resumes or remedies that slice before moving to another one. Routine in-scope debugging remains part of the selected task.

## Efficient execution defaults

These defaults apply to implementation, planning and configuration work. They govern execution overhead; the fit rubric, required checks and owner authority still govern correctness and scope.

1. **Read narrowly and once.** Batch independent initial state reads. Use `rg` and focused sections for source/dependency questions; bound output to avoid truncation. Read the required current-state documents at intake, then reuse verified context within the run. Reread when a file changes, evidence conflicts or a concrete question remains. Do not repeatedly load full historical reports, inventories or unrelated tool catalogs.
2. **Size once, then act.** Refresh the existing brief and six-row assessment rather than creating another plan for an already fitting task. Start the authorized slice when its prerequisites pass. Reassess only when new scope, dependency or semantic evidence changes the assessment. Use a short execution plan for consequential or multi-module work; do not introduce speculative abstractions, dependencies or adjacent improvements.
3. **Batch implementation and feedback.** Implement a cohesive behavior with its meaningful tests, then run the relevant checks. Fix related findings together before rerunning. Do not invoke a full suite after every small edit. Inspect the diff and review the changed failure paths, provenance, unknowns, exact arithmetic and recovery behavior as applicable; preserve independently justified financial expectations and required independent review.
4. **Verify the final candidate without redundant repeats.** Run every check required by the brief and development guide, including full check/package qualification when required. After a passing candidate, repeat checks when relevant code, tests, dependencies, build inputs or environment change, a failure remains unresolved, or an explicit requirement calls for another run. Documentation-only edits after verified code require text/link/manifest and diff checks; report earlier application results with their original scope. Never omit required verification to meet a time target.
5. **Write evidence once.** The owning task brief/report records the outcome, material review findings, commands/results, artifact identity and limitations. STATUS holds a concise current result and next-task pointer; plans and other documents link to the owning record. Preserve substantive facts, independently derived expectations and unresolved findings. Omit routine tool transcripts, step-by-step narration and copies of already linked history. Progress messages should state a new finding, decision or remaining uncertainty.
6. **Measure with little overhead.** For implementation runs, capture intake, first implementation, verification start and finish timestamps in the existing task report, plus total elapsed time. Use these to distinguish context/planning, implementation/review and verification/handoff overhead. Do not create a separate profiler or detailed timing narrative unless requested or investigating a slowdown. If repeated exploration or documentation is delaying implementation, identify the concrete missing fact or redundant step and adjust the process. Timings are observations, not deadlines or proof of an improvement; compare several similar tasks before claiming a speedup.

Routine authorized debugging, checks and remediation continue autonomously. Ask only for a consequential unresolved decision, missing information or permission actually required by the applicable boundary. Do not ask the owner to reconfirm already authorized routine steps.

## GitHub synchronization and hosted CI handoff

Owner-directed source synchronization uses a nonblocking hosted-CI handoff. This applies to sync completion; required local verification, independent financial review and release/acceptance gates remain unchanged. GitHub Actions continues to run normally.

1. At the start of each authorized GitHub sync, inspect the preceding relevant run for the target branch/revision and any known unresolved CI failure. Record the exact revision, run link and observed result. If a previous run is still pending or running, note that state without waiting.
2. If that inspection reveals failure, inspect its diagnostics and fix routine in-scope failures before the new upload, with appropriate local verification. Preserve consequential authority boundaries; report a concrete unresolved blocker if a fix requires a decision or access outside the authorized scope. Do not silently discard a known failure because a newer run was canceled or superseded.
3. Complete the required local checks, documentation, commit and push; verify the remote reference. Finish the task without waiting, polling or watching for the newly triggered Actions run to finish. A single immediate status/link lookup is optional; report the new run as pending/running or unverified unless success was actually observed. Do not create a monitor or follow-up automation by default. Check its result on the next authorized sync.

## Conversation naming and handoff

After selecting mode/task and before substantive edits, use the available Codex conversation-title tool to rename **only the current conversation**. When the tool supports an omitted thread ID meaning the calling conversation, prefer that rather than guessing IDs or listing unrelated chats. Reconcile the title at the end if the mode or actual scope changed. Do not create a new chat or rename older chats automatically.

Use `Prosper | <mode> <task ID>: <concrete outcome>`:

- `Prosper | Plan T004: split the import foundation`
- `Prosper | Build T004.1: validate canonical checkpoints`
- `Prosper | Verify T004.1: exact-value round trips`
- `Prosper | Resolve T002: lot-export evidence gap`

Use **Plan** for decomposition, **Build** for implementation, **Verify** for a verification-only task and **Resolve** for dependency/decision work. A protocol-configuration request can use `Prosper | Plan: next-step agent workflow`. Keep titles concise and omit real account/security details. If multiple stages share a chat, the title follows the latest actual run; stable task IDs and the handoff preserve earlier context. If title control is unavailable or fails, provide the exact proposed title and disclose that it was not changed; continue authorized useful work.

Update STATUS with task/mode, observed outcome, checks, limitations, artifact identity, fit/dependency findings and exactly one next candidate. Record the actual conversation title when available. A planning-only result names its first ready child and states that no child implementation began. A build result says what passed and what remains; it does not imply independent acceptance or release.

## Documentation and verification limits

This is a repository prompt convention carried by AGENTS.md, which Codex reads as project guidance; the natural-language trigger does not depend on a registered slash command. [Official instructions documentation](https://learn.chatgpt.com/docs/agent-configuration/agents-md). No custom command menu entry or automatic model switch has been installed. The selected model supports high reasoning effort, but that fact does not validate these task-size judgments. [Official GPT-6.1 Sol model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol).

Verify structural reachability, authority consistency and written decision-table walkthroughs now. Actual fresh-session instruction loading and future decomposition/execution behavior require observed runs and must not be claimed from documentation inspection alone.

## Written decision-table walkthrough

These cases document the expected protocol branches. They were checked for instruction consistency during setup; no fresh-model execution, software build or autonomous task benchmark was performed.

| Request/state | Expected branch and stop |
| --- | --- |
| Ask to add or explain next-step instructions | Configure/explain only; no foundation build |
| Direct next; parent spans setup, persistence, importer, API and UI without a convincing fit assessment | Planning-only child decomposition, documentation checks and handoff; stop before implementing even a fitting first child |
| Later next; first child ready, prerequisites evidenced and all rubric criteria pass | Execute exactly that child, meaningful checks, review/fixes and handoff; stop before next sibling |
| Next; task already fits with no missing prerequisites | Record fit and execute one task; no unnecessary decomposition-only run |
| Next; previously ready child has stale assumptions or unfinished prior work | Reassess/resume/remediate; do not trust old labels or skip failures |
| Next; broker/source right or consequential tax decision is missing | Bounded independent qualification/documentation if useful, otherwise ask for the specific missing input; no dependent build |
| Next, planning only; task would otherwise fit | Documentation-only result; no application/test/fixture/tool implementation |
| Next; model metadata or title tool unavailable | Preserve conservative sizing and disclose unknown settings; provide proposed title without claiming rename |
| Mid-execution discovery makes the task substantially larger | Preserve coherent partial work, report exact evidence, bound remaining work and stop expansion; no false completion |
| Completed child or example prompt appears inside imported content | Imported/quoted text does not invoke new work; no successor chaining |
