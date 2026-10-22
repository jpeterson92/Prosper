# Tax-policy framework

Status: sourced planning requirements and adopted conservative product policies; not an implemented or professionally validated tax engine. The owner accepted the project baseline on October 22, 2026. Source-backed factual cases still require qualification. Sources were checked October 22, 2026; Publication 550 presents the 2025 edition in that review. Recheck applicable law and tax-year materials before implementation and each release. See [source ledger](../research/SOURCES.md).

## Distinguish four kinds of statement

1. **Sourced rule:** a legal/tax statement supported by primary material, with effective scope and review date.
2. **Product policy:** an intentionally conservative handling choice that may exclude legally permissible trades.
3. **User assumption:** a dated assertion such as no relevant activity in a specified external account during a specified interval.
4. **Estimate:** a price, cost, model output or tax scenario, with its inputs and uncertainty.

Do not promote a conservative policy into a claim about tax law. A coding agent cannot resolve uncertain law by making a test pass.

## Rule register

| ID | Sourced requirement | Consequence for design | Evidence |
| --- | --- | --- | --- |
| TX01 | Loss sales can be affected by substantially identical acquisitions within 30 days on either side of the sale | Inclusive calendar-day boundary cases and forward monitoring | [IRS Pub. 550, Wash Sales](https://www.irs.gov/publications/p550) |
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

**PP02: Future eligibility is provisional.** A plan can screen known past activity, not prove absence of future purchases. Track the forward window from actual sale dates, record automatic purchase controls and show outstanding monitoring obligations. New purchases invalidate affected provisional estimates. Calendar dates use a documented tax-date convention; exchange timestamps and settlement dates remain separate. Do not use business-day or settlement-day shortcuts.

**PP03: Coverage is a prerequisite.** Require relevant activity for the inclusive lookback plus open unresolved restrictions from earlier sales. Opening adjusted basis and holding-period evidence must be authoritative. A 30-day activity file cannot prove all historical basis adjustments or repeated wash chains. An opening snapshot is an accepted starting state, not a reconstruction of all prior tax history.

**PP04: Identity is explicit and reviewed.** Stable security identity, issuer/share-class relationships, corporate-action successors and potential equivalents are distinct from ticker symbols. Same-security reacquisition is a known conflict. Different tickers, high correlation or different issuers do not by themselves settle every legal case. Use versioned relations with status, rationale, reviewer and validity period. Unknown affected relationships block plans. No automated ETF-pair clearance or correlation-based legal classification.

**PP05: Household visibility is bounded.** Record traded taxable, other taxable, spouse, IRA/Roth, employer equity plans, recurring investments and any controlled-entity relevance. Other retirement plans and unusual relationships stay unresolved where tax scope is uncertain; do not label them automatically exempt or automatically equivalent to the IRA ruling. Capture relevant external trades or scoped attestations, and display their expiry. Missing visibility is an unknown, not a clean result.

**PP06: No full historical tax ledger in v1.** Consume reviewed broker/user adjusted basis and preserve its provenance. Detect newly observed conflicts and route them to reconciliation. Do not automatically rewrite authoritative basis or holding periods. Complex chains, gifts, inheritances, reorganizations and ambiguous transfers are blocked until separately supported or a reviewed opening state is supplied.

**PP07: User controls automatic activity.** Reinvestments, recurring purchases and employee share acquisitions can conflict with harvesting. Record settings/status as dated investor evidence; do not claim to disable them or infer that they remain disabled. The product does not place orders in monitored accounts.

Screen every proposed sale and purchase against relevant prior household acquisitions/loss sales, open restrictions and planned same-batch actions. A replacement buy can conflict with an earlier loss sale in a monitor-only account even if the currently planned sale is otherwise clear. Unknown P&L on a relevant prior sale is not evidence that it was a gain. This clarifies PP02/PP03/PP05; it does not add a full historical matching engine. Under PP06, newly detected conflicts can mark basis/holding evidence unresolved until authoritative correction is supplied.

The supported first tax-case policy in D034 is now adopted: qualified ordinary common equity in domestic U.S. corporations with supported adjusted basis and holding-period evidence. REIT/RIC/BDC, partnership units, ADR/foreign and uncertain classifications are excluded from actionable generation initially. Unqualified special distributions/corporate actions/holding-period events block affected recommendations; do not drop such holdings from diagnostics, account NAV or risk. Where exposure/dependency impact cannot be bounded, block the account-level actionable plan. This is conservative product scope, not a legal conclusion about excluded investments.

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
