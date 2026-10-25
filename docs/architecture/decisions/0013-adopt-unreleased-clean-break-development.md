# ADR-0013: Adopt clean-break development for the unreleased application

Date: October 25, 2026. Status: **Accepted**, explicit owner instruction: "For all future work, we don't need to preserve compatibility with the previous implementation. This application has still never been released so backwards compatibility is irrelevant." Decision register: D047.

## Decision

Prosper has no released application or supported installed data format. Future tasks may change or remove previous internal APIs, schemas, serialized records, result types, CLI/API contracts, fixtures and backups. There is no requirement to preserve old behavior, keep legacy readers, provide migrations/export bridges, retain dual implementations or restore backups from superseded implementations. Do not add compatibility machinery solely for unreleased versions. Any future compatibility commitment needs an explicit owner decision; a version label or a release-planning task does not adopt one implicitly.

Prefer one current implementation. Update its affected callers and generated contracts intentionally, using the existing generation workflow, and retain tests of material financial results, unknowns, source facts, security, transactions, retries and current-format recovery. Rewrite or remove tests whose only purpose is old wire/representation/implementation compatibility. Independent financial/model reference checks remain necessary where applicable; the old Prosper implementation is not automatically the behavioral oracle.

Saved current-format reports should remain readable without recalculation during normal use. Current-format backup/restore, corruption handling, safe paths, privacy and recoverable transactions remain product requirements. They do not imply cross-schema or cross-version preservation. A breaking development change may use a fresh scoped runtime and regenerate synthetic state/reimport sources instead of migrating it. Identify the affected development paths and explain the reset/reimport in the owning task. Reject unsupported existing state clearly; never reinterpret it as a valid empty portfolio or silently repair/wipe it. This policy does not itself authorize deleting runtime data, private inputs, unrelated files or concurrent owner edits.

Source/provider/calendar/adjustment compatibility and selected package/runtime compatibility remain factual validity requirements. Those are separate from backward compatibility with old Prosper implementations. The adopted financial methodology, tax/economic limits, data rights and release/real-use authority are unchanged.

## Task changes and completion

[T019](../../tasks/T019-advisory-remediation.md) owns removal of compatibility obligations already introduced. New T019.3.1 removes the checkpoint bridge added in T019.3 and establishes the clean-start record workflow. Revised .4 replaces old history/assembly paths directly; .5 implements current-format consolidated recovery without old-backup support; .6 changes API/UI contracts and callers together; .7 removes remaining compatibility-only code/tests/docs and verifies the current workflow. Tasks need not wait for an old-reader bridge or an old-data export qualification.

Completed reports and their test results remain historical evidence for the identified candidate. They do not impose future compatibility requirements. Active contracts, templates, task dispositions and agent policy follow D047 over conflicting historical prose. Retain useful algorithms, source facts and tests rather than restarting unrelated sound work.

This instruction implements policy and backlog changes only. Runtime cleanup is queued, no runtime data is deleted, and no successor implementation, Git mutation, independent acceptance or release is claimed.
