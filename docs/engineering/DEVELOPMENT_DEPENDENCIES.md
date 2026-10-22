# T003.1 development dependency inventory

Observed October 22, 2026 from installed wheel metadata in both locked environments. All external packages came from public PyPI; [uv.lock](../../uv.lock) records exact versions and distribution SHA-256 hashes. Direct versions are pinned in [pyproject.toml](../../pyproject.toml). There are no Prosper runtime dependencies yet. This is inventory/qualification evidence for local development, not a license grant for Prosper, a legal audit, a vulnerability audit or release-distribution approval. D014 remains open. No third-party dependency source was modified or vendored.

| Distribution | Version | Role | Installed metadata license label |
| --- | --- | --- | --- |
| uv | 0.13.5 | Environment/lock orchestrator | MIT OR Apache-2.0 |
| Ruff | 0.17.2 | Lint/format | MIT |
| mypy | 2.4.0 | Strict checker | MIT |
| pytest | 9.1.1 | Test runner | MIT |
| Hypothesis | 6.170.5 | Synthetic property probes | MPL-2.0 |
| Hatchling | 1.32.4 | Build backend | MIT |
| ast_serialize | 0.13.1 | Checker dependency | MIT |
| colorama | 0.4.6 | Test terminal support | BSD License classifier; see bundled LICENSE.txt for exact text |
| iniconfig | 2.3.1 | Test configuration | MIT |
| librt | 0.16.0 | Checker dependency | MIT |
| mypy_extensions | 1.1.0 | Checker dependency | MIT |
| packaging | 26.3 | Build/test metadata | Apache-2.0 OR BSD-2-Clause |
| pathspec | 1.1.1 | Build file selection | MPL-2.0 classifier |
| pluggy | 1.7.0 | Test plugin framework | MIT |
| Pygments | 2.21.0 | Test diagnostic rendering | BSD-2-Clause |
| sortedcontainers | 2.4.0 | Property-test dependency | Apache 2.0 metadata/classifier |
| tomlkit | 0.15.2 | Tool dependency | MIT |
| trove-classifiers | 2026.9.21.13 | Build metadata | Apache Software License classifier |
| typing_extensions | 4.16.0 | Checker annotations | PSF-2.0 |

Metadata may omit a precise SPDX expression. The inventory preserves classifier-level uncertainty instead of upgrading it to a verified legal conclusion. `sortedcontainers` metadata did not declare a License-File entry; any future redistribution needs the applicable license texts/notices from authoritative distributions. The selected development baseline uses the already adopted Hypothesis and a minimal MIT build/checker stack, including the build backend's MPL-labeled path selector. No project license, new paid service or release commitment was selected.

The isolated tools bootstrap also contained ensurepip's pip 24.0; this was supplied by the existing Python installation and used only to install uv 0.13.5. It is not in the project environments or project lock. The existing Python/Git/PowerShell installations are prerequisites, not newly installed dependencies. Further backend/API/frontend packages enter only in their corresponding child tasks with updated qualification and rights inventory.
