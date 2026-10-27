# Benchmark and market-input contract

Current adopted requirements. Implementation/readiness is in [STATUS](../STATUS.md); [remaining tasks](../tasks/REMAINING_WORK_PLAN.md) own delivery. This page incorporates the current outcomes of ADR-0005/0006/0009/0010/0011, including the later numerical and clean-break decisions. No ADR reading is required.

## Exploratory MVP scope

The owner-approved October 27 MVP reset permits exploratory calculations on adequate declared inputs before independent acceptance/calibration is complete. The application has no invented-versus-real data category. Actual mathematical requirements (complete union, correct identity/dates/units, compatible raw OHLC/simple total returns/actions and coherent history) still apply; a label does not qualify a source. No action repair, subset/model fallback or economic-limit relaxation is introduced. The adapter accepts explicit no-action/raw-equals-adjusted inputs or total-return-adjusted inputs with the declared compatible action/OHLC construction. All selected model/profile/numerical checks remain. Financial reliance, calibrated-risk claims, source-use rights and publication retain their applicable gates.

## Standard benchmark selection

The user explicitly selects a supported Vanguard ETF and an actual reported full-portfolio holdings date. VTI and VOO are the initial bounded adapter request list, not default fund selections or a claim of universal issuer support. Fetch through the local backend. The observed advisor latest response identifies its actual latest reported date; historical requests use the requested reported date. Display requested, effective and collection dates separately. Historical as-of access alone proves neither original publication time nor absence of look-ahead.

Use the ETF's complete reported portfolio as the acquisition source. Creation/redemption/PCF baskets are forbidden inputs and fallbacks. A catalog is discovery evidence, not complete portfolio evidence. Missing dates, wrong fund/date, empty responses, throttling, redirects and changed schemas need explicit outcomes; never substitute latest, a neighboring date, an upload, a basket or the previous benchmark silently.

Preserve the original complete response, source/request identifiers, fund identity, collection time, all arrays/rows and material values/unknowns. Verify identity against attributable fund metadata; a source URL alone is insufficient. Reconcile primary versus alternate/duplicate representations before counting economic rows. No array concatenation, silent top-500 truncation or guessed mappings. Acquisition is an observation; review and explicit selection establish the benchmark used by a run.

## Equity-only proxy and weights

Model supported mapped standard equities. Preserve every source row and give unsupported/unmapped holdings explicit exclusion reasons, counts, locators and known excluded values separately from unknown values. ETF units, bonds, derivatives and reserves are outside the modeled portfolio/benchmark. ETF holdings can supply benchmark constituents without making ETF units eligible portfolio holdings. Exclusions do not create modeled or spendable cash.

Let `E` be the sum of original primary USD market values for retained supported mapped equities, counting each retained economic row once. Derive Float64 weights as `marketValue / E`; the derived retained weights sum approximately to one under [ADVISORY_NUMERICS](../engineering/ADVISORY_NUMERICS.md). Preserve published percentages separately, including blanks, rounded totals and contradictions. Do not normalize rounded published percentages or fabricate zeros. The superseded all-primary equity/reserve/derivative denominator is not the modeled denominator; no old diagnostic implementation must be preserved.

Block the affected benchmark result for unqualified fund identity, incomplete/ambiguous row accounting, contradictory included mappings, missing/nonfinite/negative required included values or nonpositive E. Explicitly excluded unsupported instruments do not require derivative models or their own risk histories. Exclusion cannot hide damage affecting retained facts. A mapped equity still needs its separate tax/candidate eligibility and required risk coverage.

Label the result an **equity-only disclosed-holdings proxy**. It is neither an exact index feed nor full-fund/ETF NAV-return replication. No source weight difference can silently become cash or a financial-readiness claim.

An observed zero included value is distinct from unknown. Zero-weight consumer/history treatment still needs explicit qualification; do not silently delete retained rows to bypass coverage or numerical requirements.

## Secondary files and permissions

Explicit custom/manual benchmark files, including qualified Vanguard/iShares exports, remain an accepted secondary direction. They are optional for initial standard-route v1 and cannot be a silent acquisition fallback. The previously supplied workbook has no default status. Supported schemas/units/dates and disclosures must qualify when that adapter is implemented. Automated fixtures/examples are fictional and offline by default; privately retained references must not enter source, screenshots or AI payloads.

The owner attested BlackRock/Vanguard permission for automated holdings downloads and specifically validated Vanguard noncommercial use. Do not ask again within that scope. These are owner attestations, not an agent-inspected redistribution/commercial grant. History, current quotes, taxonomy and fund identity require their own qualified source/convention/permission scope. Research yfinance evidence is not production-provider adoption. No broker-account or private-portfolio access is implied.

## History, current marks and classifications

History must cover the retained modeled held/benchmark/candidate union in explicit security/session order. Keep provider/dataset, resolved identity and dated symbol mapping, USD units, interval, calendar/timezone, adjustment/action/repair conventions, relevant transform versions and permission scope. Current reference quotes, holdings-date marks, raw OHLC, adjusted history and derived returns have different uses.

Reuse compatible locally retained history across sessions. Plan missing leading/interior/tail intervals and new names; request only necessary data plus qualified overlap/predecessors. Record requested, received and usable coverage separately. Holidays need calendar evidence; missing rows are not zero returns. A latest date is not a coverage proof.

Overlap/action/vintage discrepancies require a qualified coherent reconstruction or targeted refetch/revalidation of the affected full required window. An unchanged overlap cannot prove older history unchanged. No blind mixed-vintage append, automatic price repair, invented proxies, future leakage or missing-name deletion. Preserve useful partial diagnostics and block only dependent risk/suggestions.

Manual selected-name and full-required-window refresh are v1 controls. Background scheduling, timers and startup catch-up are deferred. Show actual cutoff, successful refresh/validation scope and unresolved gaps; a tail refresh is not full-window validation. Offline data retains its dates and cannot masquerade as current quotes.

Retain the input data actually used by saved current-format runs plus chosen reusable cache. Refresh creates new observations/results and does not rewrite saved output. Required run inputs are current user work; rebuildable cache loss may require refetch or explicit unavailability. Retention/deletion is explicit and respects rights, without a general proof registry or silent purge.

Classifications use a permitted attributable sector/industry/security mapping with source/version/as-of, corrections and unknowns. Do not call a taxonomy GICS/BICS without evidence or treat current mappings as point-in-time history. Missing classification blocks its applicable constrained result; it cannot silently disappear or become zero exposure.
