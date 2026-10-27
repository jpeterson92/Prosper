# Fictional Fidelity-shaped stock lots

These are **entirely invented development fixtures**, using the 15-column combined-file structure supplied by the owner on October 23, 2026. The owner authorized assuming that structure also applies to other users and individual stocks. No stock export or universal Fidelity format has been independently verified. All accounts, labels, stocks, values, dates and source filenames below were invented; none were copied from the private example's records.

This is the **combined format produced by the documented collection prompt**, not an official single-file Fidelity export. The current protected synthetic browser accepts it with attributable context and explicit mark/settings documents. [Collection guide](../../../docs/guides/FIDELITY_IMPORT.md). These fictional assumptions and local software checks do not establish real broker support, source qualification or tax acceptance.

## Files and expected behavior

| File | Case / current import behavior |
| --- | --- |
| [combined-stocks.csv](combined-stocks.csv) | Baseline: eight lots, three fictional account labels, four fictional stocks and five source exports. Preserve all rows, identifiers and original display text. This is an inspection case, not a planning-ready portfolio. |
| [missing-basis.csv](missing-basis.csv) | Acquisition/basis blanks, `Unknown` term and `--` display markers on a fractional lot. Keep explicit unknowns; never zero-fill or invent a date. |
| [repeated-reference.csv](repeated-reference.csv) | A repeated source-file/source-record locator. Refuse or explicitly report the duplicate evidence. Do not confuse it with separate lots that have identical values. |
| [conflicting-reference.csv](conflicting-reference.csv) | Different basis/gain text for the same source locator. Retain the conflict and refuse silent selection/overwrite. |
| [schema-drift.csv](schema-drift.csv) | Renamed column: `Average cost basis USD`. Refuse the unsupported header rather than guessing. |
| [malformed-row.csv](malformed-row.csv) | Last record has fourteen fields under a fifteen-field header. Refuse explicitly rather than dropping the row or manufacturing a basis value. |
| [current-context.json](current-context.json) | Checksum-bound source context: 000SYNTH001 selected taxable, 000SYNTH002 explicitly IRA/Roth, 000SYNTH003 unresolved scope; reviewed fictional identities and classes, actual source cutoff and disclosed ordinary reported-basis assumption. |
| [current-lot-settings.json](current-lot-settings.json) | Explicit same-day marks/age limits, $1 isolated fee, 10 bps sell discount, reviewed zero additional cash, disabled final target and unverified history/funding assertions. These are test inputs, not adopted investor defaults. |
| [fixture-manifest.json](fixture-manifest.json) | Machine-readable schema, exact baseline expectations, case intentions, simulated source locators and unresolved evidence. It is not an executed adapter result. |

All CSVs use UTF-8 with BOM, CRLF record endings and CSV quoting. Every field is source-style **text**, including formatted currency/percentages and account identifiers with leading zeros. A narrow `.gitattributes` exception preserves these bytes in Git. Other authored text retains UTF-8/LF.

## Independent expected values

| Fictional account | Lots | Quantity | Total basis (USD) | Current value (USD) | Display gain/loss (USD) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 000SYNTH001 | 5 | 18.125 | 1954.00 | 1593.75 | -360.25 |
| 000SYNTH002 | 2 | 24.000 | 1160.00 | 1500.00 | 340.00 |
| 000SYNTH003 | 1 | 7.000 | 490.00 | 560.00 | 70.00 |
| Total | 8 | 49.125 | 3604.00 | 3653.75 | 49.75 |

These totals were specified independently of a broker import implementation. Money is not computed with binary floats. Display percentages are rounded to three decimals for these fictional cases; the source average basis can be rounded. In particular, the three-share FBBB lot has total basis **100.00** and displayed average basis **33.33**. Multiplying the rounded display yields 99.99 and must not overwrite the authoritative supplied total. Display P&L is not a forecast, realized result or tax eligibility determination.

Two FAAA lots in 000SYNTH001 have identical eight-field lot values but different source record references. Preserve both. FAAA also appears in another account, so a ticker is not an account or lot identity. Fictional descriptions include commas, parentheses and quotes to exercise real CSV parsing. Fractions include a 0.125-share residual. The `IRA Monitor` label is a fictional scenario cue; account names cannot determine account ownership/tax status in a production mapping.

## Source reconstruction and provenance limits

The six CSVs under `sources/` contain five baseline exports and one missing-basis alternative. Their manifest locators count **logical parsed CSV records**, starting at one. Each source's lot header is record five, and data begins at record six. Combined rows refer to source basenames, not repository paths.

Their preamble layout is explicitly invented: account/parenthesized label; symbol/parenthesized description; a single download-timestamp record; a blank record; then the eight-column lot header. Only the combined 15-column header and formatting classes were observed in the owner's attached example. The original per-position downloads were not supplied or inspected. These constructed preambles, timestamp spelling, missing markers and negative cases are test assumptions, not a claimed exact native Fidelity serialization. Do not use these source fixtures to certify a native preamble parser without separate source evidence.

The combined file has no durable broker lot ID, security classification/ID, original/carryover holding evidence, wash adjustment detail, cash snapshot, same-cutoff position snapshot, activity coverage, confirmations or event-inclusion boundary. `Source CSV row` is file-local provenance, not a stable broker lot ID across downloads. `Source download date` is collection metadata, not portfolio effective time. Nothing here authorizes an actionable plan, expands supported assets to ETFs/mutual funds, or passes G1.


## Browser walkthrough and expected estimates

Use the [current launcher](../../../docs/engineering/DEVELOPMENT.md#local-browser-workflow) with a fresh scoped `.local/lots-demo` runtime. In **Source-shaped lots and loss diagnostics**, choose the baseline CSV and current context, click **Review source-shaped lots**, review the normalized lots/unknowns and select the snapshot. Load the explicit settings JSON, inspect its assumptions, acknowledge review and save settings. Save lot opportunity diagnostics, then reopen the dated record or download/restore the current workspace backup.

All eight rows remain accounted for. Five lots belong to the selected account. The two identical-looking 2.500-share FAAA lots keep distinct source locators and IDs; the 0.125-share FBBB residual remains unsold. No independent positions or cash are fabricated. Supplied source amounts remain decimal text; derived estimates are Float64 with unrounded values retained in the saved record.

With the supplied marks, FAAA's hypothetical price/basis losses are $250/$40/$40; all three are blocked by the explicitly supplied IRA acquisition. The three-share FBBB row allocates $100 basis at a $30 mark: price/basis loss $10, cost $1.09, net proceeds $88.91, indicative tax P&L -$11.09. Its conditional price-loss subtotal is $10. These figures are independent of the CSV's displayed gains. Each row charges the full isolated-order fee; row costs must not be summed as a multi-lot order. Explicit portions and replacement IDs also screen same-batch conflicts, without proposing orders.

A cash editor changes only the selected additional budget. Enabling a separate final cash target requires an entered amount and investor tolerance; no target default or optimizer feasibility is inferred. Optional manual names require an explicit reviewed security mapping or remain unresolved and block affected scope. Their default restriction applies to both sales and replacement buys. Existing imported restrictions survive a new source import even when that file omits the other account. All history/household and future-activity warnings remain conditional.

The source parser deliberately accepts a bounded numeric/display grammar (28 significant/12 fractional input places); unsupported source lexemes become located unknowns while original bytes remain retained. No generic rational transport, durable cross-download broker lot key, basis reconstruction or native-export certification is implied.
