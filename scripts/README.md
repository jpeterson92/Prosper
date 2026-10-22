# Future development tooling

`dev.ps1` provides `bootstrap`, `sync`, `check` and `package` operations for the Python baseline; `check_project.py` validates authored text, local links and the supplemental manifest. See the [development guide](../docs/engineering/DEVELOPMENT.md) for arguments, exact versions and network/write behavior. It uses project-local `.venv` and `.tools/uv`, normal tool caches and ignored synthetic package-probe output. It restores its two process-environment overrides on success/failure. No system-wide runtime or global setting is changed.

A future read-only environment diagnostic should verify prerequisites without installing software, changing credentials or reading real portfolios. Build/test commands should be reproducible and synthetic-only. Release, migration and brokerage operations need separate explicit scope.
