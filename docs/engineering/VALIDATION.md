# Verification and acceptance framework

Status: evidence framework adopted with the October 22, 2026 project baseline. T003.1 now has executable toolchain qualification tests; no application/financial verification has been performed. Written expectations below still need implementation and the specified independent/specialist review. Evidence is distinguished in [STATUS.md](../STATUS.md).

## Evidence model

Verification must address data semantics, tax assumptions, numerical behavior and actual investor workflow. Code and tests written from the same mistaken interpretation can agree. Create expected outputs independently: source-linked arithmetic cases, tiny enumerated portfolio problems and broker workflow evidence. Independently review tax/risk cases before using them as financial acceptance standards.

Future suites should include domain unit tests, golden reference cases, property/invariant tests, adapter contract tests, end-to-end workflow tests and observed manual acceptance. Use each where it can catch a distinct failure. Do not add tests that merely restate implementation internals or a line-count target.

## Reference scenario pack

Every fixture must record provenance, assumptions, supported/diagnostic-only status and expected outcomes. Synthetic symbols below are invented. D is an actual sale's tax trade date; calendar boundaries require reviewed date semantics.

| ID | Scenario | Independently specified expectation |
| --- | --- | --- |
| V01 | Old lot: 100 shares, adjusted basis $10,000, sale price $80, no fees/conflicts | Proceeds $8,000; realized loss $2,000 before any wash adjustment; tax value not inferred |
| V02 | Same old lot, sell 40 shares at $80 | Allocated basis $4,000; proceeds $3,200; loss $800; 60 shares remain with basis $6,000 |
| V03 | Separate relevant acquisition at D-30, D-31, D, D+30, D+31, each tested in isolation | Inclusive +/-30 dates in window; +/-31 outside this sale's window; pre-sale known conflict blocks under PP01; future conflict changes provisional outcome |
| V04 | Sell 100 old shares at $20 loss/share; 25 retained replacement shares acquired at $82 within window | Diagnostic legal-matching case: $500 disallowed, $1,500 allowable, replacement total basis $2,550 under simple taxable assumptions; first planner avoids known lookback conflict rather than exploiting it |
| V05 | Same security acquired in own IRA after loss sale | Distinct disallowance treatment; never add disallowed loss to IRA basis. Practitioner reviews factual scope |
| V06 | Spouse activity/DRIP known; separate case with external coverage unknown | Known activity detected; unknown coverage remains unknown and blocks affected plan; no single-account clean certification |
| V07 | Two overlapping downloads, then replay same file | Stable events imported once; ambiguous duplicate identity flagged; snapshots do not double holdings |
| V08 | Source adjusted basis $1,100 already includes $100 prior adjustment | Preserve $1,100; never automatically add $100 again |
| V09 | Missing basis, missing holding-period evidence, inconsistent lots versus positions | No affected actionable sales; no zero basis or fabricated date; account reconciliation status fails where appropriate |
| V10 | 100.25 shares ingested, whole-share order policy | Keep all 100.25 in state; sale can use supported whole shares with correct basis allocation and preserved remainder; never truncate holdings |
| V11 | Different ticker but same security; unresolved successor/share-class relation | Stable identity detects alias; uncertain relation blocks affected candidate |
| V12 | Benchmark 50% A/50% B, portfolio 60% A/40% B, annual covariance diag(0.04,0.09) | Active weights +10/-10 percentage points; variance 0.0013; annual TE about 3.60555%. Units, order alignment and rounding checked independently |
| V13 | Non-PSD matrix, missing holding/benchmark history, stale quote | Invalid risk inputs/prices block actionable plan; sector proximity is not a TE substitute |
| V14 | Tiny 3-5-name, integer-share portfolio | Enumerate valid orders independently; selected solution feasible and objective claim supported; heuristic never labeled globally optimal without evidence |
| V15 | Rounding changes risk or cash | Recompute after rounding; reject/repair then validate; pre-round feasibility is insufficient |
| V16 | $8,000 sell proceeds, $8,000 purchases, $10 costs, zero starting cash | Cash would be -$10; reject or reduce purchases. Do not hide costs in a balancing entry |
| V17 | No candidate can satisfy risk, cost, lot or buy restrictions | No actionable plan plus binding-constraint explanation; no silent relaxation |
| V18 | Gains from one lot offset by larger losses in another, zero positive-gain budget | Reject positive-gain sale even if total net P&L is negative |
| V19 | Approved plan, then corrected lot import/new trade/settings change | Old candidate expires/supersedes; execution evidence still accepted for reconciliation if investor already traded |
| V20 | Partial sell fill, replacement buy fails, or broker uses different sale lot | Record actual state, flag exposure/cash/lot issue; do not mark reconciled or replay original quantities |
| V21 | December loss sale followed by January purchase | Keep cross-year monitoring; update prior provisional result under applicable rules |
| V22 | $2,000 usable loss at assumed 30% offset, $20 costs; then no current offset | Scenario A $600 before costs/$580 illustrative immediate net; scenario B immediate tax reduction zero; carryforward/lifetime outcomes separate |
| V23 | Import text includes spreadsheet formula/HTML-like payload or oversized/malformed file | Treat as data; safe preview/export, clear rejection where appropriate; no network/execution side effects |
| V24 | Failed import commit, interrupted update, restore from backup | Last valid committed state recoverable; no partial portfolio mutation or erased provenance |
| V25 | Exact-value round trip through import, SQLite, API, TypeScript and analytical transforms | Decimal book values and fractional quantities preserved at declared precision; unsafe float/overflow/coercion rejected; display rounding never rewrites authoritative values |
| V26 | Client/schema mismatch or unexpected API fields | Contract check detects drift; runtime domain validation still rejects semantically invalid plans; generated types alone are insufficient |
| V27 | Approved plan, then a late-recorded backdated correction | Original known-at-approval evidence remains reproducible; corrected state produces separate invalidation/new analysis |
| V28 | Optional AI explanation with missing/conflicting facts or malicious imported text | Only verified tool-returned facts cited; unsupported assertions/unauthorized writes rejected; no AI output directly changes financial state |
| V29 | Optional desktop packaging and compute worker lifecycle | Supported installer, loopback/session boundaries, restart/cancellation, worker failure and private backup/restore qualified before release |
| V30 | Report-date-only position snapshot and same-day acquisition with ambiguous inclusion | Stage ambiguity; do not add the event again or invent a timestamp; reconcile an explicit inclusion boundary before mutation |
| V31 | Proposed replacement buy follows an earlier household loss sale of that security; separate unknown-P&L case | Screen the purchase leg; known conflict blocks, unknown sale outcome stays unresolved; no assumption the earlier sale was a gain |
| V32 | Analysis A starts, an import/settings change creates B, then A finishes late | A remains non-actionable diagnostic evidence; cannot replace/approve against current state; fresh-generation check required |
| V33 | Two windows approve/reserve the same lot; repeated command and same-key/different-payload retry | One atomic reservation succeeds; equivalent retry returns recorded outcome; conflicting retry/oversubscription rejected |
| V34 | Worksheet expires while external order/submission status is unknown | Freshness expires, but shares/cash remain held pending evidence/reconciliation; no implied broker cancellation |
| V35 | Heuristic/timeout produces no candidate; separate exact-model infeasibility proof | Distinct result/reason status; no false proof of infeasibility from search failure; label breached baseline separately |
| V36 | Costs change NAV and rounded orders differ from continuous relaxation | Recompute final cash/NAV/weights/TE and limit residuals; relaxed/fixed-NAV result cannot certify final orders |
| V37 | Partial lot allocations require rounding; fees already embedded in source values | Sum of remaining/sold basis conserved under reviewed allocation method; costs not deducted twice; overflow/excess precision handled explicitly |
| V38 | Database restore succeeds but committed raw/risk evidence is missing; interrupted file publication | Dependent results remain non-actionable; manifest detects missing evidence; staged orphan recovery cannot delete committed files |
| V39 | Common-share security has unqualified special distribution/classification or carried holding period | Do not classify from ticker/acquisition date alone; block affected recommendation until supported evidence/rules exist |
| V40 | Representative already-drifted, DRIP-heavy and small whole-share sleeves | Report valid/blocked candidate yield and baseline breaches without relaxing zero-gain/TE policies; test the adopted D031-D034 policies without treating adoption as demonstrated utility |
| V41 | Local UI starts without network but external asset/telemetry reference exists in its build | Offline acceptance detects unbundled assets/unexpected network access; no private portfolio payloads in URLs/logs/scratch artifacts |
| V42 | Same 100-share sale, basis $10,000, reference and execution price $80; compare $20 versus $30 sell fees | Objective loss $2,000 in both cases; net proceeds $7,980/$7,970, indicative tax loss $2,020/$2,030, costs $20/$30; lower cost wins the objective tie; fees cannot increase reward |
| V43 | 10 shares, basis $900, reference/execution price $100, sell fees $200 | Reference gain $100 blocks sale under zero-positive-gain policy, even though net-proceeds P&L is a $100 loss; no fee-driven gain laundering |
| V44 | Foundation F001 checkpoint includes BUY-001; repeat file and then try F002-F009 variants | Holdings 12 FAAA/5 FBBB, cash $319, NAV $2,399, basis $2,181; do not replay purchase; preserve exact values, stage ambiguous state and reject conflicts/invalid precision as specified |
| V45 | Synthetic $1 total basis over 3 shares, successive 1-share diagnostic allocations | HALF_EVEN to source cent quantum yields $0.33, $0.34, $0.33; total basis conserved; qualified production broker allocation still required |
| V46 | Otherwise eligible portfolio also holds an excluded/uncertain tax-class security | Preserve all holdings/NAV/risk diagnostics; block affected actionable relationships, or entire account plan if dependency impact cannot be bounded; no silent removal |
| V47 | Windows x64 installation, offline UI, interrupted update and recovery on selected supported versions | Record exact OS/browser/runtime/hardware and exercised commands; supported matrix based on observations; no macOS/Linux investor-release claim from portable code |


V04/V05 and any matching/holding-period adjustment case require specialist-reviewed expectations before financial-use claims. Initial PP01/PP06 can block complex cases rather than implementing a complete historical tax engine. Keep diagnostic expectations and supported planner capabilities separate.

V25-V27 support the adopted showcase architecture. V28-V29 apply when optional AI/desktop features progress from evaluation into implementation. The [technology tradeoff review](../architecture/TECHNOLOGY_TRADEOFFS.md) records the adopted pytest/Hypothesis, Playwright, contract-check and metadata-only local diagnostic direction. [T003.1](../tasks/T003.1-development-baseline.md) now qualifies Python tools and four bootstrap checks only; none of V01-V47 is implemented or passed by those toolchain probes. Playwright and application/financial verification remain unrun.

## Invariants and integration checks

- Lot quantities and allocated basis reconcile after supported partial sales; no overselling/reservation duplication.
- Source adjusted basis is preserved unless a recorded authoritative correction supersedes it.
- Committed cash agrees with explicit cash flows and costs, not an unexplained residual plug.
- A repeated or reordered identical input batch yields equivalent committed state within documented event ordering.
- Every actionable order has complete lot/funding/restriction/risk evidence and passes the independent validator.
- A plan is reproducible from its recorded versions and settings, with deterministic tie-breaking.
- Unsupported data cannot disappear during import or be mislabeled as verified.
- Sensitive inputs do not appear in repository fixtures, default logs, URLs, telemetry or public support examples.

Adapter tests must use source-qualified synthetic versions of actual formats, including missing/renamed columns, locale variations and revised downloads. A generic CSV test does not qualify a broker. Performance targets require measured datasets at the proposed 100-stock/2,000-lot/500-universe scale; the provisional qualification targets below are unmeasured and require a recorded reference machine.

## Acceptance ladder

| State | Required evidence | What it does not establish |
| --- | --- | --- |
| Structurally checked | Links, boundaries and documents consistent | Financial behavior or running software |
| Implemented | Identified code/artifacts exist | Tests pass or user accepts |
| Locally verified | Named checks run against identified revision/environment | Independent tax/risk validity or broker qualification |
| Independently reviewed | Reviewer scope/findings recorded and material issues resolved | Guarantee of legal/tax outcomes |
| Paper accepted | Investor completes supported synthetic/shadow workflows | Real-money outcomes or broad broker support |
| Financial-use pilot authorized | Owner names artifact, supported use, limitations and acceptance evidence | Public release or order-API authority |
| Public beta released | Licensed artifact, data/dependency rights, install/security/support scope and explicit release authorization | Production-grade reliability across unsupported cases |

Proposed paper workflows: a clean harvest cycle; a household/DRIP conflict cycle; and partial fills or lot mismatch with recovery. Use representative portfolios, record assistance needed, and do not infer user satisfaction from test completion.

## Review and release package

The [critical review](../reviews/2026-10-22-pre-implementation-review.md) maps findings to these scenarios and G0-G3 readiness checkpoints. V30-V47 are written expectations, not implemented tests. Add representative paper/manual execution and recovery evidence before substantial workflow build-out; record setup/review/lot-selection burden, blocked-candidate rates and measured results against the provisional budgets before claiming usability or capacity.

Use the [review template](../templates/REVIEW_PACKAGE.md). Tax-policy, optimizer and import semantics changes require criterion-level evidence and independently reasoned cases. A source revision, test output, manual script and unresolved limitations must be attributable to the same candidate. Until Git exists, list exact changed file paths and hashes; do not invent a commit ID.

Public release needs license/rights resolution, documented supported tax years and broker workflow, review findings, tested installation/update/restore, privacy-safe diagnostics and rollback instructions. No CI or command is represented as passing until actually configured and run.

## Provisional measurement charter

These are adopted planning targets for an early feasibility exercise, not measured service levels, implicit investor constraints or evidence that the product is usable. Record the dataset, hardware, versions, assistance and timing method; revise targets explicitly if evidence changes the plan.

| Measure | Initial target and experiment | Evidence boundary |
| --- | --- | --- |
| First setup | At most 60 minutes with required supported exports already available | Also record time obtaining exports and unresolved fields separately; do not hide acquisition burden |
| Recurring review/reconciliation | At most 30 minutes for a representative small paper worksheet, with order and lot-selection counts recorded | Measure manual broker steps separately; do not promise brokerage execution latency |
| Exception recovery | At most 30 minutes to understand and reconcile a stipulated partial-fill/wrong-lot paper case | A failure is a workflow finding, never permission to bypass a block |
| Import preview | At most 2 seconds for the 100-stock/2,000-lot target on a recorded reference Windows x64 machine | Measure parsing/validation separately from disk/network export collection; larger inputs require profiling |
| Candidate analysis | At most 30 seconds for the qualified 500-name target problem; progress remains visible | Model and discrete search not yet qualified; timeout may return an honest no-qualified-candidate result |
| Cancellation | UI acknowledges within 1 second; worker computation stops or is isolated within 2 seconds | Canceled/stale result cannot publish actionable state; no worker needed in the foundation slice |

The [foundation brief](FOUNDATION_SPEC.md) is the authoritative written G0 contract. Its current scope does not include candidate analysis, full execution lifecycle or a performance claim. The [brokerage paper charter](../research/BROKERAGES.md) defines the early G1 walkthrough; later observed sessions are still required for paper acceptance.
