# Working with coding agents

The owner is responsible for product outcomes and consequential decisions. Once implementation is explicitly authorized, agents should complete routine engineering, verification and remediation within the agreed scope. The protocol-configuration task is documentation only. Future direct next-step requests use the standing scoped authority in the [next-step protocol](NEXT_STEP.md). [AGENTS.md](../../AGENTS.md) defines the active authority boundary.

## Context hierarchy and task intake

Use [STATUS.md](../STATUS.md) as the handoff, [DECISIONS.md](../DECISIONS.md) for accepted versus unresolved choices, and the task brief for the current outcome. Read domain/architecture documents relevant to that task. Do not paste the full project plan into every prompt or duplicate rules in multiple agent files.

The owner adopted the baseline architecture and staged learning plan on October 22, 2026; [ADR-0001](../architecture/decisions/0001-adopt-project-architecture.md) records the decision. Use the accepted choices without repeating approval requests. Qualification of versions, data and behavior remains engineering work; accepting a plan does not claim those checks passed or authorize implementation.

The [pre-implementation review](../reviews/2026-10-22-pre-implementation-review.md) records the original findings and engineering clarifications; [ADR-0002](../architecture/decisions/0002-adopt-critical-review-actions.md) adopts D031-D035. Use one source of truth per topic: DECISIONS for acceptance status, PROJECT_PLAN for scope/dependencies, product/domain contracts for behavior, VALIDATION for expected evidence, and STATUS for observed work. The owner explicitly adopted the review recommendations. Preserve the strict risk/zero-gain policy and the recorded supported tax scope; do not infer acceptance of later strategy changes. Preserve historical ADRs and record new decisions explicitly.

Codex supports repository `AGENTS.md` instructions and layered scope. This project uses one concise root file and a `CLAUDE.md` import for shared guidance. No machine-wide configuration has been changed, and fresh-session instruction loading has not been tested. [Official OpenAI instructions documentation](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

The additional status, plan and template filenames are project conventions. OpenAI's workflow guidance also distinguishes optional organizational conventions from the recognized agent-instructions file. [Official workflow example](https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex).

## Advance with one prompt

Use **let's work on the next step**, **next**, or **/next** as a direct request. The [next-step protocol](NEXT_STEP.md), referenced by AGENTS.md, defines the mandatory current-state inspection, quick GPT-6.1 Sol/high fit decision with a reusable execution sketch, planning-only decomposition branch, single-task execution branch, persistent handoff and conversation naming. Use **next, planning only** to forbid implementation on that run. The natural-language prompt works as an instruction convention; no command-menu integration or automatic model switch is installed.

A decomposition run must stop after writing and verifying bounded substages. The next invocation rechecks readiness and can implement one fitting child without repeated approval. A fitting existing task can proceed directly. Do not run an entire roadmap phase simply because it is the next row. This workflow does not authorize release, private data or brokerage access.

## Normal task loop

Apply the authoritative [efficient execution defaults](NEXT_STEP.md#efficient-execution-defaults): focused intake, cohesive implementation/check batches, material evidence in one owning record and lightweight timing. Use the existing brief when it already fits; the loop does not require another planning document or repeated approval.

1. Reuse or briefly fill the task brief with outcome, scope, authoritative requirements, constraints, independently justified examples and done conditions. For a next-step task, its short sizing sketch is already the execution plan.
2. Resolve consequential unknowns before their dependent work. Continue independent useful work while a decision is pending.
3. For consequential or multi-module work, use the same short execution sketch made for sizing; add detail only when a concrete implementation need arises. Do not create a second coding plan. Small local fixes do not need a new planning document.
4. Once authorized, implement the complete bounded slice, run appropriate checks, inspect the diff, and remediate introduced problems.
5. Review financial logic against independent expected cases. Independent human/specialist review is a separate requirement; automated self-review does not substitute for it.
6. Deliver a review package with exact artifact/revision identity, actual check results and limitations. The owner accepts behavior and approves consequential integration/release steps as applicable.
7. Update status and material decisions so a new session can continue without reconstructing chat history.

Do not leave a task partially done merely to ask whether to run the next routine test. Do not silently extend it into live brokerage activity, external publication or a different financial strategy.

## Responsibility table

| Activity | Agent authority after a relevant implementation task is authorized | Owner/reviewer responsibility |
| --- | --- | --- |
| Read source, inspect state, reproduce bugs | Autonomous within scope and managed permissions | Set outcome and data access boundaries |
| Edit scoped code/docs/tests, run local checks and remediate | Autonomous | Review acceptance evidence |
| Interpret uncertain tax law or change risk objective | Prepare evidence and alternatives; do not decide silently | Accept policy with qualified review where needed |
| Add ordinary development dependency | Within accepted stack and task scope, subject to license/security review | Decide material license/cost/distribution commitments |
| Use real portfolios or send data externally | Only with explicit authorization for data and destination | Control sensitive data access |
| Merge/integrate, shared test deployment, production/public release | Prepare exact candidate and review package | Authorize named consequential transition unless already authorized |
| Brokerage read/write or trades | Separate explicit authorization and qualified feature | Retain execution control; initial product has no trade API |

Do not add repeated approvals when the owner has already authorized the action. Tool sandbox restrictions still apply. If an approval is needed, explain the concrete unresolved action and evidence, rather than asking for vague permission to continue.

## Session hygiene

- One primary task with a clear outcome per session where practical. Do not change architecture while repairing an unrelated importer bug.
- No subagents by default. Delegate only when explicitly authorized; define ownership and avoid concurrent edits to the same files. Independent review must still be characterized honestly.
- If Git/worktrees are later introduced, branch/worktree names should identify a task. Runtime files, databases, ports and credentials need explicit isolation beyond worktree files.
- Run financial checks with synthetic data. Do not introduce portfolio-bearing screenshots, fixtures or logs to simplify debugging.
- Record substantive conclusions and commands, not a full transcript or repeated status narrative.
- An agent should never change an unapproved proposal to an accepted decision just to unblock itself.

## Ready-to-use prompts

### Advance one bounded step

> Let's work on the next step. Follow the next-step protocol in AGENTS.md: inspect current truth, make a quick rough fit decision for GPT-6.1 Sol at high effort, and rename this conversation for the actual stage. Reuse the short sizing sketch as the coding plan and begin; no six-row report or second planning phase. If the next task needs decomposition, update the substages and handoff, verify the documentation, then stop without implementation. Otherwise complete exactly one fitting authorized task with checks, review, remediation and handoff.

### Plan the next step only

> Next, planning only. Inspect progression and dependencies, assess fit, and prepare or refine the smallest useful task briefs. Rename this conversation for the planning stage. Do not implement application code, tests, fixtures or tooling.

### Continue planning now

> Read AGENTS.md, docs/STATUS.md, docs/DECISIONS.md and docs/engineering/FOUNDATION_SPEC.md. T001 written planning deliverables are complete and D031-D035 are adopted. Continue only the requested documentation or public/synthetic G1 qualification work. Preserve unobserved evidence as unverified. Do not implement code, install tools, access accounts or place trades without a later implementation instruction.

### Authorize a later implementation slice

> Implementation is authorized for the attached feature brief only. Read the project instructions, current status and relevant source documents. Resolve any required dependent decisions, then implement the complete slice, meaningful tests and local checks, review the diff and remediate introduced issues. Use synthetic data. Do not access brokerage accounts, publish, merge or deploy unless separately authorized. Report exact candidate identity, acceptance evidence, limitations and update the handoff.

This example is a template for a future owner instruction; its presence in the repository does not authorize implementation.

### Review a candidate

> Review the identified candidate against its feature brief and independent reference cases. Focus on incorrect financial assumptions, missing data/time semantics, unsafe feasibility claims, provenance, and recovery. Verify the checks you can actually run and distinguish them from claimed results. Report actionable findings and residual limits. Do not broaden scope or release the candidate.

### Resume after an interruption

> Read AGENTS.md and docs/STATUS.md. Verify the workspace/revision and current files before trusting the handoff. State the last verified outcome, remaining acceptance criteria and current authorization boundary, then complete the next already-authorized work. Ask only for material information or decisions not available from project sources.
