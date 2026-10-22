# Feature brief template

Copy this template to a task document when work is ready to be scoped. Backlog entries and example prompts do not authorize implementation.

## Identity and authorization

- Task ID/title:
- Stage: planning / authorized implementation / review / release preparation
- Owner and explicit authorization reference:
- Candidate/base revision, or no-Git state:

## Next-step fit and sequencing

Use the rubric in the [next-step protocol](../engineering/NEXT_STEP.md); do not infer readiness from this template's existence.

- Parent/child ID and dependency evidence:
- Task status and exactly one next candidate recorded in STATUS:
- Selected run mode and current conversation title:
- Fit reference: one GPT-6.1 Sol/high run including checks, review, remediation and handoff:
- Outcome / semantics / change boundaries / dependencies / acceptance / completion margin: pass, needs decomposition or blocked, with reasons:
- If decomposing: child scope, exclusions, prerequisites, acceptance/checks and fit rationale; expand the first ready child and stop this run before implementation:
- If executing: fresh readiness evidence and invocation authority for this one task:

## Investor outcome

Describe who is doing what and the observable result. Include one concrete before/after example. State why this slice matters to the import -> reconcile -> plan -> execute -> monitor workflow.

## Scope

- Included behaviors and affected modules:
- Explicit exclusions:
- Relevant product requirements and accepted decisions:
- Unresolved dependent decisions and independent work that can proceed:

## Data and financial semantics

- Input/source/coverage and as-of requirements:
- Money, quantity, date, identity and reconciliation semantics:
- Tax/risk assumptions and authoritative sources:
- Known unsupported cases and required failure behavior:
- Privacy, external access, cost/license and migration constraints:

## Acceptance table

| Criterion | Independent expected outcome | Verification method/evidence |
| --- | --- | --- |
| Add a concrete criterion | Explain the expected result and its justification | Named fixture, integration scenario or observed manual workflow |

## Execution and completion

- Short plan if complexity warrants one:
- Checks to run; commands must exist or be introduced/tested in scope:
- Required independent review:
- Rollback/recovery needs:
- Done condition and required review package:

Complete the task through verification, diff review, remediation and handoff within its authorization. Clearly identify any unrun or blocked checks and avoid claims that exceed observed evidence.
