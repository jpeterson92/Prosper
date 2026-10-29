# Investor experience and UI polish plan

**Current pass, October 29:** the owner subsequently requested **"Implement all suggestions"**, authorizing UI.6-UI.9 together. [Section 11](#11-third-evaluation-and-proposed-implementation) retains the evaluation and implementation sketch; [section 12](#12-third-pass-implemented-result) records the resulting behavior. STATUS owns actual verification and remaining acceptance.

Designed October 28, 2026; implementation subsequently authorized by **"Please implement all suggestions"**. The complete UI.1-UI.5 scope is implemented locally. The original motivation was **"Too much setup or technical detail"** and a modern, elegant interface that feels close to a native application. [SPEC](SPEC.md) remains the product authority; [STATUS](../STATUS.md#complete-investor-ui-polish-implementation) owns actual checks and remaining acceptance.

**Fit:** the explicit all-suggestions request authorizes the complete coherent UI outcome. Use the five phases below as implementation milestones: shared presentation/navigation, holdings/benchmark, native preparation/settings, proposals/worksheets, then recovery and final visual/regression review. Reuse the existing React/API/persistence/calculation boundaries, preserve concurrent edits and exact financial/source facts, and stop after local implementation/checks and owner handoff. No financial method, source, investor-limit default or release adoption follows.

## 1. Findings that motivated this pass

The current React application already contains import/review, cash treatment, holdings mapping, benchmark/source review, EOD preparation, candidate calculation, comparison, worksheets, saved diagnostics and recovery. The live two-name fictional demonstration was inspected without changing its financial state. The remaining screens were assessed through current components and their browser consumers; this is not a claim of a newly observed complete owner workflow.

The pre-pass presentation problems were:

- Most workflows coexist on one long page. Import controls, current settings, market preparation, calculations, saved records and maintenance tools compete for attention.
- Large headings, bordered sections, explanatory paragraphs and green buttons recur at similar prominence. There is little distinction between the main task, an optional tool and supporting evidence.
- IDs, JSON, source locators, issue codes, machine timestamps and full analytic precision appear in ordinary views. A checkbox or action can be far below the explanation it concerns.
- The same exception, source facts or qualification language may appear in several adjacent panels. This makes the interface feel longer without helping the investor decide.
- Several ordinary setup steps still start with settings/control files. Moving these file inputs into a disclosure alone would leave the underlying task difficult; supported investor settings need normal form controls.
- Existing useful review/save boundaries, immutable history, exact source facts and financial safeguards should be presented more clearly, rather than weakened to make the interface appear simpler.

Current implementation anchors: `frontend/src/review.tsx` composes the page and owns mutations; `style.css` supplies broad global element rules; `lots.tsx`, `benchmark.tsx`, `benchmark-review-form.tsx`, `input-preparation.tsx`, `inputs.tsx`, `candidates.tsx`, `worksheets.tsx`, `history.tsx`, `holdings-mapping.tsx` and `cash-treatment.tsx` own the task views. Implementation should preserve those behaviors while separating application layout from workflow state.

## 2. Visual direction

**A calm desktop investment workspace.** Retain Prosper's green identity, with a neutral canvas, readable white/light surfaces, deep charcoal text and a restrained forest-green action/selection accent. Use amber for a review warning and red for a blocking error; state always has a text label as well as color. Avoid large promotional headings, decorative charts, gradients, glass effects and repeated card frames.

| Element | Proposed treatment |
| --- | --- |
| Application frame | Compact persistent sidebar, quiet top toolbar, one main working area and a contextual details panel when needed |
| Navigation | Text labels with consistent small outline icons; selected item has a restrained background/accent; no icon-only primary navigation |
| Typography | Local system font stack led by Segoe UI on Windows; approximately 14-16 px ordinary text, 12-13 px supporting text and 22-28 px page titles; consistent weights and tabular numeric alignment |
| Spacing | A small shared scale based on 4/8 px; generous separation between tasks, tighter relationships inside forms and tables |
| Surfaces | Neutral background, subtle separators, moderate 8-12 px radii; shadows mainly for popovers/dialogs, rather than every section |
| Buttons | One obvious primary action per task area, quiet secondary actions and text buttons for optional actions; compact coherent control heights |
| Forms | Visible labels, short helper text only when needed, related fields grouped, errors beside the affected input and entered values preserved |
| Tables | Readable names/tickers first, aligned quantities/currency, restrained row separators, clear selected/hover/focus states and details on demand |
| Appearance | Shared light/dark tokens with system preference support; the first visual review should establish the light appearance and test both appearances before the pass is complete |
| Motion | Brief, subtle panel/state transitions; no decorative looping or unnecessary entrance animation; respect reduced-motion preferences |

Native feel comes from coherent navigation, keyboard/focus behavior, compact toolbars, predictable panels and responsive feedback. Keep the adopted local web/React architecture. A desktop wrapper, new UI framework, new font download or dependency migration is not a prerequisite. Any proposed new package must be justified separately before adoption.

## 3. Application layout and navigation

Use four main destinations, with Settings below them:

| Destination | Investor purpose | Main contents |
| --- | --- | --- |
| **Overview** | Know where things stand and what to do next | Current account/date, last saved analysis or worksheet, a concise readiness summary and Start/Continue analysis |
| **Holdings** | Import and understand the selected portfolio | Import/replacement, holdings/lots, cash treatment, mapping and source exceptions |
| **Analysis** | Prepare, review and compare a new analysis | Guided stages: Benchmark -> Review inputs -> Proposals; visible progress and access back to earlier stages |
| **Worksheets** | Reopen, inspect and export dated work | Saved analyses/worksheets organized by date/account/benchmark, historical-state labels and manual worksheet detail |
| **Settings** | Adjust reusable preferences and maintain local work | Investor settings, data sources/history, backup/restore, appearance and Advanced tools |

The toolbar should carry a human-readable account label, relevant analysis/source date and concise application/financial qualification state. Machine revision IDs and hashes belong in details. Do not fabricate account names or hide uncertainty when an account/date is unavailable.

The analysis header uses a compact stage indicator, a concise status and one next action. Desktop layouts may keep a small account/benchmark summary beside the task; narrower layouts stack it. Use a task-local footer/toolbar for actions on long reviews so the button is near the decision. Navigation must preserve in-progress state within the current session, or clearly warn before leaving an unsaved form; it must not silently commit, discard or recalculate financial inputs.

An empty first session should offer **Import holdings** and **Restore a backup**. A returning session should offer **Continue analysis**, **Open worksheet** or **Import refreshed holdings** according to actual saved state. Avoid a decorative dashboard and unsupported performance/history figures.

## 4. Information that appears only when requested

The interface should have one consistent hierarchy. A small question mark is useful for a short explanation, but should not become the container for every kind of information.

| Visibility | Contents | Interaction |
| --- | --- | --- |
| **Always visible** | Decision-relevant amounts/dates, costs/cash, selected investor limits, unresolved facts and their consequences, exclusion warnings/unknown coverage, current/historical state, running/error status and concise financial-use limitation | Ordinary text, concise summaries, inline warnings and action buttons |
| **Short explanation** | Meaning of cost basis, tracking error, a model estimate, a cash distinction or a metric's units | Small labeled `?` button opening a short popover; hover can supplement click/focus/tap |
| **View details / Why?** | Calculation explanation, affected holdings, exclusions, source-date comparisons, complete limit breakdown or longer assumptions | Text button opening an accessible side panel; a full-screen panel on narrow layouts |
| **Advanced / Source details** | Model constants, exact session/calendar conventions, provider/dataset evidence, original values/locators/checksums, internal IDs, verbose diagnostics and supported JSON import/export tools | Clearly labeled optional section or panel, with deeper tables/files available there |

Rules for these controls:

- Use a `?` beside an unfamiliar concept, not after every word or ordinary field. Give icon-only buttons explicit accessible names such as **About tracking error**.
- Use a popover for a few sentences. Put long explanations, forms, tables and evidence into a panel instead of an oversized tooltip.
- Support keyboard focus/activation, Escape to dismiss, sensible focus return and touch. Do not require hover to read any explanation or take an action.
- Keep missing required declarations in the main task as focused questions. A required unanswered investor limit or source convention is not an Advanced preference.
- Hide resolved technical detail, not financial consequences. A price change, excluded exposure warning, unknown basis or inability to calculate remains visible with an understandable next action.
- Consolidate repeated qualification prose into one concise application/result notice plus **Assumptions and limitations** details. A positive check means its actual scoped check passed, never that financial use is approved.
- Present money, prices, percentages and dates with useful display precision. Preserve originals and exact values in details and in existing source/record contracts; formatting must never alter a calculation, economic comparison or saved output.

Example: replace the ordinary display of `marks / security-faaa / lot_mark_conflict / row:2520` with **Prices changed for 2 holdings**, followed by the old/new dated prices and **Review updated prices**. Put the code, row locator, exact values and original evidence in **Source details**. Explicit acceptance still uses the existing reviewed settings action.

## 5. Complete investor journey

### Import and holdings review

- Make supported holdings upload the main opening action, using an accessible file picker/drop area with concise format guidance. Keep normalized JSON and supplied context tools under Advanced import.
- After parsing, show account/date, import counts and a focused list of issues that need attention. Review and selection remain explicit; a failed/replaced draft must not overwrite selected holdings.
- Use one holdings table with ticker/name, shares, cost basis, available value/loss estimate and review status. Use a row details panel for tax lots, unknown reasons and original source facts.
- Put **Cash / Cash equivalent / Undo** treatment beside the relevant holding, with its supported reported amount. Explain the distinction from the chosen investment budget with a `?`; keep any missing cash value visible.
- Integrate mapping and exclusions into the same review instead of separate disconnected panels. Names, values, excluded exposure and unknown coverage remain inspectable; full source accounting is retained.

### Benchmark selection

- Present the supported fund choices using ticker, fund name and concise coverage description. Keep provider/date controls compact and the current explicit selection unmistakable.
- Show the reported date, source status and relevant exclusions before confirmation. Do not silently choose a fund, alternative date or replacement provider.
- Offer **View benchmark holdings**, **Source details** and Advanced source import. Keep full row/metadata editing available for exceptions, rather than placing the entire ledger on the main route.
- Keep the selected benchmark visible in the analysis summary when proceeding.

### Preparation and input review

- Start with a short readiness summary: what is available, what needs a decision, and what prevents the next calculation. Show only the unresolved questions that matter to the selected inputs.
- Fill attributable routine facts from supported selected sources and use the adopted Standard R1 preset. Reuse previously reviewed declarations only through the existing explicit, source/date-consistent behavior; do not invent calendars, permissions, freshness policies or economic defaults.
- Replace ordinary lot/candidate settings-file prerequisites with native controls for supported investor choices. Use clear amounts, percentages, dates, enabled/disabled limits and reviewed cost/funding controls. Keep JSON as an expert tool. This is a real workflow change, not a CSS-only relocation, and must be verified as such.
- Put technical model/capacity controls and resolved source conventions behind Advanced/details. Keep genuinely missing conventions/declarations as plain-language questions with **Why is this needed?** help.
- Group exceptions by **Needs attention**, **Review warnings** and **More information**; show affected counts, an understandable consequence and a direct resolution action. Display each issue once in the main review while retaining its full source locations in details.
- Summarize retained/excluded holdings and benchmark coverage. Keep strict materiality warnings and unknown denominators visible, while detailed rows open on request.
- Review the actual cash budget, funding assumptions, fees and enabled economic limits before calculation. Hide repeated machinery, not these decisions.

### Calculation and proposal comparison

- Use a single **Create proposals** action when current required inputs/settings are ready. When blocked, state why and link to the affected task; keep useful partial holdings/loss diagnostics available.
- Replace technical worker/status text with clear stages such as **Preparing inputs**, **Estimating risk** and **Comparing proposals**. Keep cancellation and unresolved-request retry visible. Do not invent progress percentages or promise successful completion.
- Compare **No changes** with checked proposals in a compact table or selectable list. Show estimated price/basis loss, costs, final selected cash, tracking error and the applicable constraint result.
- Keep a selected proposal's trades visible by security and lot. Use **Why these trades?**, **Risk details** and **Constraints and assumptions** panels for explanations.
- Use charts only where existing results support a useful comparison, such as current/proposed benchmark-relative exposures. Do not add fabricated performance series or decorative analytics.
- Preserve honest bounded-search outcomes. **No proposal found** is distinct from proved infeasibility; **Checked proposal** does not imply independent model acceptance, a global optimum or financial authorization.

### Worksheet, export and return visits

- Give the worksheet a clean document-like view with source/analysis dates, estimated trade lines, loss/cost/cash summary and concise assumptions.
- Keep share edits inline and explicitly recheck changed quantities. Unsaved edits cannot retain a previous successful-check state.
- Use **Save worksheet** and **Export** as primary outcomes. Preserve unambiguous lot/security references in the saved/exported worksheet even when the on-screen summary is simpler.
- Keep **Manual execution only** and the need to import refreshed holdings after external changes visible at this handoff. Do not introduce a trading action.
- Replace ID-only saved-record dropdowns with a readable dated list. Historical outputs reopen without recalculation; revising old inputs starts a new analysis and cannot overwrite history.
- Put backup/restore and reusable-history maintenance in Settings, with clear destination/empty-workspace restrictions and refusal/retry states. Recovery remains available from the empty starting screen.

## 6. Interaction quality across every screen

- **Keyboard and focus:** logical navigation order, visible focus, labeled controls, predictable Enter/Escape behavior and focus returned after closing a panel. Critical actions have visible labels.
- **Responsive layout:** desktop is the primary workspace; test approximately 1440/1280 px, narrower 768 px and 390/320 px layouts. Collapse the sidebar on narrow screens and use full-screen details panels. Keep wide tables in their own scroll container, not a horizontally scrolling application.
- **Readability:** normal text should meet a 4.5:1 contrast target and large text 3:1; test both appearances, text zoom and reduced motion. These are design checks, not an unearned accessibility-conformance claim.
- **Feedback:** loading placeholders for actual pending work, clear success acknowledgement, useful empty states and actionable errors. Distinguish an unsaved draft from a saved record; never claim **Autosaved** for an explicit financial/settings save.
- **Failure and concurrency:** preserve identical pending requests after a lost response, explain an action refused on newer inputs, and stop late responses from replacing current state. Changing screens must not bypass those protections.
- **Efficiency:** navigation, disclosure and historical reads must not trigger numerical fits. Reuse existing pagination and bounded services; add virtualization only for an observed rendering bottleneck.

## 7. Ordered implementation route

The owner authorized all five phases together after reviewing this plan. The implemented scope follows these dependency-ordered milestones; the final scope/evidence below supersedes the original planning-only stop.

| Phase | Outcome | Main acceptance evidence |
| --- | --- | --- |
| **UI.1 - visual foundations and application layout** | Shared visual tokens, typography/buttons/forms/tables, tooltip/popover/details-panel patterns, sidebar/toolbar and four destinations; retain current workflows and their state while relocating them | Screens/navigation at desktop/narrow widths, keyboard/focus and both appearances; affected review, saved-state and error/retry browser consumers; no numerical change |
| **UI.2 - holdings and benchmark experience** | Polished import/review, integrated lots/cash/mapping/exclusions and clear benchmark selection; ordinary views use investor language and evidence is available on request | Supported/invalid import, mapping/cash undo, source/benchmark switch, exclusion/unknown coverage, stale review, explicit selection and reopening; full ledger/source access remains |
| **UI.3 - guided preparation and exceptions** | Focused unresolved questions, native supported investor/cost settings, coherent help and one actionable exception review; standard preset/technical details become quiet summaries | Existing preparation/profile/EOD binding, no silent defaults, exact limits/cash, invalid edits, source/settings changes, price review, lost response and incomplete/empty outcomes; affected API tests if those boundaries change |
| **UI.4 - proposals and manual worksheet** | Polished calculation states, no-trade/proposal comparison, trade detail, quantity checking, worksheet save/export and readable historical work | Checked/unavailable/cancelled/limited outcomes, stale results, strict final checks, edits clear validation, save/retry, export and historical equality; one adequate existing small fit journey rather than a new study |
| **UI.5 - settings, recovery and final experience review** | Organized preferences/data/Advanced tools, backup/restore, returning-user flow and final consistency/accessibility pass across every stage | Restore/refusal/lost response/reopen, preserved original records/sources, first/returning sessions, desktop/narrow/light/dark/keyboard observation and owner walkthrough |

Implementation should build a small shared component set, not a general design framework. Keep current API/persistence/calculation contracts unless a specific supported UI interaction requires a scoped change. Do not introduce compatibility readers, migrate owner state, change financial methodology or create an automatic data-acquisition route as part of visual polish.

## 8. Definition of completion

The overall pass is complete when:

1. A first-time user can identify the next action at import, benchmark, review, proposals and worksheet without reading a technical paragraph or finding an unrelated section lower on the page.
2. A returning user can resume or reopen dated work, and can find backup/restore and refreshed-holdings import deliberately.
3. Ordinary screens contain no raw JSON, checksums, internal run/security IDs, solver diagnostics or model constants; legitimate investor-facing lot references remain available where execution/review needs them.
4. Each unfamiliar concept has concise optional help. Long evidence has a consistent panel/details route, accessible by mouse, keyboard and touch.
5. All material missing facts, unknown values, affected scope, source dates, warnings, financial limitations and required decisions remain visible or are explicitly presented before the affected action. Nothing unknown becomes zero or silently accepted.
6. Data/order/value/financial results and historical outputs are unchanged by presentation-only work. Any intentional input workflow change has specific behavioral tests and current consumer coverage.
7. Loading, blocked, no-opportunity, partial, failed, cancelled, stale, unresolved-write and historical states are designed and checked alongside the successful path.
8. Desktop and narrow layouts, both appearances, zoom, focus and reduced motion are visually reviewed with fictional fixtures; the investor journey reaches saved/exported/reopened work through the current application boundary.
9. The owner reviews the resulting experience. Local UI tests and polished graphics do not establish source qualification, independent model/tax acceptance, financial-use authorization or release.

**Current stop:** UI.1-UI.5 are implemented locally; owner visual/usability acceptance remains open. No additional implementation successor is implied.

## 9. Implemented result and acceptance boundary

- The persistent application shell has Overview, Holdings, Analysis and Worksheets, with Settings, account/date context, explicit refresh and System/Light/Dark appearance. Navigation retains mounted drafts and never commits settings or starts a model fit. Only appearance is kept in browser storage.
- Shared question-mark help, keyboard-dismissable native modal side panels, exact-value popovers and grouped human-readable exceptions put long evidence behind explicit interaction. Original source/record JSON, IDs, hashes, full ledgers, history rows and model settings remain available. Tiny nonzero values retain their sign instead of displaying an exact zero.
- Holdings show the selected portfolio before import tools, with supplied quantity and single-lot basis, per-lot details, cash treatment and source-bound mapping. Multiple-lot basis is inspected per lot rather than silently summed or reconstructed. Benchmark choices remain explicit; complete source filtering and original-response inspection are optional tools.
- Native cash/cost/funding/target controls and native proposal cost/whole-share-bound controls replace ordinary settings/control JSON prerequisites. Standard R1, explicit declarations, EOD price review, strict economic checks and immutable save boundaries remain. JSON tools are retained in Advanced sections. Costs, bounds and the supported exploratory calculation method still require explicit choices; this pass does not invent a qualified production solver/default, missing source permissions, calendar, basis, funding or investor limits. Imported-history acquisition/import remains an explicit existing source tool.
- Proposal progress/outcomes, no-change comparison, quantity checking, dated worksheet save/export and the readable saved-work library share the same visual language. Historical records retain their saved financial inputs/results. Backup/restore and history/workspace maintenance are in Settings; restore still refuses a populated destination.
- Final source-build browser coverage, build/contracts/docs checks and screenshots are recorded once in STATUS. New fixture journeys exercise exact native settings through a checked worksheet/export/restore, disclosure/theme/navigation behavior, and late native reads versus malformed imported controls. These are local engineering checks, not a formal accessibility certification or independent tax/model, calibration, source, owner-usability, financial-use or release acceptance. The next action is an owner walkthrough of the refreshed experience.


## 10. Second evaluation and implemented refinements

The owner requested another evaluation, then explicitly authorized **"Implement all of your suggestions"** and **"Sync to GitHub and update the readme where appropriate"**. The implementation authority supersedes that pass's planning-only boundary. The evaluation's reached observations were the live Overview, Holdings, cash draft, benchmark selector, saved input review, worksheet empty state, Settings and lot-details panel, plus retained completed-worksheet/narrow/dark captures and current source. Automatic review declined opening a new preparation draft during the earlier planning-only stage; that action was not bypassed. The later explicit implementation request authorizes ordinary preparation and verification.

The next coherent outcome preserves the established visual direction while tightening these interactions:

| Area | Refinement implemented | Boundary retained |
| --- | --- | --- |
| Overview | Current saved record/revision drives the next task; readiness text and a direct saved-review link replace a generic loop back to benchmark choice | Missing, stale or unavailable evidence never becomes ready |
| Navigation | Hash-addressed destinations/stages, browser Back/Forward and reload, and heading focus; mounted drafts persist between destinations | No financial values enter browser storage or the URL; reload is not autosave |
| Holdings | Display actual reported holding membership, remove empty tax-lot actions, separate an unselected preview from current holdings and collapse returning-user import controls | Original identity/source records and unknowns remain retained; no quantity/basis reconstruction |
| Benchmark and mapping | Prominent selected benchmark/date; replacement/source tools use a separate disclosure; unsupported IVV/date mapping has an explicit reason | No fund/date/provider substitution or implicit selection |
| Cash setup | Visible unsaved-draft state and an explicit keep/discard choice before reloading edited cash settings | Existing reviewed-budget, funding, target and immutable save checks remain |
| Input review | Numbered questions, a compact source/window/investor checklist, unresolved-required badges, human limit names and exact decimal-to-percent previews | Required calendar/source/permission/limit facts stay explicit; previews never rewrite the input fraction |
| Proposal setup | Costs explain their relationship to saved sell costs/funding; the calculation-method disclosure stays open until explicitly chosen | No production solver/default or economic limit is adopted by visual polish |
| Saved work | Bounded merge of recent worksheet/analysis streams, creation time separate from analysis date, type filtering and pagination | Read failures stay explicit; no historical recalculation |
| Worksheet | Separate compare/revise and saved views; opening a worksheet loads its original proposal; task labels use investor language; narrow comparison becomes readable cards | Strict final checks, stale restrictions, frozen outputs, full export and manual execution remain |
| Evidence and visual detail | Better reading sizes, mobile account/date layout, grouped warnings with missing/unknown/unverified information open, popover bounds/scroll dismissal and consistent details | Exact values, full warnings, reasons and source records remain available; no accessibility certification is inferred |
| README | Current fixture screenshots, navigation/native-setup explanation and a precise development/acceptance boundary | No private data, performance fabrication, financial-use or release claim |

STATUS owns the final focused/full-checkpoint evidence and GitHub synchronization result. Source, method, investor and release decisions remain under their direct contracts. No account access, trading, private-data publication or automatic follow-up work is added.

## 11. Third evaluation and proposed implementation

### Scope and evidence

The owner requested **"Do another UI polish pass in terms of evaluating it and making a plan for implementation"**. **Fits as one evaluation/planning task:** inspect the existing experience, identify specific remaining friction, order implementation outcomes and define proportionate acceptance checks. Stop before implementation. The reviewed checkout is `13a8e59808dfc4b1eaf0569da2a67c5f054b1f7a`, initially clean. No application, financial settings or test changes, source acquisition, calculation, commit or push belongs to this pass.

Fresh read-only inspection used the existing fictional demonstration at `http://127.0.0.1:51492`: Overview, Holdings, Benchmark, Review inputs and Proposals entry, the saved-work library, an existing saved input review and Settings. No preparation/proposal draft was loaded or submitted. Expanded preparation and completed comparison/worksheet evaluation combines current source with retained fixture images: `docs/assets/decision-workspace.png`, `docs/assets/worksheet-checks.png` and `.local/mvp223/preparation-narrow.png`. The preparation image predates the last refinement and is supporting layout evidence, checked against current source, not a fresh traversal. This pass does not claim a new complete calculation/export/recovery journey, fresh responsive/theme testing or owner usability acceptance.

### Design judgment

Keep the green identity, neutral surfaces, system typography, persistent navigation and existing investor destinations. They now form a coherent visual foundation. The largest remaining gains come from a clearer task, more trustworthy context and less competing information. Refinement should make Prosper feel like a focused application: compact context, one main action, a readable working area and predictable optional evidence.

The default view should answer **which portfolio/date, what is known or unresolved, what changed, and what to do next**. Question marks explain unfamiliar terms; explicit details controls reveal evidence. Required investor choices, material warnings and unknown affected values remain visible before their dependent action. Hiding a required form inside Advanced does not resolve setup burden.

### Findings and proposed changes

| Priority / area | Observed friction or source-backed concern | Proposed implementation |
| --- | --- | --- |
| P1: dates and saved context | The live library's input review shows `2026-10-25`, while selected holdings are dated `2026-10-23`. `saved-work.tsx` renders `run.as_of` as an unlabeled leading date, despite help describing analysis dates. Saved details repeat that shorthand. A current-workspace toolbar also remains above historical work. | Label analysis date, source date and saved time explicitly. Read each from its appropriate frozen record; use an explicit unavailable value where absent. Keep knowledge time in details. Add a compact original account/benchmark/date header to an opened historical document, clearly distinct from current workspace context. Never substitute knowledge time or current holdings for a missing saved analysis date. |
| P1: task state and feedback | The live message **"Saved analysis opened. Its original dates and input revision are shown below"** persists after navigating to Holdings, Benchmark, Proposals and Settings. Overview derives guidance from a single latest record/revision; its conditions have no dedicated running, failed-read or cancelled guidance. | Scope feedback to its action/destination and clear obsolete success text on navigation/edit. Preserve unresolved write/retry messages until resolved. Derive a small explicit view state from available evidence: loading, needs attention, inputs reviewed, calculating, limited/cancelled, comparison available or historical. Keep readiness scoped to the specific task. Show a loading placeholder rather than a premature empty-portfolio assertion; distinguish failed reads from no saved work. |
| P1: preparation focus | Current preparation renders the editor, exceptions, profile, settings/funding, coverage and review/save controls in one vertical flow. Required declarations can remain inside closed sections. The retained narrow capture illustrates the cumulative length. EOD correction can send the user to cash settings and require another preparation. | Separate **Edit inputs** and **Review inputs** within the existing stage. Start review with outstanding decisions and a concise source/coverage/settings summary. An exception should open and focus its relevant editor. Summarize explicitly reused declarations with dates/source and a reviewable change summary; do not silently copy them. Provide a clear return from reviewed cash/EOD changes, state why preparation must be repeated and preserve compatible draft facts. Keep the review/save action near the decision, including on narrow screens. |
| P1: comparison and worksheet reading | Comparison gives absolute metrics without a compact change-versus-no-changes explanation. Saved worksheet combines ST/LT/unknown loss and cost/cash/NAV into slash-separated values. Risk is shown to four decimals without nearby selected-limit context. | Pair proposals with their no-change baseline under the same frozen inputs. Show concise changes for loss, cost, cash and estimated tracking error, with units and exact details. Separate the combined worksheet metrics into labeled values. Surface the relevant saved limits and validator outcomes beside the trade-offs; do not infer feasibility from rounded values. Label modeled-sleeve value accurately and keep price/basis loss distinct from tax savings. No automatic best/recommended ranking or optimum claim. |
| P2: ordinary setup and holdings | Holdings begins with a prominent **Review current holdings** button above an already visible review. Unsupported mapping occupies a full section. The table shows basis `30` under a USD heading. Proposals exposes **"Prepared input run: inputs"** and **"cost/search controls"**. Sale maximums render every lot at once, unlike paged replacement maximums. | Give the portfolio table first emphasis; move repeat-read, mapping and import tools into a quiet contextual toolbar/disclosure, with a visible reason when mapping is relevant but unavailable. Use consistent currency precision and quantity formatting with exact values available. Replace machine references with a dated input-summary link. Group costs and sale/replacement maxima by investor purpose; page large sale-lot lists with unresolved counts and a route to the first missing value. Preserve explicit choices and exact supplied quantities/basis. |
| P2: saved work as a document | A saved analysis opens below the library and the empty comparison panel. Opening a record does not create an address for that selected record; route reload only restores the destination. | Use a selected-document view with a compact library/back control and a clear distinction between input review, proposal comparison and saved worksheet. Keep original account/benchmark/date visible from frozen facts. Support read-only record selection in navigation where current contracts allow it; reload/back should reopen the same supported record or explain its unavailability. Never run a calculation or borrow current input labels to fill historical gaps. |
| P2: visual hierarchy and density | Overview repeats the next-step paragraph in Analysis status; backup has equal card prominence. The shell repeats Local workspace and adds an eyebrow/tagline above or beside every task. Several equally green review buttons compete. | Compact Overview into portfolio context plus one next-action summary, recent work and quieter recovery access. Remove repeated decorative labels; keep privacy and exploratory status clearly discoverable, with the qualification status visible. Use one primary action per task, neutral secondary controls, aligned numerical columns, constrained form widths and a consistent spacing/control scale. Keep supporting text readable. Trim mobile header/navigation height; place Appearance in Settings or a compact menu without obscuring context. |
| P2: evidence, warnings and recovery | In-app details panels use an external-link arrow. Many exact-value triggers can lengthen keyboard traversal. Warning expansion/grouping uses string keywords, which cannot reliably encode materiality. Settings shows a restore file chooser even when the workspace cannot accept a restore. | Reserve question marks for short definitions, chevrons for local panels, carets for inline expansion and external arrows for external destinations. Provide structured readable evidence before raw records. Make exact values reachable without redundant controls, retaining keyboard/touch access and focus return. Summarize repeated consequences while preserving full original warnings; use existing structured issue/scope/outcome facts where available and do not hide an unknown because its text missed a keyword. Keep backup prominent; collapse restore under a clear explanation of the empty-workspace requirement. |

Implementation anchors: `review.tsx` (current state, next action, feedback, task composition), `saved-work.tsx` and `presentation.ts` (saved dates/status), `input-preparation.tsx`, `inputs.tsx` and `investor-settings.tsx` (edit/review, exceptions, EOD/cash return), `proposal-setup.tsx` (costs and large lot lists), `worksheets.tsx` (comparison and document), `app-shell.tsx`, `navigation.ts`, `ui.tsx` and `style.css` (shared interaction/visual behavior). These are starting points, not a requirement to replace the architecture or introduce a new framework.

### Ordered implementation outcomes

| Outcome | Concrete scope and dependency | Focused acceptance evidence after authorization |
| --- | --- | --- |
| **UI.6: trustworthy context and task state** | First. Correct date semantics in saved lists/details; original historical context; scoped messages; explicit loading/read-failure/running/stale/cancelled/limited guidance. Inspect existing saved facts before deciding whether any API work is necessary. | Fixtures with different source, analysis, knowledge and creation dates; missing dates without fallback; current account different from historical account; record-read failure versus empty; late refresh/read and running/cancelled/limited results; success message navigation and unresolved-write/identical-retry behavior. Navigation/read must not mutate or recalculate. |
| **UI.7: focused preparation and proposal setup** | Build on UI.6 context. Separate edit/review, link exceptions to fields, make required missing choices apparent, clarify explicit declaration reuse and EOD/cash return. Remove ordinary machine references; bound large sale/replacement lists. | First-use and explicit-reuse fixture flows; missing declarations; source/revision changes and late responses; cash/EOD edit invalidation and return; costs/funding consistency; paged missing/invalid maxima. Reuse existing strict preview/save/quantity checks and one adequate checked-candidate consumer. No new numerical study. |
| **UI.8: decision comparison and saved document** | Build on clear input identity. Add baseline changes, separate worksheet metrics, selected-limit context and focused saved-record reading/navigation. | Hand-specified display/delta cases including negative, tiny nonzero and unavailable metrics; conservative validator result retained near rounded display; no-change diagnostic and limited search; historical reopen after current inputs change; export equality and original identities/source dates; selection reload/back with unavailable-record handling. |
| **UI.9: final visual and interaction consistency** | Apply the compact shell/Overview, primary/secondary hierarchy, disclosure vocabulary, evidence/warning and Settings refinements across the completed journey. Shared primitives may be introduced earlier when needed; this phase verifies consistency. | Visual inspection at 1440/1280 desktop and 768/390/320 narrow widths, light/dark/system, 200% zoom, keyboard and touch-sized targets, focus return, long content and reduced motion. Check first-use, returning, loading, blocked, empty, partial, failed, unresolved-write, cancelled, stale and historical states. Keep unknown exposure/material warnings visible and exact evidence accessible. |

Use existing APIs and retained records where adequate. If a saved date/context is absent, show that absence; do not expand scope into historical reconstruction or a new metadata subsystem. Add a narrowly justified current API field only if existing attributable frozen facts cannot support the agreed display. Existing full input/source payloads should not be fetched without bounds merely to decorate a large library.

Production calculation-method selection and additional financial defaults remain separate owner decisions. UI.7 should explain the existing exploratory choices clearly and hide optional computation budgets; it must not silently choose a new production method, funding, source permission, calendar or economic limit. No new desktop wrapper, dependency, decorative performance chart or compatibility migration is needed for this plan.

### Completion and stop

The resulting interface should let an investor identify the account/date and current-versus-historical state, find the unresolved decision, understand a proposal's change from no changes and reopen the original saved worksheet without reading technical machinery. Material missing facts, strict enabled limits, original sources/exclusions and full warnings remain intact. Estimates remain exploratory and unqualified; pass/fail comes from saved checks, not display rounding or a green card.

After implementation authorization, run affected browser/build/type checks and relevant boundary consumers in proportion to each change; reserve the full checkpoint for an explicit delivery/sync request. Same-agent UI checks are not formal accessibility certification, independent model/tax acceptance, source qualification, owner paper acceptance, financial authorization or release.

**Planning-stage stop, subsequently superseded:** UI.6-UI.9 were proposed without implementation. The owner then authorized all suggestions; the implemented result follows.


## 12. Third pass implemented result

The owner's **"Implement all suggestions"** request authorizes the complete UI.6-UI.9 sequence. **Fits:** implement the shared context/state and document navigation first, focus native preparation/setup, improve comparison/worksheet reading, finish shared visual/disclosure behavior and check affected consumers with fictional fixtures. Preserve all three prior planning-document edits. No subagents, new dependency, financial method/default, backend/API/schema change or publication is part of this outcome.

- **UI.6:** saved lists label modeled analysis dates and benchmark source dates correctly; knowledge time is optional evidence, never an analysis-date fallback. Selected saved documents show original account/source/analysis/benchmark context from frozen facts and retained references, with explicit unavailability on failed reads. Workspace reads publish selected state together; loading/failure, in-progress, cancelled/limited and checked-comparison guidance differ. Current saved input lookup is bounded. Success feedback is scoped away on navigation while unresolved writes retain their explicit retry block.
- **UI.7:** preparation separates Edit inputs from Review inputs. Exceptions link to the relevant editor or holdings/benchmark/cash task; unresolved required sections expose review badges and focus destinations. Explicit declaration reuse has a before/after summary and original reference. Cash/EOD review has a return route and a revision/repreparation explanation. Investor limits use readable labeled summaries, with exact declarations/references in details; review/save is directly reachable. Sale maximums now use bounded pages, preserve edits and expose a first-unresolved-lot jump. Native proposal summaries replace ordinary raw input-run instructions.
- **UI.8:** comparisons show signed changes from no changes, distinguish tracking-error percentage points, expose saved limits and conservative check bounds, and retain exact comparison records. Worksheets separate short-/long-/unknown-term loss, cost, cash and modeled sleeve value. Saved records open as focused documents with read-only selection addresses, reload/Back/Forward, unavailable-record retry and original proposal binding. Late reads cannot replace another destination or record. Historical reopen and export use original outputs without a new fit.
- **UI.9:** compact Overview/toolbar, quieter secondary actions, readable numerical formats, a portfolio-first Holdings view and collapsed mapping tools reduce competing controls. Appearance lives in Settings. In-app panels use a chevron; short help remains question-mark driven, with keyboard dismissal/focus return and bounded scrolling. Repeated recognized warning boilerplate has concise consequences and full originals on demand; unfamiliar/dated warnings remain visible verbatim rather than depending on a keyword to open. Recovery keeps backup prominent and restore in an explicit empty-workspace disclosure. Mobile worksheet metrics use two columns where readable.

STATUS records the actual focused browser/build/docs checks, fixture screenshots, demonstration revision and limitations. Checks cover dates/account changes, missing facts, late reads, exact/rounded/tiny values, explicit declarations, invalid/stale settings, identical retries, cancellation, original export/recovery and responsive disclosure/navigation. Browser viewport checks are not a formal accessibility certification or native browser-zoom certification. Independent model/tax review, source qualification, calibration, owner usability/paper acceptance, financial authorization and release remain separate.

**Current stop: UI.6-UI.9 implemented locally; next action is an owner walkthrough of the refined preparation, comparison and saved-document experience.** No automatic GitHub sync, acquisition, financial-method adoption or release follows.
