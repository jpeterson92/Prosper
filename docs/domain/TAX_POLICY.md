# Tax-policy framework

Status: sourced planning requirements and adopted conservative product policies; not an implemented or professionally validated tax engine. The owner accepted the October 22 baseline and October 23 D038 input/history amendment. Source-backed factual cases still require qualification. The October 22 source review was supplemented by a targeted October 23 check of Publication 550 (2025 edition) and Revenue Ruling 2008-5 for warning context; other rules were not broadly refreshed. A targeted October 25, 2026 primary-source refresh of [Publication 550 (2025 edition)](https://www.irs.gov/publications/p550) and [Revenue Ruling 2008-5](https://www.irs.gov/pub/irs-drop/rr-08-05.pdf) checked the inclusive 30-day, spouse/IRA and lot-identification warning context before T005.1 implementation. This refresh does not qualify 2026-specific tax materials, account-specific broker behavior or an independent tax interpretation. Recheck applicable law and tax-year materials before financial use and each release. See [source ledger](../research/SOURCES.md).

## Distinguish four kinds of statement

1. **Sourced rule:** a legal/tax statement supported by primary material, with effective scope and review date.
2. **Product policy:** an intentionally conservative handling choice that may exclude legally permissible trades.
3. **User assumption:** a dated assertion such as no relevant activity in a specified external account during a specified interval.
4. **Estimate:** a price, cost, model output or tax scenario, with its inputs and uncertainty.

Do not promote a conservative policy into a claim about tax law. A coding agent cannot resolve uncertain law by making a test pass.

## Rule register

| ID | Sourced requirement | Consequence for design | Evidence |
| --- | --- | --- | --- |
| TX01 | Loss sales can be affected by substantially identical acquisitions within 30 days on either side of the sale | Inclusive calendar-day boundary cases and explicit future-activity warning | [IRS Pub. 550, Wash Sales](https://www.irs.gov/publications/p550) |
| TX02 | Relevant acquisitions can include a spouse's purchases; IRA/Roth acquisitions require distinct treatment | Model related-account coverage rather than just the traded account | [IRS Pub. 550](https://www.irs.gov/publications/p550) |
| TX03 | Ordinary taxable replacement acquisitions can transfer disallowed loss into basis and carry holding-period history | Preserve existing adjustments and lineage; never double-apply them | [IRS Pub. 550](https://www.irs.gov/publications/p550) |
| TX04 | In the ruling's IRA/Roth case the loss is disallowed without increasing IRA basis | Do not treat every conflict as recoverable tax deferral; do not generalize to every retirement vehicle | [Rev. Rul. 2008-5](https://www.irs.gov/pub/irs-drop/rr-08-05.pdf) |
| TX05 | Unequal quantities require share matching; identity depends on facts and circumstances | Keep quantity-aware evidence and reviewed identity relationships | [IRS Pub. 550](https://www.irs.gov/publications/p550) |
| TX06 | Required broker wash-sale reporting has narrower same-account/same-CUSIP covered-security scope | Broker flags cannot establish complete investor eligibility | [2026 Form 1099-B instructions, box 1g](https://www.irs.gov/instructions/i1099b) |
| TX07 | Loss use depends on capital netting and carryover rules; excess losses have an annual ordinary-income limit | Do not multiply every loss by a tax rate and call it realized savings | [IRS Topic 409](https://www.irs.gov/taxtopics/tc409) |
| TX08 | Particular-lot basis requires adequate share identification | Preserve intended and broker-confirmed lots as separate facts | [IRS Pub. 550, Stocks and Bonds](https://www.irs.gov/publications/p550) |

Detailed matching, holding-period tacking, specific-identification procedure and basis-adjustment propagation need source-linked expected cases and qualified review before the corresponding feature is accepted.

## Adopted initial product policies

**PP01: Avoid known-conflict harvests.** If a relevant, already observed acquisition in the lookback creates a conflict, exclude the affected security from initial actionable harvest generation. Display the amount and evidence available; do not optimize around partial disallowance in the first release. This is stricter than a full legal matching engine. A diagnostic fixture may calculate partial disallowance to validate semantics without authorizing that strategy.

**PP02: Future eligibility is provisional.** A run screens supplied relevant activity and cannot prove absence of future purchases. Carry the future-activity/automatic-purchase assumptions and warning into review/worksheet; v1 does not track actual sales or operate forward monitoring. Subsequent supplied purchases can change a new estimate; after external trades require refreshed holdings. Calendar dates use the reviewed tax-date convention; exchange/settlement time remains separate, with no business-day shortcut.

**PP03: Distinguish coverage from conditional planning.** Under the [current holdings-first workflow](../product/SPEC.md#investor-workflow), incomplete transaction history produces an explicit unverified-wash-sale warning, not a universal ban on optimization. Allow conditional plans under displayed source/user assumptions and optional manual recent-name restrictions, while preserving known conflicts and other scoped financial blockers. A manual list or scoped attestation is not broker-validated history, and an empty list proves no absence. Complete historical-screening claims require supported relevant activity and a supported disposition of prior restrictions; future eligibility remains provisional under PP02. Accept source-reported total basis as a disclosed opening assumption for supported ordinary cases, preserving provenance and known disputes/adjustments; do not require full historical reconstruction or fabricate missing basis/holding evidence.

**PP04: Identity is explicit and reviewed.** Stable security identity, issuer/share-class relationships, corporate-action successors and potential equivalents are distinct from ticker symbols. Same-security reacquisition is a known conflict. Different tickers, high correlation or different issuers do not by themselves settle every legal case. Use versioned relations with status, rationale, reviewer and validity period. Unknown affected relationships block plans. No automated ETF-pair clearance or correlation-based legal classification.

**PP05: Household visibility is bounded.** Record traded taxable, other taxable, spouse, IRA/Roth, employer equity plans, recurring investments and any controlled-entity relevance. Other retirement plans and unusual relationships stay unresolved where tax scope is uncertain; do not label them automatically exempt or automatically equivalent to the IRA ruling. Capture relevant external trades or scoped attestations, and display their expiry. Missing visibility is an unknown, not a clean result.

**PP06: No full historical tax ledger in v1.** Consume reviewed broker/user adjusted basis and preserve its provenance. Keep newly supplied conflicts as scoped blockers until supported source facts resolve them; no fill/account reconstruction service is required. Do not automatically rewrite authoritative basis or holding periods. Complex chains, gifts, inheritances, reorganizations and ambiguous transfers are blocked until separately supported or a reviewed opening state is supplied.

**PP07: User controls automatic activity.** Reinvestments, recurring purchases and employee share acquisitions can conflict with harvesting. Record settings/status as dated investor evidence; do not claim to disable them or infer that they remain disabled. The product does not place orders in monitored accounts.

**PP08: Manual restrictions are a supported input route.** Offer optional recently traded/restricted names, resolved to securities and scoped to the run. Names alone conservatively exclude both harvest sales and replacement purchases; dates, direction, related accounts and automation can refine the input. Merge actual known conflicts from imports, retained recent lots and open restrictions; user omission cannot clear them. Keep missing/user-reported/imported coverage separate and warnings on conditional results. The [product workflow](../product/SPEC.md#investor-workflow) and [portfolio contract](PORTFOLIO_CONSTRUCTION.md) own source/review/conditional-output behavior; forward monitoring is deferred. This changes product handling of uncertainty, not the legal rule or professional-review gate.

Screen every proposed sale and purchase against relevant prior household acquisitions/loss sales, open restrictions and planned same-batch actions. A replacement buy can conflict with an earlier loss sale in a monitor-only account even if the currently planned sale is otherwise clear. Unknown P&L on a relevant prior sale is not evidence that it was a gain. This clarifies PP02/PP03/PP05; it does not add a full historical matching engine. Under PP06, newly detected conflicts can mark basis/holding evidence unresolved until authoritative correction is supplied.

The supported first tax-case policy in D034 is qualified ordinary common equity in domestic U.S. corporations with supported basis and retained holding evidence. D038 permits source-reported total basis as a disclosed ordinary-case opening assumption and unknown holding term in an unweighted loss-dollar calculation; unknown term cannot support an ST/LT or tax-dollar claim. REIT/RIC/BDC, partnership units, ADR/foreign and uncertain classifications are excluded from actionable generation initially. Known unqualified special distributions/corporate actions/holding-period events block affected recommendations; preserve these observations and exclusion reasons in diagnostics; the equity-only modeled sleeve excludes unsupported/unmapped instruments under the [market-input contract](BENCHMARK_INPUTS.md), while an unbounded effect on included holdings remains a blocker. Where exposure/dependency impact cannot be bounded, block the account-level actionable plan. This is conservative product scope, not a legal conclusion about excluded investments.

Use versioned reviewed classification/identity rules with documented exceptions. Do not require an individual opinion on every possible stock pair, infer legal identity from correlation or override adjusted holding-period evidence with acquisition date alone. An authoritative reviewed opening state can carry qualified prior adjustments; it does not authorize reconstruction of unsupported historical chains. Special-case and fee-allocation behavior still requires source-linked expectations and specialist qualification before financial use.

## Amounts and tax-benefit presentation

For a supported lot sale, compute estimated realized P&L as net proceeds minus adjusted basis allocated to shares sold. Prevent double counting acquisition fees already in basis or selling fees already in net proceeds. Keep fees, spread estimates and price changes visible. Show ST/LT categorization separately and preserve unknown holding periods.

Distinguish these report fields:

- Gross realized loss before wash adjustments, with price/cost assumptions.
- Modeled currently allowable loss, provisional until future activity and coverage are resolved.
- New potential carryforward, if a complete enough scenario supports it.
- Illustrative current-year tax reduction under user-supplied offset assumptions.
- Estimated transaction cost and portfolio-risk change.

The optimizer's eligible price/basis loss excludes cost reward, while indicative net-proceeds tax P&L can include qualified selling expenses. Label these fields distinctly using the [portfolio accounting equations](PORTFOLIO_CONSTRUCTION.md). A modeled gain/loss is still conditional on actual fills, basis, household coverage and applicable tax rules.

The first product does not compute a complete return. Default to loss amounts. An optional marginal-value scenario can use $2,000 eligible loss times an explicitly assumed 30% applicable offset rate = $600 current-period value before costs. This calculation assumes the loss can be used at that rate; it is not an inferred tax liability. With $20 estimated costs the illustrative immediate net is $580. With no usable current offset, immediate benefit can be zero while a potential future carryforward remains. Later liquidation can reduce or reverse benefits through lower basis. Do not market that scenario as lifetime savings or tax alpha.

## Required review before financial use

Review the sourced rule register and expected cases with a qualified U.S. tax practitioner. Resolve specific-lot procedure, household relationships, boundary dates, existing adjustments, inherited holding periods, partial matching and unsupported events. Store a dated record of what was reviewed and what was not. This is an adopted project acceptance gate, not a claim that a review has happened or that review can guarantee tax outcomes.

## Regulatory boundary

Local execution and open-source distribution do not establish a legal exemption for the resulting product or any service built around it. SEC materials describe algorithmic investment advisory services as subject to advisory obligations in applicable cases. The project's actual distribution, recommendations, compensation and service model need qualified legal scoping before external pilot/public beta. Do not use a disclaimer as evidence that classification is resolved. [SEC guidance release](https://www.sec.gov/newsroom/press-releases/2017-52).


T005.1 implements local synthetic conditional price-loss estimates and conservative supplied-fact exclusions under PP01/PP03/PP08. It keeps unknown source term, date, identity, scope, basis and history coverage explicit. It does not allocate wash-sale shares, adjust basis or determine deductible loss; no sourced-rule or independent-review gate closes because the tests pass. The API and browser label loss before wash adjustments separately from net-proceeds P&L and carry the future-activity/coverage warnings into immutable saved results.
