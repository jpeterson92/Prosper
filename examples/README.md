# Synthetic examples

Only invented portfolios, fictional account aliases and permitted data belong here. The [written reference portfolio](../docs/domain/REFERENCE_PORTFOLIO.md) informs the versioned synthetic examples below.

Do not copy real exports here to simplify adapter development. Actual portfolios and diagnostic reports must live outside the source repository. Do not redistribute proprietary index constituents, prices or risk datasets without verified rights.

The current browser accepts [advisory-workspace.json](synthetic/advisory-workspace.json), an invented normalized snapshot plus base64 original source bytes. It preserves `12.5000`, explicit missing basis/classification/acquisition facts, row locators and exclusions. It supports source diagnostics only; no financial readiness is claimed.

The [current history fixtures](synthetic/history/README.md) add reviewed fictional source responses, an explicit required window and independent return examples for reuse/manual refresh and current recovery. Old checkpoint/proof-format fixtures were retired; prior candidates remain in Git history.

The [fictional paper input package](synthetic/paper/README.md) adds 20/100/200-stock sleeves and a 500-name stylized U.S. large-cap benchmark, with exact weights, stipulated cash choices and explicit missing history/risk facts. The owner-supplied real market-reference sample is retained under ignored `.local/reference-data/`, not in authored examples. These CSVs are inspector inputs, not browser-importable checkpoints or qualified investment plans.

The [fictional Fidelity-shaped common-stock fixtures](synthetic/fidelity/README.md) add a combined eight-lot baseline, focused unknown/conflict/schema cases and simulated source records. They follow the owner's supplied combined-file structure under an explicit stock-format assumption. The source-shaped lot panel accepts the baseline CSV plus its checksum-bound current context and explicit settings documents for conditional fictional diagnostics. The [collection guide and reusable prompt](../docs/guides/FIDELITY_IMPORT.md) explain the original file's provenance and the retail browser/download workaround.

The [tiny checked candidate reference](synthetic/candidates/README.md) supplies a fictional two-name, fractional-holding, nine-state problem with explicit synthetic PSD covariance/settings and hand-derived feasible/best outcomes. Its Python request is separate from browser uploads and fitted investor risk. It preserves source locators, unknowns, screening, qualification and exact search-domain boundaries.

The [current application candidate fixture](synthetic/candidates/application/README.md) extends that reference through protected API/browser selection, complete compact 1,260-session two-name history, actual IDR fitting, checked bounded search and frozen recovery. Its declared limits and all-day calendar are fictional test inputs, not investor defaults or qualified market sources.
