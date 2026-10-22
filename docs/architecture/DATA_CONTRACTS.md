# Data-contract framework

Status: conceptual semantics adopted as part of the October 22, 2026 project baseline. These tables are not implemented schemas or public API compatibility promises. T001-T004 will qualify precise formats/fields and turn accepted semantics into versioned schemas and synthetic fixtures.

## Shared conventions

- Include schema version, source/provider, source record reference, import batch ID, effective/as-of timestamp and ingestion timestamp. Record timezone where meaningful; a tax trade date is a date, not an arbitrary UTC conversion.
- Encode book money and quantities as exact decimal values, not binary floats. Currency is explicit. Quantity precision follows evidence, including fractions, even where proposed orders are whole shares.
- Unknown values are explicit and accompanied by a reason. Zero is a known value, not an unknown sentinel. An absent file is not an empty account.
- Each record belongs to a household/profile and account scope where applicable. Use aliases in reports; do not expose full account numbers by default.
- Preserve source evidence outside the repository. Hashes identify inputs locally but do not make sensitive portfolio records safe to publish.
- Schema changes require compatibility/migration decisions and fixtures. Historical plan inputs remain interpretable after updates.
- Preserve effective time and recorded/known time for corrections and evidence; do not rewrite what an earlier approved plan knew.
- For the adopted SQLite backend, use canonical decimal strings stored in TEXT under the [foundation specification](../engineering/FOUNDATION_SPEC.md) and test exact round trips; SQL numeric affinity/ORM types cannot be assumed to preserve precision. API book values use validated decimal strings, with deliberate conversions for chart/risk floats. Parquet/dataframe/NumPy paths require explicit schema/cast tests.
- Before persisting/computing a supported field, define its precision, scale/bounds, excess-precision behavior, rounding stage and allocation-residual rule. Supported partial sales must conserve lot basis under the reviewed method; costs embedded in source basis/prices cannot be counted twice.

## Records

These are logical responsibilities, not a requirement for one database table/class per row or an instruction to implement every abstraction in the first slice. Use the minimum concrete representation needed to satisfy the slice's invariants; preserve the stated semantics across representations.

| Record | Required conceptual fields | Key validation and meaning |
| --- | --- | --- |
| AccountProfile | Internal account ID, alias, broker/source, owner/relationship, taxable/IRA/Roth/other/unknown, currency, traded/monitor-only, lot-method capability | One traded account initially; uncertain relationship is not inferred from alias |
| Security | Internal stable ID, type, issuer/share-class IDs, currency, ticker aliases with dates, external IDs and source | Ticker alone cannot define identity; unknown supported status blocks affected plans |
| SecurityRelation | Two security IDs, identity/restriction type, status, rationale/source, reviewer, effective period, policy version | Separate tax relationship from risk similarity; unknown is preserved |
| ImportBatch | ID, file hashes, source type/version, as-of/coverage interval, row counts, validation results, commit status, superseded batch | Same file replay is idempotent; overlapping changed files need record-level matching |
| OpenLotSnapshot | Account, lot ID/source lot reference, security, remaining quantity, acquisition date, holding-period evidence, total adjusted basis, currency, basis status and included adjustment metadata, snapshot cutoff | Total basis versus per-share basis must be explicit; preserve source adjustments; missing date/basis blocks sale |
| PositionCashSnapshot | Account/security quantity, market valuation timestamp, cash by currency, available-to-trade/settled/unsettled amounts, snapshot cutoff | Position quantities reconcile to lots; cash buckets are not interchangeable |
| ActivityEvent | Source event ID or reviewed dedup key, account/security, type, trade date/time, settlement date, quantity, gross/net proceeds, fees, cash movement, correction/supersession and lot links | Purchases, sales, DRIPs, transfers, dividends, actions, cancellations; unknown type cannot be silently ignored |
| CoverageStatement | Account/relationship, inclusive covered dates, data or attestation, activity types covered, known automation, verification date, expiry, unresolved gaps | Coverage can be complete, partial, unknown or contradictory; a static declaration never proves future absence |
| BenchmarkSnapshot | Basket ID/name, as-of/effective dates, security weights, cash definition, source/usage rights | Sum of weights and identity coverage validated; no implicit missing-name renormalization |
| QuoteSnapshot | Security, price, currency, timestamp, price type/session, source, adjustment convention | Execution price and historical adjusted close are distinct fields/uses |
| RiskModelSnapshot | Universe ordered by stable ID, covariance or factors, units/frequency/annualization, estimation window, data cutoff, missingness policy, version/quality evidence | PSD, order alignment and full holdings/benchmark/candidate coverage checked |
| InvestorConstraints | Version, cash floor, TE/security/sector caps, restricted names, whole-share policy, trade-count/notional/turnover limits, gain/cost budgets, expiry settings | Explicit values in plan; no documentation examples become implicit defaults |
| HarvestPlan | ID/version/hash, input-version references, objective/rule/model versions, baseline, candidate trades, reason codes, estimates, assumptions, validation results, expiry and status | Immutable once validated/approved; invalidating facts generate a new candidate |
| ProposedTrade | Plan ID, security, side, quantity, sell-lot allocations, indicative price, cost estimate, funding/dependency notes, reasons | Aggregate position does not replace exact sell-lot mapping |
| ExecutionEvidence | Account, order/fill IDs, actual security/side/quantity/price/fees/times, cancellation state, broker-confirmed lot allocations, source references | Intent, order, fill and tax-lot confirmation are separate records; mismatch stays unresolved |
| Restriction | Security/relation group, start/end tax dates, source sale/activity, affected account scope, provisional/resolved status and rule version | Derive from actual events; carry open windows across years |
| ReconciliationResult | Prior/new snapshot refs, matched events/lots, position/cash/basis differences, tolerances, reviewer disposition | No automatic replacement of unknowns with zero or unexplained balancing entries |
| AuditEvent | Local event ID/time, action, referenced record versions, actor category, outcome | Avoid raw financial payloads/secrets in general diagnostics; audit detail remains private |
| SnapshotBoundary | Source as-of, timezone/session, trade-date/settled/closing convention, included event/sequence evidence and reconciliation status | A report date alone cannot resolve same-day event inclusion; ambiguous evidence stays staged |
| ReadinessAssessment | Component, dependency scope, complete/partial/unknown/contradictory status, reason codes, evidence and remediation | Unknowns block their proven impact scope; unbounded impact blocks the account plan |
| AnalysisRun | Run ID, frozen input-bundle hash/version refs, state generation, computation version/settings, requested/started/completed times, canceled/stale status | Worker output cannot become actionable if relevant current generations changed |
| AnalysisResult | Run ID, candidate/baseline refs, exact model/solver status, feasibility evidence, residuals, search limits and actionability | Separate no-candidate-found from proven infeasibility; baseline may itself be outside limits |
| MutationReceipt | Command/idempotency key, payload hash, expected generation, outcome and referenced plan/reservation | Same-key retries cannot duplicate state changes or accept a different payload |
| ExecutionCommitment | Plan/order references, reserved lots/cash, investor report of submitted/not submitted/unknown state, reconciliation evidence | Recommendation expiry alone cannot release uncertain external commitments |
| RecoveryManifest | Schema/app versions, database backup identity, authoritative file hashes/references, cache classification and restore checks | Restore required evidence as well as SQLite; missing committed references invalidate dependent results |

## Snapshot and event reconciliation

An opening snapshot at cutoff C represents holdings/cash already inclusive of its stated source activity. Events on or before C inform tax screening but are not applied again to current holdings. Events after C are applied only under defined completeness and date-order semantics. A later snapshot is a reconciliation checkpoint, not a second inflow of all existing assets.

The adapter must establish the inclusion boundary, including unsettled and same-day events. A file's report date is not a substitute for a known economic cutoff or transaction sequence. Where inclusion cannot be determined, stage the records and reconcile before state mutation. Keep hypothetical/scenario trades outside committed actual events. Earlier household loss sales must carry their known P&L or an explicit unknown outcome so replacement-buy screening does not assume every prior sale was a gain.

Source transaction IDs are preferred for event deduplication. A fallback composite key can collide for identical same-day trades; require deterministic disambiguation evidence or manual resolution. File hashes alone cannot deduplicate overlapping downloads. Do not merge two lots just because acquisition date, ticker and price coincide.

Corrections to imported basis retain old and new evidence with a supersession link. Existing broker wash adjustments are already part of adjusted basis when the source says so; never add the same adjustment from activity a second time. The initial product records newly detected conflicts for review rather than maintaining an unqualified full historical basis engine.

## Time semantics

Maintain at least: source as-of, event trade date/time, settlement date, imported-at, analysis-as-of, approval-at, actual-fill date/time and monitoring-through. A fresh download of an old snapshot is still stale economic information. A January import may change the modeled tax outcome of a December sale. Coverage and restrictions therefore cannot be truncated at the tax-year boundary.

Before generating a plan, determine that all relevant state is aligned to an accepted analysis cutoff, then record differences rather than pretending all sources were captured simultaneously.

## Generic import bundle

The first synthetic inspection bundle uses the adopted `synthetic-checkpoint-v1` single UTF-8 JSON object in the [foundation specification](../engineering/FOUNDATION_SPEC.md): typed metadata/record arrays, decimal strings, explicit unknown reasons and checkpoint/activity inclusion. Benchmark and risk inputs are not required for that inspection-only slice. T003/T004 child work will qualify concrete field schemas and materialize synthetic fixtures against those accepted semantics; it must not treat the initial transport as an open CSV-versus-JSON decision. Later broker CSV/XML or other adapters map into versioned canonical contracts and require separate qualification. No spreadsheet dependency is required for users, and no sample containing real account information belongs in source.

An import preview must show required fields, detected units, unsupported values, coverage and exact error rows. The user can repair a mapping, not silently override financial validation. Schema and synthetic bundle examples become executable contracts only during authorized implementation.
