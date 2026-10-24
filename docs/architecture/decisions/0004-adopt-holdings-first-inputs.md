# ADR-0004: Holdings-first imports, conditional history screening and selected cash

Date: October 23, 2026. Status: **Accepted**. Approver: project owner in this chat. D038-D039 record this update. This supersedes blanket requirements that every broker file supply transaction history, independent position/cash snapshots or a durable broker lot ID before any useful optimization. It does not remove checks on actual contradictory facts or authorize financial use, account access, trades or release.

## Owner direction and current scope

The owner directed Prosper to work with typical lot-level holdings information comparable to the supplied Fidelity combined file, display an unverified wash-sale warning when history is unavailable, offer manual identification of recently traded names, and make cash import optional. Before optimization, the user must see and be able to change how much existing cash the run may invest, including none or a portion. In response to a specific scope question, the owner selected **stock sleeve plus selected cash** for risk/benchmark comparisons, excluding untouched account cash from that calculation.

This request adopts product/data requirements and revises the project plan. The current implementation is a synthetic import foundation and a read-only combined-lot inspector, not a tax/risk optimizer. These new run controls and conditional planning modes are **not implemented by this documentation update**. Existing historical fixture/checkpoint contracts retain their meanings; no missing observed account balance is rewritten to zero and no financial readiness flag is switched on.

## D038: Minimal import and supplemental run facts

Use a lot snapshot as the normal entry point. The necessary imported financial core is account grouping, a resolvable security label, remaining lot quantity and reported total basis for lots considered for sale. Preserve acquisition date/term when supplied. Retain unsupported holdings for scope/risk diagnostics. Unknown total basis or genuinely ambiguous sale-lot identification excludes the affected sale; a rounded average is not a substitute for total basis. Unknown holding period may remain unknown in an unweighted loss-dollar objective; never fabricate ST/LT classification or imply that a date proves all inherited/carryover holding facts.

The system or user supplies missing profile/market/run facts separately. A broker file need not contain tax validation flags, benchmark weights, risk history, a covariance matrix, current execution quotes, account classification or every household relationship. Account labels are hints, not proof. Resolve these at onboarding or run setup and retain their source. Use current source-reported basis as a disclosed opening assumption for ordinary supported cases; do not demand reconstruction of the client's entire tax history. Known disputed basis, special events or unsupported asset classes still require a supported disposition.

Durable broker lot IDs, CUSIPs and independent position/cash exports are useful optional evidence. Internal immutable import/row IDs may identify observations; later lot matching can use account/security/acquisition/quantity/basis descriptors with explicit ambiguity handling and broker-view verification. Never assert that a file-local row ID persists across downloads. Summed lot quantities may form a **derived holdings view**, not an independent reconciliation proof. If a separate position file exists, compare it; disagreement remains a real blocker for its dependency scope. A missing redundant file is not itself a mismatch.

Record the holdings/as-of assertion, import/collection time and any reported intervening trades. A current holdings snapshot need not replay historical events to become usable. Keep history for screening separate from holdings truth; later activity cannot be added again to a snapshot merely because the same-day inclusion boundary is unknown. Freeze the accepted starting view and expose its source/user assumptions. Require refresh or explicit reconciliation when material holdings changes are known.

## Optional history and manual restrictions

No transaction-history file is required just to inspect holdings or run **conditional optimization**. When coverage is incomplete, show a persistent message such as: **"Transaction history is incomplete. Wash-sale eligibility has not been verified. These results depend on your inputs and future trading."** Record history coverage and evidence source separately from candidate/solver validity. An empty file or empty manual list is not a statement that no conflicts exist.

Offer a simple optional list of recently traded or otherwise restricted names. Resolve a typed name/ticker to the intended security and show it back to the user; do not guess an ambiguous identity. With names alone, exclude the resolved names from **both harvest sales and replacement buys for this run**, a conservative product rule. Dates, buy/sell direction, account/relationship and automation details are optional refinements; never manufacture them. Lists without dates do not auto-expire into a clean result and are reconfirmed on later runs. Include known related/security-alias restrictions where supported. An unresolved manual entry must be resolved or excluded safely before presenting a fully specified candidate.

Combine the manual list with actual evidence already available: recent acquisition dates in retained lots, any imported purchases/loss sales, open restrictions, the proposed batch and known household/automatic activity. Known conflicts remain excluded under PP01; missing history does not override a detected conflict. User reports and complete imported history retain different provenance. A scoped "no other relevant activity" declaration, if offered, is a dated user assertion rather than broker-validated evidence.

The manual list is a practical restriction input, **not a substitute for full legal validation**. Explain the relevant pre-sale review and post-sale monitoring period, other-account/spouse/IRA/Roth activity, reinvestments and recurring acquisitions, plus substantially identical securities. Continue forward monitoring from actual sales and flag newly reported conflicts. Do not describe gross/reference-price loss as confirmed deductible loss or tax savings. Conditional worksheets may be produced under stated assumptions when financial/risk/funding constraints are otherwise satisfied; broader financial-use and independent-review gates remain.

These are product handling choices. Primary-source context rechecked October 23: [IRS Publication 550 (2025), Wash Sales](https://www.irs.gov/publications/p550) discusses acquisitions in the inclusive 30-day periods on each side of a loss sale and related purchases; [Revenue Ruling 2008-5](https://www.irs.gov/pub/irs-drop/rr-08-05.pdf) addresses the specified IRA/Roth fact pattern. The planning change does not amend those rules or establish specialist validation.

## D039: Optional cash observation, explicit run budget and sleeve risk

Keep three concepts separate:

| Concept | Meaning |
| --- | --- |
| Observed/imported cash | Optional account fact with bucket, amount, currency, source and time; can be unknown. It is never overwritten by a run preference. |
| Selected additional cash budget (`cash_to_invest`) | The user's nonnegative maximum amount of existing cash this optimization may deploy alongside the stock sleeve. Zero means no additional existing cash, not an empty account. |
| Modeled residual cash | Cash left inside this run's sleeve after proposed trades, costs and rounding, recomputed by the independent validator. |

Before each run display imported/reported cash when available, the **selected budget to invest**, its source and any funding uncertainty. Always allow the user to edit the selected budget regardless of the import. Start an unset selection at zero with a visible review field; do not automatically spend all imported cash. Positive manual entry is a user-provided funding assumption, not verified cash. If current evidence contradicts that usable amount, resolve the discrepancy or reduce the budget; an edit cannot erase a known shortfall or pending commitment. Changing it creates a new frozen run/candidate; it never rewrites the imported account evidence or silently changes an approved plan.

The selected budget is a **cap**, not a promise to spend an exact amount. Whole shares, costs, minimum order sizes and hard constraints may leave some unused. Show expected use and residual; do not create tax-inefficient trades or a hidden objective reward simply to consume the budget. Selling existing holdings can still fund replacement purchases when the selected additional budget is zero. No borrowing or spending of untouched cash is implied.

Use the modeled sleeve denominator: `initial_sleeve_value = included stock holdings at reference marks + selected additional cash budget`. The baseline and proposed candidate use the same scope. Final sleeve NAV uses final holdings plus modeled residual cash, with costs accounted for consistently. Untouched account cash is outside that risk/benchmark calculation; label all such results as **stock-sleeve risk**, not whole-account or household risk. When the full account balance is unknown, do not invent its uninvested remainder. Optional account-level reporting may include known outside cash separately.

The existing cash equation becomes `final_sleeve_cash = cash_to_invest + gross_sell_proceeds - sell_fees - buy_principal - buy_fees`. Preserve reservation/funding/settlement checks and cost treatment. The cash floor applies to cash **inside the modeled sleeve**, not unknown external savings. The reported loss objective is unchanged: cash neither directly rewards loss harvesting nor disappears from feasibility/risk arithmetic. Small optional cash deployment alongside an existing stock sleeve is supported direction; starting entirely from cash or liquidating ETFs remains the separately scoped transition problem.

Total broker cash is not mandatory to optimize this sleeve. Actual proposed funding still needs a plausible sequence and user/broker confirmation before execution: net sale proceeds, selected usable cash, costs, pending commitments and account restrictions must agree. Holdings-only conditional runs must label unverified funding and must not claim that unsettled proceeds are immediately spendable. This distinction is consistent with the [SEC cash-account bulletin](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/updated-9) (updated August 7, 2026), checked October 23. No source licenses or brokerage capabilities are adopted here.

## Truly necessary additions, and who provides them

| Needed for | Input beyond the lot snapshot | Normal source |
| --- | --- | --- |
| Correct portfolio scope | Traded taxable account, currency, included holdings and current/as-of assertion; material changes/pending orders | One-time profile plus run review; supported reference lookup; user confirmation |
| Price/basis loss and specific-lot sales | Nonmissing reported total basis, quantities, supported security resolution and distinguishable sale lots | Lot file plus exception repair/broker lot view; no universal durable broker ID required |
| Replacement/risk optimization | Current marks, benchmark/target weights, candidate universe, supported risk estimates and explicit risk/operational constraints | Permitted application market/reference data and user-selected settings; no requirement to embed them in the broker CSV |
| Additional investment | Selected additional cash budget, allowing zero, with funding assumptions when needed | Editable run field; optional imported cash as a reference |
| Conditional wash screening | Warning/history status and optional manual restrictions; known imported conflicts still applied | Existing evidence and optional user input; complete history improves verification but is not an import prerequisite |
| Execution and later reconciliation | Specific-lot selection, actual fills/fees and confirmed allocations; material external changes | Broker/manual forms or later supported files; not required in the initial holdings snapshot |

Tax rates, prior returns, full lifetime transactions and income are not required for the adopted loss-dollar objective. They are separate optional scenario inputs if a later feature estimates tax-dollar value. No input route can turn unknown basis, contradictory holdings, unresolved security identity, invalid risk data or unfunded orders into a sound candidate through a generic warning.

## Required downstream changes and verification

The current inspector continues to report only source facts and unqualified readiness. Its missing-source observations must not become a universal permanent list of required broker columns. Implement readiness at the **assembled run/profile** level: observed, derived, user-reported, provider-supplied and missing facts remain distinguishable, with separate mathematical feasibility, wash-sale verification and execution/reconciliation states.

Carry D038 into T002.2/T017 onboarding/mapping and T005 manual/history screening; D039 into T006 weights/NAV, T007 candidate/validator funding, T008 run review and T018 frozen inputs/provenance. T009 must accept appropriately qualified manual fill/lot evidence as well as supported files. No optimizer, cash editor, manual-history UI or runtime readiness relaxation is implemented in this policy request.

Add validation for holdings-only conditional runs; missing history warnings and empty-list semantics; manual names blocking both legs; imported known conflicts surviving user omissions; future/household/automatic activity messaging; missing versus zero account cash; zero/partial/manual budget selection; imported balance retained when selection changes; stock-sleeve NAV/risk; rounding/cost residuals; insufficient funding; changed input invalidation; and manual execution evidence. Existing strict risk, zero-positive-gain, whole-share, unknown/contradiction, independent-review and release controls remain except for the explicit import/history/cash gate revisions above.

## Adoption, limitations and reconsideration

Observed acceptance is the owner's direction plus their sleeve-risk selection. The document/link/consistency checks are planning evidence; no new behavior, tax correctness, financial-use acceptance or release is established. Reconsider if a representative broker's lot file lacks reliable total basis/quantities, supported security identity cannot be resolved, user assumptions prove too burdensome, or paper qualification finds that funding/restrictions cannot be expressed reliably. Material new tax cases and whole-account optimization still need their own decisions.
