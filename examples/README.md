# Future synthetic examples

Only invented portfolios, fictional account aliases and permitted data belong here. The [written reference portfolio](../docs/domain/REFERENCE_PORTFOLIO.md) informs the versioned synthetic examples below.

Do not copy real exports here to simplify adapter development. Actual portfolios and diagnostic reports must live outside the source repository. Do not redistribute proprietary index constituents, prices or risk datasets without verified rights.

T004.1.1 materializes [F000](synthetic/F000.json) and [F001](synthetic/F001.json) as fictional `synthetic-checkpoint-v1` bundles. [Execution evidence](../docs/tasks/T004.1.1-synthetic-bundle-parsing.md) documents schema, fingerprints and intentional prior-checkpoint unknowns. Parsing them establishes no financial reconciliation or planning readiness.

The [fictional paper input package](synthetic/paper/README.md) adds 20/100/200-stock sleeves and a 500-name stylized U.S. large-cap benchmark, with exact weights, stipulated cash choices and explicit missing history/risk facts. The owner-supplied real market-reference sample is retained under ignored `.local/reference-data/`, not in authored examples. These CSVs are inspector inputs, not browser-importable checkpoints or qualified investment plans.

The [fictional Fidelity-shaped common-stock fixtures](synthetic/fidelity/README.md) add a combined eight-lot baseline, focused unknown/conflict/schema cases and simulated source records. They follow the owner's supplied combined-file structure under an explicit stock-format assumption. They are future CSV mapping/test inputs; the current JSON importer does not accept them. The [collection guide and reusable prompt](../docs/guides/FIDELITY_IMPORT.md) explain the original file's provenance and the retail browser/download workaround.
