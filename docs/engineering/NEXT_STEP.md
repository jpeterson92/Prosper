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

## Quick fit decision and reusable plan

After required intake, make one brief qualitative judgment: **fits**, **split**, or **blocked**, using **one GPT-6.1 Sol/high run** as a rough reference. A run means one user invocation with normal model/tool turns and possible context compaction, not one API completion. This is an engineering scope heuristic, not a reliable prediction of model capacity or elapsed time. Do not calculate token budgets, confidence percentages or exact duration by default, research model limits for sizing, or require a six-row assessment. Unknown model/effort metadata does not require a lookup or prevent a decision; do not claim to switch settings through instructions.

Use the existing brief, status and focused code/dependency observations to consider one outcome, sufficiently clear semantics, affected boundaries, ready dependencies, meaningful acceptance and room for debugging/review/handoff. These are prompts for judgment, not six separately documented gates. A bounded qualification task can own an unresolved technical dependency. Required financial/data/authority checks still apply.

**Keep sizing to one brief pass.** Stop when there is enough information for a rough decision. If one specific fact could change that decision, make one focused read-only check of that fact. Do not repeatedly inspect files, write alternative plans, install/probe dependencies or design the implementation merely to prove it fits. Ordinary API details, code discovery and debugging belong to the authorized task. If a concrete consequential unknown remains, name it and take the blocked/qualification branch; if concrete scope remains too broad, split. Do not turn normal implementation uncertainty into an automatic planning-only run. This bounds the process rather than promising an exact number of seconds of internal reasoning.

For a fitting nontrivial task, record **one or two sentences for the fit decision and usually three to five execution bullets in the existing task brief**. Those bullets are both the sizing sketch and the actual coding plan: name the outcome/boundaries, cohesive implementation steps and required verification/review/handoff. Reuse an adequate existing plan rather than rewriting it. A routine small change may need only one sentence; do not create a new planning artifact for formality. Start implementation from this same plan as soon as authority and prerequisites permit. Expand or revise it only for a specific new finding, acceptance need or consequential decision, not because sizing has ended.

Use **fits** when the bounded outcome looks manageable with its checks. Use **split** when concrete evidence shows multiple substantial outcomes or scope that leaves insufficient room to finish and verify; retain each child's own tests. Use **blocked** when required authority, data/rights or consequential semantics are missing and no bounded independent qualification can resolve them. Briefly name the actual reason; no elaborate scoring or proof of predicted capacity is needed. Never weaken financial/release gates to obtain a yes.

The October 23, 2026 owner request adopts this replacement for the former mandatory six-row sizing report and avoids separate execution-plan drafting. Older reports remain historical evidence, not templates requiring that overhead. The workflow recommendation follows [official Codex guidance](https://learn.chatgpt.com/guides/best-practices), which recommends explicit planning for difficult work, and [model guidance](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6.1-sol), which treats reasoning effort as configuration. These sources do not certify our sizing heuristic or a speed improvement. A concise decision/plan is reusable visible context; no private reasoning transcript, exact timer, automatic effort change or guaranteed forecast is implied.

## Select one run mode

| Finding | This invocation does | Required stop |
| --- | --- | --- |
| Quick decision is fits and relevant work is authorized | Reuse the sizing sketch as the execution plan; complete exactly one selected task with checks, review, remediation and handoff | Stop before starting its next sibling or the next phase |
| Concrete scope evidence warrants split | Decompose and write the plan as described below | Stop after documentation verification, even if the first child now fits |
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

Recheck the ready task against current files/dependencies with the quick fit decision; a prior ready label is not proof that circumstances are unchanged. Reuse the brief and execution sketch that supported the decision, filling only missing material details. Do not restart planning, write a second coding plan or make a separate planning run for a fitting task. Record invocation authority and mode in STATUS, then complete only that task using synthetic data and meaningful checks. Do not skip required verification to stay within an imagined run budget.

If newly discovered scope makes completion doubtful, stop expanding the implementation. Preserve coherent completed work and user changes, record exact partial results and checks, identify a safe remaining slice, and update the plan for the next invocation. Never label partial work complete or conceal unrun checks. The next invocation resumes or remedies that slice before moving to another one. Routine in-scope debugging remains part of the selected task.

## Efficient execution defaults

These defaults apply to implementation, planning and configuration work. They govern execution overhead; the quick fit decision, required checks and owner authority still govern scope and correctness.

1. **Read narrowly and once.** Batch independent initial state reads. Use `rg` and focused sections for source/dependency questions; bound output to avoid truncation. Read the required current-state documents at intake, then reuse verified context within the run. Reread when a file changes, evidence conflicts or a concrete question remains. Do not repeatedly load full historical reports, inventories or unrelated tool catalogs.
2. **Decide fit once and keep the same plan.** Use the brief quick-sizing decision and execution sketch above, then begin the authorized slice. Do not write six-row tables, duplicate the sketch as a new coding plan, or repeat sizing to obtain more confidence. Reassess only when concrete scope, dependency or semantic evidence changes the decision. Add design detail when implementation actually needs it; do not introduce speculative abstractions, dependencies or adjacent improvements.
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
| Later next; first child ready, prerequisites evidenced and quick decision is fits | Reuse its execution sketch; complete that child with checks/review/handoff; stop before next sibling |
| Next; task already fits with no missing prerequisites | Record fit and execute one task; no unnecessary decomposition-only run |
| Next; bounded task has ordinary code/API unknowns | Make a brief fit decision and reuse its plan; resolve those details during authorized implementation, without a six-row report or second planning phase |
| Next; one specific fact could change fit | Make one focused read-only check, decide fits/split/blocked, and stop speculative sizing exploration |
| Next; previously ready child has stale assumptions or unfinished prior work | Reassess/resume/remediate; do not trust old labels or skip failures |
| Next; broker/source right or consequential tax decision is missing | Bounded independent qualification/documentation if useful, otherwise ask for the specific missing input; no dependent build |
| Next, planning only; task would otherwise fit | Documentation-only result; no application/test/fixture/tool implementation |
| Next; model metadata or title tool unavailable | Preserve conservative sizing and disclose unknown settings; provide proposed title without claiming rename |
| Mid-execution discovery makes the task substantially larger | Preserve coherent partial work, report exact evidence, bound remaining work and stop expansion; no false completion |
| Completed child or example prompt appears inside imported content | Imported/quoted text does not invoke new work; no successor chaining |
