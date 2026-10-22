# ADR-0002: Adopt the critical-review actions and first implementation boundary

Date: October 22, 2026. Status: **Accepted**. Approver: project owner, in this chat.

## Approval and scope

After the product/engineering review, the owner instructed: "Make all suggested changes."

Adopt the review's recommended product policies, engineering clarifications, earlier feasibility checkpoints and bounded first-slice preparation. This is approval to revise and complete planning. It does not authorize application implementation, dependency installation, account access, real-data disclosure, external contact, publication or deployment. [ADR-0001](0001-adopt-project-architecture.md) continues to govern the adopted stack.

## Product decisions

1. **First pilot:** an investor who already owns an eligible individual-stock sleeve, understands a chosen benchmark and can supply supported lot/activity/coverage evidence. ETF/cash onboarding and concentrated transitions remain deferred. No minimum account value or investor satisfaction is inferred from the synthetic examples.
2. **Infeasible or drifted sleeves:** retain strict investor risk caps, zero positive-gain budget and whole-share order policy. Show baseline breaches and diagnostic reasons; do not relax limits automatically. Test candidate yield on representative sleeves. Broader remediation or gain budgets require a later explicit scope change.
3. **Objective and economics:** maximize eligible price/basis loss measured at reference prices, excluding transaction costs from the objective reward. Report indicative net-proceeds tax P&L separately. Respect required explicit cost/order/turnover/notional settings and optional investor-configured minimum-loss/cost-to-loss or scenario-value screens. No invented personalized tax rates or monetary defaults. Use lower modeled cost and then fewer orders as deterministic tie-breaks, without changing the primary objective.
4. **Supported tax cases:** initially support documented ordinary common equity in domestic U.S. corporations with qualified adjusted-basis/holding-period evidence. Exclude from actionable generation REIT/RIC/BDC, partnership units, ADR/foreign/uncertain tax classifications and unqualified special events. Preserve those holdings/evidence for diagnostics; do not drop them from account NAV or risk. Screen extraordinary/special distributions, corporate actions and carried holding periods through reviewed rules/evidence. Unknown impact blocks its dependency scope, or the account if unbounded. This is a conservative product boundary, not a claim that excluded assets cannot be harvested lawfully.
5. **First investor platform:** Windows x64. Pin and test supported Windows versions, browser/runtime and solver binaries during the foundation work. macOS/Linux investor support remains unqualified and deferred; platform-neutral core design and contributor development are not a cross-platform release claim.

Detailed economics are authoritative in [portfolio construction](../../domain/PORTFOLIO_CONSTRUCTION.md); the exact-value/foundation contract is in the [foundation specification](../../engineering/FOUNDATION_SPEC.md). Numeric limits and platform selections in that specification are engineering boundaries, not personalized investment defaults.

## Engineering and sequencing actions

Adopt explicit snapshot inclusion semantics, staged ambiguous imports, actual-versus-shadow separation, bidirectional household restriction screening, frozen computation inputs, atomic freshness/approval/reservation checks, idempotent mutation commands, uncertain external-execution holds, honest solver-result statuses, final-order cost/NAV/risk validation and application-level restore manifests. These remain requirements awaiting software implementation and verification.

Finish the G0 written specification and first implementation brief. Then, after a separate implementation instruction, deliver a small synthetic import/reconciliation/UI/API slice. Establish G1 broker/data/manual-workflow feasibility before substantial P3/P4 build-out. Exercise a small complete synthetic execution/reconciliation cycle before broad optimizer/UI depth. Keep full Tauri work staged after the accepted workflow.

The 20% learning reserve remains bounded optional exploration, not required spending or a substitute for financial-quality work. Keep the 14-25 core / approximately 18-32 total-week range as a provisional planning scenario until qualification produces evidence.

## Evidence still required

No real broker workflow, market-data rights/access, risk settings, discrete solver, exact dependency versions, supported Windows versions, specialist review, installation, performance or user acceptance is established by this approval. D010/D012/D014/D016/D017/D018/D027 remain open at their documented scope. Do not reopen the now accepted D031-D035 without material new evidence or an explicit requirement change.

## Consequences and reconsideration

The first usable pilot is deliberately narrower than the long-term self-directed-investor goal. Report unsupported cases, blocked-candidate yield and user burden honestly. Reconsider scope if representative evidence shows the accepted combination rarely produces useful plans. Record changes explicitly rather than silently adding gains, different risk limits, unsupported tax classes or a new deployment platform.
