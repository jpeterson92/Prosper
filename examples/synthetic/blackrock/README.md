# Fictional BlackRock-shaped benchmark example

All holdings, mapping assertions and amounts here are fictional. The fund title and CSV columns mirror the supported IVV transport so automated checks can exercise the ordinary application contract; there is no application data-category flag.

Import `current-observation.json` through **Import saved benchmark response**, then supply `current-review.json`. A selected holding snapshot is needed to save a reviewed benchmark result. Review and save the result, then explicitly select it. Import/fetch alone never selects a benchmark. `current.csv` is the exact retained response, including a quoted multiline name and grouping commas.

Six source rows remain: two reviewed equities with values USD 60,000 and USD 30,000, plus excluded cash, money market, future and warrant rows. The retained equity total is USD 90,000 and weights approximately 2/3 and 1/3. A published equity weight is unknown. The negative cash value, unknown money-market value and distinct market/notional future weights remain source facts; exclusions create no spendable cash. No quantity-times-price fallback is performed. All supplied original cells and response bytes survive reopen/backup/restore.

The dates and reviewed identities are fixture assertions, not qualified market inputs or investor defaults. Subsequent analysis dates require compatible complete total returns for the retained names under the [dated-weight contract](../../../docs/domain/BENCHMARK_INPUTS.md#total-return-drift-to-a-later-effective-date).
