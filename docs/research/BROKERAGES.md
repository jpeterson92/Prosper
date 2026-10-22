# Brokerage feasibility

Status: public-documentation reconnaissance checked October 22, 2026. No brokerage account was accessed, export downloaded, developer access requested or API tested. The user has chosen a broker-neutral file/manual starting workflow.

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
| Open tax lots | Acquisition dates, exact quantities, total adjusted basis, basis/holding-period status, distinguishable lot references | No actionable specific-lot plans |
| Position and cash snapshots | Same-cutoff holdings, settled/available/unsettled cash definitions | Reconciliation/funding blocked |
| Historical/recent activity | Buys, sells, DRIPs, external transfers, corrections and actions, with dates/IDs and coverage | Explicit history/eligibility gaps |
| Existing wash adjustments | Meaning of adjusted versus original basis and holding-period fields | No inferred basis; review required |
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

The first pilot persona is adopted under D031: an investor with an existing eligible stock sleeve and sufficient source/household evidence. This charter is prepared; no participant or broker session has run. Use fictional data and public/source-qualified schemas first. Real exports, credentials, outreach and account operations require their relevant authorization.

| Paper case | Exercise | Record before declaring G1 passed |
| --- | --- | --- |
| Clean cycle | Assemble lots, same-cutoff positions/cash, included activity, permitted quotes/benchmark/history; select exact lots on a paper worksheet and map confirmations | Field/source/version coverage, cutoff and settlement meanings, rights/refresh plan, acknowledgement deadline/timezone, quantities/fees and confirmed lot identifiers |
| Household/DRIP conflict | Add a recent household purchase and an earlier household loss sale affecting the proposed replacement | Both legs screened; blocked reason and missing evidence understandable; no manual bypass masquerading as a clean plan |
| Partial execution | Sell only part of a worksheet and stipulate failed replacement; then a separate wrong-lot confirmation | Actual quantities/cash and exposure recovery, uncertain commitments retained, lot mismatch unresolved until evidence arrives |
| Ineligible or drifted sleeve | Use unsupported tax facts or an initial breach for which strict zero-gain/whole-share constraints yield no qualified candidate | Diagnostic holdings preserved, honest search outcome, burden/candidate-yield recorded; no silent risk/gain relaxation |

Record setup/import/review/lot-selection/reconciliation and recovery time, assistance, manual order count, blocked reasons and unresolved source fields. Apply the provisional [measurement charter](../engineering/VALIDATION.md). G1 requires a qualified mapping and completed paper walkthrough with material gaps dispositioned; a filled template or public feature list alone does not pass it. Independent review and observed investor acceptance remain later requirements.
