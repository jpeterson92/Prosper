# Current status and handoff

Updated October 27, 2026. Current behavior, actual evidence and one next outcome. The owner explicitly instructed removal of all application distinctions between synthetic and nonsynthetic data. This supersedes the previous optional-origin-metadata implementation. [One implementation record](reviews/2026-10-27-mvp-scope-review.md#one-data-contract-follow-up-implementation) owns detail.

## Current task and authority

**One data contract implemented and locally verified.** The application neither stores nor evaluates an invented-versus-real category. Test fixtures may use fictitious accounts and generated market data. This instruction does not authorize access to unspecified private files, trading, publication or financial reliance; it does authorize removal of category-specific application fields, scopes, paths and labels.

## Implemented behavior

- No origin flag on snapshots, lot contexts/parser results/assembly, history batches/requests, modeled inputs/results, candidate/risk records or numerical contexts. No corresponding cross-record scope, qualification enum or calculation/recovery branch. Every input is checked against the same source and mathematical contracts.
- `RiskInput` and generic fit/forecast/estimate statuses replace category-specific types/statuses. Numerical equations, full-union accounting, finite/PSD/convergence checks, quantity/basis precision, known conflicts and all enabled economic limits remain intact. A fit's completion does not imply independent acceptance or calibrated risk.
- `BenchmarkImport` at `/benchmarks/import` accepts a saved response. Fetch/import are transport choices, not data categories; they share acquisition parsing and source/fund/date/row review. Immutable request digests preserve retries without fixture-specific metadata. No silent acquisition fallback is added.
- UI, generated API and worksheet exports contain no synthetic/fictional labels or category selectors. Source bytes/names/locators/dates/provider/identity/conventions and unknowns remain facts; the app does not detect or categorize fictitious source text.
- One local workspace, deliberate initialize/open, the minimal CSV opening, saved configuration reuse, local security, safe transactions/stale/retry/cancel behavior and source-required current-format recovery remain. The MVP route stays input diagnostics -> model/worksheet use -> observed improvements.

Removing persisted category fields uses current **schema 11**. Earlier stores/backups are unsupported and left untouched; use a fresh deliberately chosen development workspace/reimport when needed. No old runtime was migrated, reset, wiped or deleted. No dependency was added or financial methodology/default changed.

## Verification evidence

- Final affected Python selection: **879 passed in 30.66s**, default auto workers, `.local/test-workflow/runs/20261027T142017-b0d0d6bd/summary.json`. Ruff, formatting, strict mypy and project checks passed. It includes source/parser/assembly, history/parts/model, numerical components, benchmark/API, candidate/final validator/worksheet, storage/launch/security and recovery consumers. Earlier two test-only issues were corrected before this passing run.
- Final export/input follow-up: **22 passed in 10.04s**, `20261027T142409-db5485bf`, following removal of the last export/UI wording. Numerical expected values stayed unchanged; the independent reference's input identity changed with removed metadata. Unchanged source/reference JSON retained its original bytes.
- Current browser selection: **37 passed in 39.2s**. Initial schema-11 installed checks: **two passed in 22.5s**, including minimal CSV import, all **513 original source bytes**, interruption/reopen, identical restore retry and saved-result equality, plus the small installed fit/worksheet/worker path. Final artifact lifecycle after the export/UI correction: **one passed in 22.2s**. These are distinct overlapping checks, not one combined installed run.
- Generated contract match and negative checks, frontend typecheck/build, locked wheel-only install/dependency/import checks and final docs/link/diff checks passed. Final case-insensitive inspection found no synthetic/fictional classification in runtime Python, frontend source or generated API. Test fixture descriptions remain outside application contracts.

The October 27 authorized GitHub sync completed `./scripts/checkpoint.ps1`: **1,127 Python tests passed in 52.16s**, Ruff/formatting/strict mypy passed, and the fresh wheel built and passed locked dependency, wheel-only installation and isolated import checks. Full-suite receipt: `.local/test-workflow/runs/20261027T142950-7d67cc97/summary.json` (`passed`, `inputs_unchanged` and `full_suite` true). The browser checkpoint passed generated-contract and negative checks, typecheck/build and **37 tests in 41.5s**, with **two optional installed-artifact tests skipped** because that invocation did not select an artifact. The separate final-artifact evidence above covers that boundary.

The preceding relevant hosted run, [40124594169](https://github.com/jpeterson92/Prosper/actions/runs/40124594169), succeeded at remote revision **1fa1bc5bc076fb00b19368efbfdce5a9c7745dc8**. The newly triggered hosted result is unverified at this checkpoint; synchronization verifies upload without waiting for CI.

Same-agent review covered source/category separation, fetched/imported request identity, exact source/unknown preservation, mathematical and final-order checks, strict current record/recovery contracts, unsupported-state refusal and local browser/path safety. No large fit/study, actual/private source session, provider acquisition, independent review, financial acceptance, trading or product publication occurred.

## Current artifact

**prosper-inputs-final**, `.local/artifacts/prosper-inputs-final/`, schema **11**. Wheel SHA-256 **e56ee2e1b6b83468f04b05f5ccf6ecf8c98730f5d284c632fc35a460b5c77f26**. [Launch guide](guides/LOCAL_ARTIFACT.md) documents initialize/start with one selected workspace and no data mode. The named Windows 11 build 22635/AMD64 and CPython 3.12.4 host is tested; broader support is unqualified. Earlier artifacts/workspaces remain preserved.

## Next task and remaining gates

**MVP.1: one bounded owner input diagnostic session.** Use a named permissible public request or owner-operated file in the local UI. Inspect source/row/quantity/basis/identity/date/coverage findings, save/reopen and observe preparation burden before another generic infrastructure task. AI access to private contents still needs its concrete scope; this implementation did not read actual files or acquire providers.

MVP.2 uses the selected core and a reviewed configuration for no-trade/candidate/worksheet estimates when concrete inputs suffice. MVP.3 fixes the largest observed usability/correctness issue. Capacity work follows only an actual reached workload failure. No investor default, source truncation, alternate model or new solver was adopted.

Independent tax/model review, usable actual source conventions/rights/coverage and predeclared forward calibration remain required for their accepted claims and financial reliance. Owner usability/paper observation can occur earlier; external distribution and financial-use pilot authority remain later. Data classification is not a gate or a future application feature.

## Revision and synchronization scope

The authorized synchronization includes the accumulated local advisory workflow and owner-approved MVP simplification, category-field/scope/status removal, current core/API/UI/records/recovery, callers/tests/examples/generated contracts, and consolidated guidance, including the previously staged document removals. The tested candidate is based on local revision **69f8cba299b7d130a87684809df77fe124b8fe5d** on **main**, which was one commit ahead of remote main. The commit containing this handoff identifies the complete synchronized candidate; its exact SHA and verified remote-reference equality are reported in the sync response. Local artifacts, runtime workspaces and private files are excluded. Existing mathematical algorithms, source facts, security/state and financial-limit protections remain.

**Next action: conduct MVP.1 on one explicitly scoped input.** The application uses one data path; fictitious data remains a testing convention.
