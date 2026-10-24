# Brokerage feasibility

Status: the owner selected **Fidelity as the initial broker test case on October 23, 2026**. [T002.1's current public evidence matrix](../tasks/T002.1-public-broker-evidence.md) owns the dated field/capability findings, source conflicts and next missing input. Broker selection is settled; the precise export/manual workflow remains unqualified under D010. [T002.2.2 opening-source evidence](../tasks/T002.2.2-opening-source-disposition.md) and [T002.2.3 manual-workflow evidence](../tasks/T002.2.3-manual-workflow-disposition.md) now own the subsequent bounded public dispositions, preserving actual account/source/funding gaps and conflicting correction instructions. No brokerage account was accessed, real export downloaded, developer access requested or API tested. The generic import architecture remains broker neutral with file imports and manual trades.

The comparison table below preserves the October 22 reconnaissance, with limited public alternative checks during T002.1. It is not the current selection queue. The owner subsequently supplied a combined ETF/mutual-fund lot example and collection prompt, authorizing the same overall stock structure as a development assumption. [T002.2 fixture preparation](../tasks/T002.2-fidelity-fixture-preparation.md) now supplies fictional CSVs and [future-user collection instructions](../guides/FIDELITY_IMPORT.md). In the owner's reported retail positions workflow, there is no single bulk lot download across accounts; the prompt collects per-position source CSVs and consolidates them without changing lot values. This is an observed-workflow report, not an assertion about every Fidelity channel. Original downloads/browser coverage and stock-output fidelity were not qualified here. Stable lot IDs, basis/holding adjustments, cutoffs, cash/history and confirmation formats remain unresolved. Do not access the owner's account to fill those gaps.

## Selection principle

Choose the first broker based on **reliable tax-lot and activity evidence plus specific-lot execution/confirmation**, not on API availability. A position endpoint with aggregate basis is not sufficient. The initial canonical importer should function with synthetic data before any broker adapter is implemented.

| Candidate | Public evidence observed | What that evidence does not establish | Qualification priority |
| --- | --- | --- | --- |
| Interactive Brokers | Open Positions Flex reference documents Summary/Lot detail, cost-basis fields, open timestamps and wash-related holding-period fields. [IBKR reporting reference](https://www.ibkrguides.com/reportingreference/reportguide/open%20positionsfq.htm) | A chosen query's complete coverage, historical adjustments, corporate actions, cross-account activity, or a verified manual specific-lot workflow for this product | Promising structured-export candidate; obtain a synthetic equivalent of an actual export schema and qualify complete bundle |
| Fidelity | Trader+ Desktop guide documents position CSV export and adjusted wash-sale display. [Fidelity positions guide](https://www.fidelity.com/trading/trader-desktop-user-guide/positions) | That a positions CSV includes individual lots, usable stable lot IDs, adjusted holding dates, or all required activity; current retail API availability was not established | Qualify lots/history separately; do not claim a position export is a complete lot export |
| Charles Schwab | Official portal describes individual-developer Trader API access for existing brokerage accounts and access-request steps. [Individual developer guide](https://developer.schwab.com/user-guides/individual-developer/become-individual-developer), [portal guides](https://developer.schwab.com/user-guides) | Approved access for this user, tax-lot API fields, historical basis, paper environment behavior or lot-specific order support | Qualify file/manual workflow first; API investigation later if useful |

Portal content can depend on authentication and change. Schwab's page was available in indexed official documentation; the unauthenticated page body did not render through the text retrieval tool. No authenticated capability is inferred.

## T002 qualification checklist

Complete one evidence sheet per candidate using public documentation and redacted/synthetic schemas. Real account review requires separate authorization and a private data location. Never ask for brokerage passwords.

| Requirement | Pass evidence | If absent |
| --- | --- | --- |
| Open tax lots | Exact quantities, reported total basis, resolvable security and distinguishable sale lots; preserve date/term and basis assumptions | Missing basis/ambiguous sale mapping blocks affected sales; unknown term remains unknown under D038 |
| Position and cash snapshots | Optional independent positions and cash buckets with as-of definitions; derive holdings from lots when needed | Missing redundant export alone is not a blocker under D038-D039; actual discrepancies and insufficient funding still require resolution |
| Historical/recent activity | Optional buys/sells/DRIPs/actions with coverage, or attributable manual restrictions | Persistent unverified-wash-sale warning and conditional results under D038; known conflicts still excluded |
| Existing wash adjustments | Preserve source-reported total basis and supplied adjustment/holding fields | Absence of a wash-validation flag does not invalidate ordinary source basis; known disputes/events need resolution, missing basis cannot be inferred |
| Fractional holdings | Quantity precision and broker's whole/fractional sell behavior | Preserve holdings; block unsupported order sizes |
| Specific-lot manual selection | Documented procedure and evidence of broker acknowledgement/confirmation | Initial execution workflow fails qualification |
| Fills and lot allocations | Actual prices/fees, partial fills/cancellations, confirmed sale lots | Trade cycle cannot be marked reconciled |
| Export stability | Format/version, date/decimal conventions, stable IDs or supported disambiguation | Adapter versioned; unsupported variants rejected |
| Funding constraints | Account cash availability and sequencing supported by broker documents | No assumed same-session reinvestment of proceeds |
| Terms and data rights | User's export access/use permissions and any redistribution constraints | No shipping broker data or unapproved access method |

The first qualified workflow can be partly manual, including reviewed mapping and confirmation import. It must state exactly what is supported. Do not introduce scraping, credential collection or unofficial access just to avoid an export gap.

The critical review requires this paper qualification before substantial broker-facing/optimizer build-out (G1), not only before release. Include deadline/timezone and acknowledgement evidence for the investor's actual account workflow. IBKR publicly documents a Specific Lot matching interface and a remaining-time display; that is further evidence to investigate, not a selected broker or a verified user session. [IBKR Tax Optimizer window](https://www.ibkrguides.com/traderworkstation/the-tax-optimizer-window.htm). Walk through a partial fill, failed replacement and wrong-lot confirmation using synthetic evidence; record manual burden and unresolved steps.

## Later integrations

Read-only connectivity is a later feature with scoped tokens, revocation, stale-data handling, deduplication and the same canonical contracts. Trading access is a separate product and safety decision requiring plan binding, exact lot selection, idempotency, authorization, partial-fill recovery and reconciliation. It is not automatically the next milestone after read-only access.

## T017 / G1 paper feasibility charter

The first pilot persona is adopted under D031: an investor with an existing eligible stock sleeve and sufficient source/household evidence. [T017.2](../tasks/T017.2-manual-execution-rehearsal.md) now completes a fictional paper exception walk with independent arithmetic and an explicit G1 gap disposition. No participant or broker session has run. Use fictional data and public/source-qualified schemas first. Real exports, credentials, outreach and account operations require their relevant authorization.

| Paper case | Exercise | Record before declaring G1 passed |
| --- | --- | --- |
| Holdings-first conditional cycle | Assemble lot snapshot plus account/as-of/security supplements, optional history/manual restrictions and selected cash, permitted quotes/benchmark/market history; select exact lots on a paper worksheet and map manual/file confirmations | Evidence/assumptions separate, unverified-history warning retained, selected-cash sleeve scope, cutoff/settlement/rights/refresh, quantities/fees and confirmed lot mapping |
| Household/DRIP conflict | Add a recent household purchase and an earlier household loss sale affecting the proposed replacement | Both legs screened; blocked reason and missing evidence understandable; no manual bypass masquerading as a clean plan |
| Partial execution | Sell only part of a worksheet and stipulate failed replacement; then a separate wrong-lot confirmation | Actual quantities/cash and exposure recovery, uncertain commitments retained, lot mismatch unresolved until evidence arrives |
| Ineligible or drifted sleeve | Use unsupported tax facts or an initial breach for which strict zero-gain/whole-share constraints yield no qualified candidate | Diagnostic holdings preserved, honest search outcome, burden/candidate-yield recorded; no silent risk/gain relaxation |

Record setup/import/review/lot-selection/reconciliation and recovery time, assistance, manual order count, blocked reasons and unresolved source fields. Apply the provisional [measurement charter](../engineering/VALIDATION.md). G1 requires a qualified mapping and completed paper walkthrough with material gaps dispositioned; a filled template or public feature list alone does not pass it. Independent review and observed investor acceptance remain later requirements.
