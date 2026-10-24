# ADR-0005: Adopt user-file benchmarks and the supplied testing default

Date: October 23, 2026. Status: **Accepted by the project owner** through explicit follow-up direction. Refines D011; no new dependency, provider subscription or application implementation is selected.

## Question and context

How will testing obtain benchmark weights, and what eventual upload route should Prosper support? The owner directed that a user-provided file similar to the previously supplied workbook be assumed available, that the supplied file serve as the default for the duration of testing, and that future uploads support Vanguard or iShares ETF holdings downloaded by the user. The [feasibility report](../../tasks/T017.1-pilot-data-feasibility.md#delivered-development-inputs) records the retained workbook/normalized companion and their provenance. The [market-data comparison](../../tasks/T017.1-market-data-comparison.md) distinguishes basket weights from quotes and adjusted history.

Alternatives considered were a paid benchmark/constituent provider, an exclusively fictional testing basket, or user-supplied weighted holdings. The owner selected the user-file route; paid benchmark-provider selection is unnecessary for this testing scope.

## Decision and consequences

- **Default input route:** assume the user supplies a weighted benchmark file comparable to the supplied example. For the duration of local testing, designate the retained `US_Total_Market_Index.xlsx` under ignored `.local/reference-data/us-total-market-2026-10-22/` as the default benchmark source; its `normalized-holdings.csv` is the existing text-preserving companion. This supersedes earlier recommendations that only the fictional basket be the testing default. It does not claim an implemented loader or that the current synthetic screen accepts this workbook.
- **Future product direction:** support user-uploaded Vanguard and iShares ETF holdings files downloaded by the user. This is an accepted upload direction; exact supported export versions, column mappings and adapter behavior remain to qualify in T006.1 or a bounded child. Prosper need not fetch issuer files or subscribe to a benchmark feed for this route.
- **Meaning:** treat the selected fund's supplied holdings/weights as a disclosed ETF-holdings benchmark proxy. Preserve the fund/source name, source file identity, effective holdings date, collection/import time and original values. Do not label it an authenticated exact index constituent feed. This accepts the owner's approximation for the input route without claiming measured tracking fidelity.
- **Transformations:** retain original rows and weights. Do not silently select the largest 500 names, remove cash/futures/unsupported or unresolved rows, or renormalize. Any modeled subset, exclusion, residual treatment or weight transformation must be explicit and reviewed before dependent risk results. This decision selects no such transformation and does not qualify a larger universe than the existing scale target.
- **Boundaries:** the supplied market-reference file stays local and outside authored source, fixtures, screenshots and chat payloads. Existing invented fixtures remain the reproducible source-controlled test/example inputs. Local testing may use the owner-designated reference; this is not permission to distribute its contents or send it to an AI/vendor. Financial-use/source-rights qualification remains separate. Benchmark marks do not replace qualified quotes or adjusted risk history.

## Subsequent owner permission for automated holdings downloads

On October 23 PDT / October 24 UTC, 2026, the owner attested permission from BlackRock and Vanguard for Prosper to automate holdings-file downloads. This supplements the user-download/upload route and resolves the acquisition-authority blocker for the bounded local T017.1.1 public-file qualification; the [resumed evidence](../../tasks/T017.1.1-public-membership-qualification.md#owner-permission-and-resumed-qualification) records exact scope and one official ITOT result. The supplied testing-default file is unchanged. Permission is owner-attested, not an independently inspected grant; do not infer redistribution/commercial rights, an implemented production download adapter, Vanguard format qualification or changed benchmark weight policy. Do not request the same permission again within the recorded use.

## Acceptance evidence and reconsideration

The owner's explicit direction settles the testing assumption/default and future upload scope. Documentation consistency/link/manifest checks qualify only that recorded decision. No importer, upload screen, normalization rule, provider integration, benchmark risk calculation or financial-use qualification is implemented by this request. G1-G3 and independent review remain separate.

Future implementation must verify raw/source-value retention, correct effective versus import dates, distinct fund/proxy labels, explicit unknown security/row dispositions, disclosed weight reconciliation and reproducible selected-basket identity. Written cases include an unchanged valid file; a missing identifier/weight/as-of fact; non-equity rows; a non-unit weight sum; a file exceeding the qualified scale; and a replacement file creating a new frozen benchmark version. These are acceptance requirements, not executed tests.

Reconsider if the owner changes the testing benchmark, an issuer export cannot provide required identities/weights, the chosen proxy is unsuitable for the intended exposure comparison, or permitted use/scale requires a different route. Actual issuer formats and entitlements must be checked when their adapters/use are qualified; none is asserted from this policy record.
