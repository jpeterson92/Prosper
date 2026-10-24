# Dependency inventory: development baseline and synthetic parser

## Parallel and affected test tooling

Owner-directed October 24 implementation adds development-only pytest-xdist **3.8.0** (MIT), pytest-testmon **2.2.0** (MIT installed License field/text), execnet **2.1.2** (MIT), and coverage **7.17.0** (Apache-2.0 installed field/text/notices). Pytest remains **9.1.1**; testmon declares pytest >=5,<10 and coverage >=6,<8, while xdist declares pytest >=7 and execnet >=2.1. The locked development environment has 39 distributions including Prosper. The isolated wheel runtime remains 17 and excludes these four development tools. No existing dependency version changed and no cloud test service/extras were added. Metadata/license observations are inventory rather than a security/legal audit or Prosper distribution-license decision. [Workflow evidence](../tasks/TEST_WORKFLOW.md) records actual compatibility and targeted qualification; initial full Prosper testmon/parallel qualification is deferred to the next authorized checkpoint.

## Original development baseline

Observed October 22, 2026 from installed wheel metadata in both locked environments. All external packages came from public PyPI; [uv.lock](../../uv.lock) records exact versions and distribution SHA-256 hashes. Direct versions are pinned in [pyproject.toml](../../pyproject.toml). The original T003.1 table below is retained; the later T004.1.1 runtime qualification is recorded separately after it. This is inventory/qualification evidence for local development, not a license grant for Prosper, a legal audit, a vulnerability audit or release-distribution approval. D014 remains open. No third-party dependency source was modified or vendored.

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

## T003.4.1 local API runtime qualification

Observed October 23, 2026 on CPython 3.12.4 Windows x64. FastAPI is the adopted API direction; minimal Uvicorn supplies the actual local h11/asyncio process. Direct versions are pinned, transitive versions/hashes are locked. No standard extras, frontend, SDK or telemetry exporter were installed. Nine new external distributions bring the development environment to 33 distributions including Prosper, and the wheel runtime to 15 including Prosper. These installed license labels are metadata evidence, not a legal/security audit or public distribution/license commitment; D014/D016 remain open.

| Distribution | Exact version | Role | Installed license metadata |
| --- | --- | --- | --- |
| fastapi | 0.161.1 | Adopted typed API | MIT expression |
| uvicorn | 0.54.0 | Minimal local ASGI server | BSD-3-Clause expression |
| starlette | 1.9.0 | Required ASGI routing/lifecycle | BSD-3-Clause expression |
| anyio | 4.15.1 | Required async framework | MIT expression |
| annotated-doc | 0.0.5 | Required annotation metadata | MIT expression |
| click | 8.5.0 | Server dependency | BSD-3-Clause expression |
| h11 | 0.16.0 | Explicit HTTP/1.1 protocol | MIT classifier; no License-Expression |
| idna | 3.20 | Required identifier codec | BSD-3-Clause expression |
| opentelemetry-api | 1.45.1 | FastAPI required API dependency | Apache-2.0 expression |

FastAPI/Uvicorn public metadata declares Python >=3.10. Installed metadata labels Starlette and h11 Alpha and FastAPI/Uvicorn Beta; functional local qualification is bounded to this exact lock and host, not a maturity/security certification. FastAPI's required telemetry API does not imply an exporter; the application explicitly disables automatic configuration/tracing/metrics/logs, including when `FASTAPI_OTEL_AUTO_CONFIGURE=true` is inherited. Existing exact Pydantic versions remain unchanged. [PyPI FastAPI metadata](https://pypi.org/pypi/fastapi/0.161.1/json), [Uvicorn metadata](https://pypi.org/pypi/uvicorn/0.54.0/json), [official origin guidance](https://fastapi.tiangolo.com/tutorial/cors/) and installed server/framework source informed qualification. No package source was modified or vendored. [Task evidence](../tasks/T003.4.1-loopback-runtime.md) records the actual check/package results.

## T004.1.1 runtime schema qualification

Observed October 22, 2026 on the same CPython 3.12.4 Windows x64 development host. Pydantic is the already adopted schema direction, introduced only when implementing real typed bundle models. Public PyPI metadata reported Pydantic 2.14.1 supporting Python >=3.10; project installation, strict typing, generic Fact/ExactValue validators, JSON-schema generation and the fresh wheel runtime check were exercised. No timezone/email extras, FastAPI or frontend packages were installed. All four newly introduced distributions declare MIT in installed License-Expression metadata; this inventory does not establish a legal/vulnerability audit or select Prosper's license.

| Distribution | Pinned/locked version | Role | Installed License-Expression |
| --- | --- | --- | --- |
| pydantic | 2.14.1 | Direct runtime schema/validation dependency | MIT |
| pydantic-core | 2.50.1 | Required compiled validation runtime, exercised on Windows x64 | MIT |
| annotated-types | 0.8.0 | Required schema annotation dependency | MIT |
| typing-inspection | 0.4.4 | Required typing introspection | MIT |
| typing_extensions | 4.16.0 | Existing baseline package, now also a runtime dependency | PSF-2.0 |

The full development environment now has 24 locked distributions including Prosper; a fresh wheel environment contains Prosper plus these five runtime distributions. uv.lock retains exact distribution hashes. The helper syncs locked runtime packages offline into its fresh environment before installing the wheel and checking metadata compatibility. The initial require-hashes requirements-export approach could not reuse the existing offline compiled-wheel cache and was replaced by uv's actual locked sync path; the passing command is the one recorded here. No new package source was vendored or modified. Version/license observations came from [public PyPI metadata](https://pypi.org/pypi/pydantic/2.14.1/json) and installed wheel metadata. Qualification covers this observed developer configuration; no investor installer or broader OS claim is made.

## T006.2.1.2 numerical stack qualification

Observed October 24, 2026 on Windows 11 build 22635/AMD64, CPython 3.12.4. The [owning report](../tasks/T006.2.1.2-python-stack-reference.md) records executable primitive/reference results and package qualification. Direct runtime pins are NumPy **2.5.4** and SciPy **1.18.1**, with distribution hashes in `uv.lock`. Official [NumPy metadata](https://pypi.org/pypi/numpy/2.5.4/json) declares Python >=3.12; [SciPy metadata](https://pypi.org/pypi/scipy/1.18.1/json) declares Python >=3.12 and NumPy >=2.0.0,<2.8. Only these two distributions were added; no extras, `arch`, stubs, accelerator or MATLAB deployment. Existing dependency versions are unchanged.

Installed NumPy metadata declares `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0`; SciPy supplies BSD redistribution text rather than a precise License-Expression. Both Windows wheels retain bundled notices for OpenBLAS (BSD-3-Clause), LAPACK (BSD-3-Clause-Open-MPI) and GCC runtime (`GPL-3.0-or-later WITH GCC-exception-3.1`). Preserve the complete wheel notices for future distribution review. These observations are an inventory, not a license/legal/security audit or Prosper distribution-license selection; D014/D016 remain open. NumPy records OpenBLAS 0.3.34.106.0 ILP64/Haswell, SciPy OpenBLAS 0.3.31.dev LP64/SkylakeX; their upstream build paths are build metadata, not local build tools or newly installed compilers. Full structured configurations and installed METADATA/WHEEL/RECORD hashes are retained in generated evidence.

## T004.4.1.1 frontend and browser qualification

The [browser-client execution report](../tasks/T004.4.1.1-browser-client.md#tools-dependency-observations-and-compatibility-findings) records exact Node/npm, React, TypeScript, Vite, generator/fetch client and Playwright/browser versions, installed license metadata, observed footprint and compatibility findings. `frontend/package-lock.json` retains exact package versions/integrity and platform alternatives; 58 packages were installed on the observed Windows host. Runtime frontend libraries are MIT-declared; tool dependencies also include Apache-2.0 and unmodified development-only MPL-2.0 lightningcss/binding, plus the other strings listed in that report. npm audit returned zero known advisories at qualification, not independent security/legal acceptance. No package source was modified or vendored, browser distribution is separate, and public release/license/notice decisions remain open. [Frontend instructions](../../frontend/README.md) own exercised bootstrap/check/build commands and runtime configuration.
