# Decision and open-choice index

Current authority locator, October 26, 2026. Adopted behavior is incorporated in the direct documents below; read the affected contract instead of an ADR/supersession chain. Approval of direction is not implementation, independent review, data qualification or release authority. Earlier rationale and owner statements are recoverable with `git show 69f8cba299b7d130a87684809df77fe124b8fe5d:<path>`; no separate archive or historical ADR files are maintained.

## Adopted decisions

| IDs | Current adopted outcome | Direct owner |
| --- | --- | --- |
| D001-D003, D005-D007, D019, D031, D035 | Open-source goal; local existing-stock-sleeve advisory tool, file/manual Fidelity starting workflow, U.S./USD/taxable/whole-share scope, Windows x64; learning value | [Product](product/SPEC.md), [plan](PROJECT_PLAN.md) |
| D004 | Historical planning authority only; each current request governs scope | [AGENTS](../AGENTS.md) |
| D008, D020-D021, D025, D028, D037 | Python/SQLite/React/FastAPI/generated client; Polars, Float64/small decimal boundary; current records/security/recovery; normal local locked development | [Architecture](architecture/ARCHITECTURE.md), [records](architecture/DATA_CONTRACTS.md), [numerics](engineering/ADVISORY_NUMERICS.md), [development](engineering/DEVELOPMENT.md) |
| D009, D015, D034, D038 | Avoid known conflicts; supported ordinary tax cases; holdings-first/conditional-history/manual restrictions; independent tax/model review before financial use | [Tax](domain/TAX_POLICY.md), [product](product/SPEC.md), [acceptance](engineering/VALIDATION.md) |
| D011, D039-D040, D044-D045 | Vanguard complete reported portfolio selection; retained-equity value/E proxy; explicit exclusions; selected-cash/final-target distinction; compatible retained history/manual refresh. D044 all-primary denominator is superseded for modeling | [Market inputs](domain/BENCHMARK_INPUTS.md), [portfolio](domain/PORTFOLIO_CONSTRUCTION.md) |
| D013, D022, D032-D033 | Eligible reference-price loss objective, zero positive gains, strict explicit limits; CVXPY/Clarabel continuous reference; separately qualified discrete construction and independent final validation | [Portfolio](domain/PORTFOLIO_CONSTRUCTION.md) |
| D023-D024, D026, D029-D030 | Focused reference research; bounded optional learning reserve; later Tauri/AI/showcase and broad-model experiments cannot block core v1 | [Plan](PROJECT_PLAN.md#outside-the-v1-critical-path) |
| D036, D043 | One fitting task per direct next; concrete-only splitting; local synthetic work can precede G1 without bypassing dependent real-use gates | [NEXT_STEP](engineering/NEXT_STEP.md), [acceptance](engineering/VALIDATION.md) |
| D041-D042 | Python IDR/OHLC DCC-NL target, analytical nonlinear shrinkage, one covariance/industry framework; reference rights owner-cleared, no investor MATLAB/MEX | [Risk](domain/RISK_MODEL.md) |
| D046-D047 | Proportional advisory scope; no execution/scheduling platform or backward compatibility; keep material current financial/security/recovery checks | [Product](product/SPEC.md), [architecture](architecture/ARCHITECTURE.md), [AGENTS](../AGENTS.md) |
| D048 | Owner-requested direct-document consolidation and v1 outcome backlog; cleanup/recovery travel with consumers, no archives, final optimizer-selected calibration follows candidates | [Plan](PROJECT_PLAN.md), [remaining work](tasks/REMAINING_WORK_PLAN.md) |
| D049 | Personal local research first remains selected. The October 27 approved MVP reset replaces mode isolation with one chosen local workspace and one input contract without data-origin categories; actual private access/disclosure, financial reliance and publication retain applicable authority | [Personal research milestone](tasks/REMAINING_WORK_PLAN.md#t011221---personal-research-runtime-separation), [STATUS](STATUS.md) |

D048 changes planning/context, not the selected risk/tax method, investor defaults, provider/license commitments or financial acceptance. Its authority is the owner's October 25 comprehensive optimization/compaction request and explicit direction to rely on Git history. The pre-compaction checkpoint commit is separately owner-authorized; it does not authorize push or application cleanup.

October 27 owner instruction "Please implement all suggested changes" adopts the [MVP review](reviews/2026-10-27-mvp-scope-review.md): one local workspace, source provenance without data-category fields or label-based execution barriers, input diagnostics then exploratory model/worksheet use, observed improvements, proportional verification, and deferred generic capacity/release/optional work. The selected risk methodology and all enabled economic caps remain unchanged. This does not name actual private files or authorize trading/publication.

October 27 follow-up: the owner explicitly removed all application distinctions between synthetic and nonsynthetic inputs. Required source bytes/dates/provider/identity/conventions remain. Fictitious brokerage accounts and generated market data are test practices, not runtime metadata or product modes.

## Open choices

| IDs | Actual unresolved choice/evidence | Resolve with / when |
| --- | --- | --- |
| D010 | Supported source/broker lot-selection/funding assumptions and actual manual worksheet feasibility | T005.1/T010.1 source-shaped cases and observed authorized workflow; no full fill reconstruction prerequisite |
| D012 | Risk data/model profile, discrete method and explicit investor risk/cost/order/turnover/notional/economic limits | T006.1.6/T006.2.4/T007.1 evidence; no invented investor defaults or solver adoption |
| D014 | Code license, copyright/contribution terms; unrelated dependency/data rights | Check before commitments; T011.2 final rights handoff |
| D016 | Legal/service/distribution scope for actual external use | Qualified advice for the concrete model before external pilot/public release |
| D017 | Supported tax years, freshness/lookback/horizon/short-history rules and measured supported workload | Source/model/candidate evidence and owner disposition, before applicable real/validated use |
| D018 | Packaging/support/name/public-distribution details and final release authority | Named Windows candidate and concrete T011.2 handoff; no automatic publication |
| D027 | First optional bounded learning track | Owner-selected later question; no core v1 blocker |

## ADR incorporation map

All thirteen former ADRs have current direct homes. Their deleted original paths are visible at the checkpoint; current agents need no historical file to apply adopted guidance.

| ADR | Current direct requirements | Superseded clauses removed |
| --- | --- | --- |
| 0001 architecture/showcase | [Architecture](architecture/ARCHITECTURE.md), [plan](PROJECT_PLAN.md) | Old exactness/event-ledger/runtime workarounds and former EWMA production suggestion |
| 0002 review actions | [Product](product/SPEC.md), [portfolio](domain/PORTFOLIO_CONSTRUCTION.md), [tax](domain/TAX_POLICY.md), [acceptance](engineering/VALIDATION.md) | Execution/reservation/reconciliation loop as v1 dependency |
| 0003 local development | [Development](engineering/DEVELOPMENT.md), [architecture](architecture/ARCHITECTURE.md) | Google Drive/external-environment restrictions; routine manifest coupling is queued tooling cleanup |
| 0004 holdings/history/cash | [Product workflow](product/SPEC.md#investor-workflow), [portfolio cash](domain/PORTFOLIO_CONSTRUCTION.md#objective-cost-and-cash-semantics), [tax](domain/TAX_POLICY.md) | Mandatory complete history/cash/independent positions, execution monitoring/reservations |
| 0005 files | [Secondary files/permission](domain/BENCHMARK_INPUTS.md#secondary-files-and-permissions) | Supplied workbook/default-file assumption |
| 0006 history cache | [History/marks/classifications](domain/BENCHMARK_INPUTS.md#history-current-marks-and-classifications), [records](architecture/DATA_CONTRACTS.md) | Background scheduling and general proof/registry lifecycle |
| 0007 risk method | [RISK_MODEL](domain/RISK_MODEL.md) | Unqualified hybrids/fallbacks; cross-version replay guarantees |
| 0008 Python risk | [RISK_MODEL](domain/RISK_MODEL.md#selected-method-and-implementation) | Mandatory investor MATLAB/MEX and reopened settled reference-rights blocker |
| 0009 Vanguard route | [Standard selection](domain/BENCHMARK_INPUTS.md#standard-benchmark-selection) | Basket/date/source fallback and manual-file default |
| 0010 value weights | [Equity proxy](domain/BENCHMARK_INPUTS.md#equity-only-proxy-and-weights) | All-primary modeled denominator; universal rational transport |
| 0011 equity/cash target | [Equity proxy](domain/BENCHMARK_INPUTS.md#equity-only-proxy-and-weights), [portfolio](domain/PORTFOLIO_CONSTRUCTION.md) | Unsupported instrument modeling, synthetic exclusion cash and implicit target relaxation |
| 0012 proportional advisory | [Product](product/SPEC.md), [numerics](engineering/ADVISORY_NUMERICS.md), [records](architecture/DATA_CONTRACTS.md), [plan](PROJECT_PLAN.md) | Old intermediate proofs/execution platform and required compatibility bridges |
| 0013 unreleased clean break | [AGENTS](../AGENTS.md#engineering-defaults), [architecture recovery](architecture/ARCHITECTURE.md#development-and-recovery) | Legacy readers/migrations/old-backup/API preservation obligations |

## Source authority and evidence boundaries

The owner attested automated BlackRock/Vanguard holdings-download permission and Vanguard noncommercial use, and independently cleared the selected risk reference-package rights concern. Use those settled scopes without asking again; they do not grant redistribution/commercial rights, private portfolio access, unrelated histories/quotes/taxonomies or financial-use acceptance. [Market inputs](domain/BENCHMARK_INPUTS.md#secondary-files-and-permissions) and [risk](domain/RISK_MODEL.md#selected-method-and-implementation) contain these facts directly. Research/source findings retain their named dates/limits; source qualification tasks verify current facts before integration.

New consequential decisions should update their direct owning contract and add a concise dated index entry only when useful. Do not append repeated supersession prose or create another mandatory ADR series. Never mark an unresolved choice accepted on the owner's behalf.
