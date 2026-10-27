# Prosper v1 delivery plan

Current owner-adopted guidance, consolidated October 25, 2026. This page defines the destination and route; [remaining tasks](tasks/REMAINING_WORK_PLAN.md) own executable outcomes and dependencies, [STATUS](STATUS.md) owns observed state and exactly one next candidate. [Decisions](DECISIONS.md) is a compact authority/open-choice index, not required routine intake. Prior plans and ADR text are available in Git at `69f8cba299b7d130a87684809df77fe124b8fe5d`; no documentation archive is maintained.

## V1 working definition

A Windows x64 user with a supported existing taxable individual-stock sleeve can import a dated lot snapshot, inspect scoped errors/loss opportunities, explicitly select a Vanguard full-portfolio benchmark date and run settings, calculate the selected qualified risk model, compare constrained whole-share suggestions against no trade, and save/export a dated manual worksheet. The user can reopen saved current-format results, recover current user work and import refreshed holdings for the next session. Every result states its assumptions, data dates, exclusions and qualification state. A useful blocked/partial diagnostic is a supported outcome; an unsupported/failed calculation cannot become zero or a fabricated feasible suggestion.

A synthetic end-to-end build, a source-qualified build, an independently reviewed candidate, a paper-accepted application, an installed local v1 and an authorized financial-use/public release are different milestones. Do not call component tests a working integrated v1 or financial readiness.

## Fixed product choices

- U.S. federal taxable, one traded account plus relevant supplied household screening facts; existing long-only ordinary domestic common equities and USD cash. Whole-share proposed trades retain fractional holdings. Unsupported/unmapped instruments are explicit modeled-sleeve exclusions with source observations retained.
- Holdings-first input; transaction history and imported account cash are optional. Missing history allows conditional screening with a persistent warning/manual restrictions. Known conflicts, ambiguous identity, missing sale basis, contradictory holdings and invalid required risk/funding remain scoped blockers.
- Equity-only disclosed Vanguard holdings proxy, explicit fund/reporting date, retained primary marketValue/E weights, complete source/exclusion accounting and no basket/date/source fallback. No fund is silently selected. Secondary custom files are accepted optional follow-on scope.
- Risk target is the maintained Python IDR/OHLC DCC-NL method, analytical nonlinear shrinkage and one covariance for TE/group attribution, with explicit variant/independent-review/calibration requirements. No model substitution is adopted by this plan.
- Eligible price/basis loss objective, zero positive-gain sales, strict explicit investor limits, independent final discrete checks and honest search status. Additional cash budget and optional final cash target are separate reviewed settings. No hidden personalized thresholds.
- Advisory output ends at saved estimates/manual worksheet. Execution/fill/account reconstruction, basis maintenance, reservations, forward monitoring and background history scheduling are deferred. After external trades, refresh holdings.
- No backward compatibility with unreleased implementations. Update callers together, remove old readers/shims/duplicate paths, and use an identified fresh development runtime/reimport when needed. No silent data wipe or automatic repair.

The actual behavior is defined in [product](product/SPEC.md), [tax](domain/TAX_POLICY.md), [portfolio construction](domain/PORTFOLIO_CONSTRUCTION.md), [benchmark/market inputs](domain/BENCHMARK_INPUTS.md), [risk](domain/RISK_MODEL.md), [records](architecture/DATA_CONTRACTS.md) and [numerics](engineering/ADVISORY_NUMERICS.md). Read only the affected contracts for a task.

## Delivery route

The owner adopted the October 27 [MVP reset](reviews/2026-10-27-mvp-scope-review.md). T019 and the synthetic import-to-worksheet workflow are implemented. The current route is:

1. **Actual-input diagnostics:** one scoped public or owner-operated input session; useful source/lot/coverage facts and located unknowns, saved and reopened. Simple CSV opening does not require a manually authored context document or fitted risk.
2. **Exploratory model to worksheet:** reuse the selected risk core and one explicitly reviewed research configuration. When actual declared inputs satisfy mathematical conventions/completeness, permit an uncalibrated exploratory fit and a bounded independently checked candidate. Compare no trade, export a dated manual worksheet and exercise one backup/reopen. Preserve all enabled financial limits.
3. **Observed improvement:** fix the largest real usability/correctness gap from those sessions. Measure capacity only for the actual declared workload. Financial reliance and public distribution have their own later review/qualification/authority milestones.

One local application and one selected data directory per instance suffice. All inputs use the same contract and processing path. The application does not track whether data is invented or real. Source bytes/dates/identity/provider/conventions determine usability; test fixtures remain an engineering practice. Keep actual date/unit/action/identity/coverage checks and explicit unqualified result labels.

Keep the implemented history cache, compressed tables/source storage, worker and recovery. Do not expand/rewrite these without a concrete observed need. One bounded search method and one useful checked incumbent suffice; global optimality, a second solver, richer frontiers and new optional controls are not MVP prerequisites. Keep advanced controls available without expanding the first-session setup burden.

[Remaining work](tasks/REMAINING_WORK_PLAN.md#mvp-delivery-route) names current outcomes. Existing component/task evidence remains scoped evidence, not a mandatory historical intake chain. No generic larger synthetic capacity run, another disposition packet or installer/platform-support project is queued.

## Readiness and unresolved decisions

G0-G3 and release evidence are defined once in [VALIDATION](engineering/VALIDATION.md#acceptance-gates). They remain open where not actually evidenced. Relevant open decisions are listed in [DECISIONS](DECISIONS.md#open-choices): qualified data/settings, discrete method, supported years/freshness/scale, tax/model review, license/distribution/support and actual manual broker workflow. Prepare concrete evidence before asking; do not reopen adopted fund-route, equity-scope, numerical, Python, cache/manual-refresh or no-compatibility choices.

No dated delivery promise is made. Existing component tests and the checkpoint provide a starting implementation, not proof of integrated source/financial usability. Local source commits are separate from publication and investor-data backups.

## Outside the v1 critical path

T009 execution/basis/forward-monitoring work; scheduling; ETF/bond/derivative portfolios and cash/ETF transitions; broader countries/currencies; broad risk-model searches; alternative databases/accelerators; Tauri replacement; AI explanation; showcase hosting; and nonessential custom uploads remain deferred or optional. Retain the accepted roughly 20% bounded learning reserve as optional owner-selected work, never mandatory spend or a core prerequisite. A marimo/reference exercise is useful when it answers a concrete qualification question; its tool adoption is not another gate. Evaluate Tauri/Python sidecar only after the working advisory workflow demonstrates a launcher need. Public hosting, AI providers, costs, real data and release require their own authority.
