# Written reference portfolio

Status: fully synthetic planning example, not a tradable portfolio or implemented test fixture. It gives future implementation an independently checkable small problem. These two-name exposures are intentionally unrealistic for a diversified investor portfolio.

## Case R01: A tiny direct-indexing harvest

Analysis date: October 22, 2026. One synthetic taxable account, no borrowing, no other assets, no relevant acquisitions during the lookback and no open restrictions from earlier sales. Household activity is stipulated complete for this fictional example. Actual future absence of purchases is not knowable; the proposed loss remains conditional on forward activity.

| Security | Quantity | Price | Market value | Total adjusted basis | Acquisition date |
| --- | --- | --- | --- | --- | --- |
| SAAA | 100 | $80 | $8,000 | $10,000 | January 2, 2024 |
| SBBB | 100 | $80 | $8,000 | $8,000 | January 2, 2024 |
| Cash | N/A | N/A | $0 | N/A | N/A |

NAV is $16,000. Synthetic benchmark: 50% SAAA, 50% SBBB, zero cash. Synthetic annualized covariance: variance 0.04 for SAAA, 0.09 for SBBB, zero covariance; cash variance/covariance zero. This matrix is stipulated for arithmetic, not estimated from a market data source. Stable IDs distinguish the two fictional issuers, and tax identity is stipulated reviewed/nonidentical.

For this reference problem only:

- Sell n whole shares from the single SAAA lot and buy n whole SBBB shares, at the stated prices.
- n is an integer from 0 through 100; SBBB is no-sell and no other securities are eligible.
- Fees/spreads are zero, NAV stays constant, no cash is left over, no gains are realized.
- At most two orders. Minimum one share if trading. No other binding weight/sector limits.
- Annual TE cap is 2%. Objective is to maximize eligible gross realized loss.

These are fixture assumptions, not recommended investor defaults. In particular, zero costs and frictionless same-price execution are not operational claims.

## Independent calculation

After the trade, active weights are `(-n / 200, +n / 200)`. Therefore:

`TE(n) = (n / 200) * sqrt(0.04 + 0.09)`.

Loss before wash adjustments is `$20 * n`. TE increases with n, so the largest feasible whole n is 11.

| Candidate | End shares SAAA/SBBB | Conditional loss | Annual TE | Result |
| --- | --- | --- | --- | --- |
| n = 0 | 100 / 100 | $0 | 0% | Feasible baseline |
| n = 10 | 90 / 110 | $200 | about 1.80278% | Feasible |
| n = 11 | 89 / 111 | $220 | about 1.98305% | Best feasible integer in this restricted menu |
| n = 12 | 88 / 112 | $240 | about 2.16333% | Violates risk cap |

For n=11, allocated sold basis is $1,100, proceeds $880, remaining SAAA basis $8,900, SBBB purchase cost $880 and cash $0. The opening SBBB basis and new purchase basis remain separate lots.

The output is conditional eligible loss, not a $220 tax refund. Future tax use and liquidation effects are separate.

## Case R02: One changed tax fact

Replace the clean history with a known recent SAAA reinvestment in an external relevant account on October 12, 2026, while leaving the traded sleeve unchanged. Under PP01, SAAA becomes excluded from actionable harvest generation. The product must explain the conflicting acquisition and return no harvest in this restricted menu. It must not retain the R01 recommendation solely because its risk and arithmetic still pass.

## Case R03: One changed cost fact

Keep the R01 proposed n=11 orders but add $10 total execution costs, still with zero opening cash. Same-quantity buys and sells now leave cash at -$10. The independent validator must reject those orders. A new candidate with different quantities/cash must be generated and risk-checked; this document makes no optimality claim for that changed problem.

## Case R04: Execution differs from intention

The investor records a fill of only 5 SAAA shares and no SBBB fill. Record the actual sale, remaining 95 SAAA shares, $400 proceeds before actual costs, and the actual sale's forward restriction. Do not record the planned 11-share sale or a replacement purchase that never occurred. Require a new holdings/cash/risk review before another plan.

For this sale date, the inclusive window runs from September 22 through November 21, 2026; November 22 is day +31. This date example remains subject to the documented tax-date convention and future source review. A December sale would retain a January forward window rather than reset at year end.

## Case R05: Replacement buy conflicts with prior household sale

Keep R01's traded sleeve but stipulate a documented external household SBBB loss sale ten days earlier. Buying SBBB in any n>0 candidate requires screening against that sale and its open restriction. A valid SAAA sale screen alone cannot clear the two-leg plan. With SBBB the only allowed replacement, no n>0 candidate is qualified under these assumptions. If the earlier sale's P&L is unknown, classify the dependency as unresolved rather than assuming a gain.

## Case R06: Date-only snapshot inclusion is ambiguous

A synthetic source reports 100 SAAA shares as of October 22 and separately reports a one-share purchase that day, without a timestamp/inclusion convention. Do not report 101 shares by applying that activity to the snapshot, or infer whether 99 shares existed before it. Stage and resolve the inclusion boundary. Historical screening can still retain the purchase as evidence without replaying it into holdings.

## Case R07: Approval result becomes stale

Analysis A freezes the R01 state. A later import changes its lot state before A finishes. Preserve A's arithmetic as evidence of the old input bundle, but do not approve/reserve it against the current account. A repeated approve command cannot create a second reservation. No database/job implementation exists; these are required state-transition outcomes.

## Acceptance use and limits

T001 should confirm these assumptions and the wider [scenario inventory](../engineering/VALIDATION.md). During authorized implementation, build executable fixtures from reviewed expectations and use enumeration to check the restricted menu. The R01 solution establishes only correctness on this tiny stated problem, not production model quality, global optimality for a larger universe or expected investment performance.
