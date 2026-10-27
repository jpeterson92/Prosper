[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('bootstrap', 'sync', 'dev', 'test', 'docs', 'check', 'checkpoint', 'package')]
    [string]$Command,
    [string]$Python = 'python',
    [string]$Uv = 'uv',
    [ValidatePattern('^(auto|[0-9]+)$')]
    [string]$Workers = 'auto',
    [string[]]$TestPath = @(),
    [string]$PackagePath,
    [switch]$LastFailed,
    [switch]$ForceFull
)

$ErrorActionPreference = 'Stop'
$prosperSource = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$prosperEnvironment = Join-Path $prosperSource '.venv'
$prosperExecutable = Join-Path $prosperEnvironment 'Scripts\python.exe'
$prosperTools = Join-Path $prosperSource '.tools\uv'
$prosperLocalUv = Join-Path $prosperTools 'Scripts\uv.exe'

# One environment per checkout; never inherit another project's uv target.
$prosperOverrides = @{
    UV_PROJECT_ENVIRONMENT = $prosperEnvironment
    UV_PYTHON_DOWNLOADS = 'never'
}
$prosperPrevious = @{}
if ($PackagePath -and $Command -ne 'package') {
    throw 'PackagePath is restricted to package.'
}
if (($TestPath.Count -gt 0 -or $LastFailed) -and $Command -notin @('dev', 'test')) {
    throw 'TestPath/LastFailed are restricted to dev/test; full checkpoint checks cannot be narrowed.'
}
if ($ForceFull -and $Command -notin @('check', 'checkpoint')) {
    throw 'ForceFull is restricted to check/checkpoint.'
}
foreach ($prosperKey in $prosperOverrides.Keys) {
    $prosperPrevious[$prosperKey] = [Environment]::GetEnvironmentVariable($prosperKey, 'Process')
}
try {
    foreach ($prosperKey in $prosperOverrides.Keys) {
        [Environment]::SetEnvironmentVariable($prosperKey, $prosperOverrides[$prosperKey], 'Process')
    }
    Push-Location -LiteralPath $prosperSource
    try {
        if ($Command -eq 'bootstrap') {
            if ((Test-Path -LiteralPath $prosperTools) -and
                -not (Test-Path -LiteralPath (Join-Path $prosperTools 'pyvenv.cfg'))) {
                throw 'Existing .tools/uv is not a virtual environment.'
            }
            & $Python -m venv $prosperTools
            if ($LASTEXITCODE -ne 0) { throw 'uv tools environment creation failed.' }
            & (Join-Path $prosperTools 'Scripts\python.exe') -m pip --isolated --disable-pip-version-check install --only-binary=:all: --index-url https://pypi.org/simple uv==0.13.5
            if ($LASTEXITCODE -ne 0) { throw 'Pinned uv bootstrap failed.' }
            $Uv = $prosperLocalUv
        } elseif ($Uv -eq 'uv' -and (Test-Path -LiteralPath $prosperLocalUv)) {
            $Uv = $prosperLocalUv
        }

        if ($Command -in @('bootstrap', 'sync')) {
            & $Uv sync --locked --python $Python
            if ($LASTEXITCODE -ne 0) { throw "uv sync failed with exit $LASTEXITCODE." }
        } elseif ($Command -eq 'docs') {
            & $prosperExecutable scripts/check_project.py
            if ($LASTEXITCODE -ne 0) { throw 'Documentation checks failed.' }
            & git diff --check
            if ($LASTEXITCODE -ne 0) { throw 'Diff checks failed.' }
        } else {
            if (-not (Test-Path -LiteralPath $prosperExecutable)) { throw 'Run bootstrap or sync first.' }
            & $prosperExecutable -m uv sync --locked --offline --python $prosperExecutable
            if ($LASTEXITCODE -ne 0) { throw 'Offline locked sync failed; run sync first.' }
            if ($Command -in @('dev', 'check', 'checkpoint')) {
                & $prosperExecutable -m ruff check src tests scripts
                if ($LASTEXITCODE -ne 0) { throw 'Ruff lint failed.' }
                & $prosperExecutable -m ruff format --check src tests scripts
                if ($LASTEXITCODE -ne 0) { throw 'Ruff formatting failed.' }
                & $prosperExecutable -m mypy --config-file pyproject.toml
                if ($LASTEXITCODE -ne 0) { throw 'Strict mypy failed.' }
            }
            if ($Command -in @('dev', 'test', 'check', 'checkpoint')) {
                $prosperTestMode = 'affected'
                if ($TestPath.Count -gt 0 -or $LastFailed) { $prosperTestMode = 'selected' }
                if ($Command -in @('check', 'checkpoint')) { $prosperTestMode = 'full' }
                if ($LastFailed -and $TestPath.Count -eq 0) {
                    throw 'LastFailed requires explicit TestPath so its scope is reviewable.' }
                $prosperTestArgs = @('scripts/run_tests.py', '--mode', $prosperTestMode,
                    '--workers', [string]$Workers)
                if ($LastFailed) { $prosperTestArgs += '--last-failed' }
                if ($ForceFull) { $prosperTestArgs += '--force' }
                $prosperTestArgs += $TestPath
                & $prosperExecutable @prosperTestArgs
                if ($LASTEXITCODE -ne 0) { throw 'Scoped/full pytest verification failed; inspect the runner message and reports.' }
            }
            if ($Command -in @('dev', 'check', 'checkpoint')) {
                & $prosperExecutable scripts/check_project.py
                if ($LASTEXITCODE -ne 0) { throw 'Project structure checks failed.' }
            }
            if ($Command -in @('package', 'checkpoint')) {
                # A fresh wheel-only environment catches src-layout/package omissions.
                $prosperProbe = Join-Path $prosperSource ('.local\package-check\' + [Guid]::NewGuid().ToString('N'))
                if ($PackagePath) {
                    # Reuse the installed runtime path rather than copying a venv.
                    $prosperProbe = $PackagePath
                    & $prosperExecutable -c "import sys; from pathlib import Path; from prosper.storage import RuntimeBoundary; p=Path(sys.argv[1]); RuntimeBoundary(p); sys.exit('Package destination already exists') if p.exists() else None" $prosperProbe $prosperSource
                    if ($LASTEXITCODE -ne 0) { throw 'Fresh local package destination required.' }
                }
                & $prosperExecutable -m uv build --wheel --offline --out-dir (Join-Path $prosperProbe 'dist')
                if ($LASTEXITCODE -ne 0) { throw 'Wheel build failed.' }
                & $prosperExecutable -m uv venv --python $prosperExecutable (Join-Path $prosperProbe '.venv')
                if ($LASTEXITCODE -ne 0) { throw 'Wheel probe environment creation failed.' }
                $prosperWheels = @(Get-ChildItem -LiteralPath (Join-Path $prosperProbe 'dist') -Filter '*.whl')
                if ($prosperWheels.Count -ne 1) { throw 'Expected exactly one built wheel.' }
                $prosperProbePython = Join-Path $prosperProbe '.venv\Scripts\python.exe'
                # Qualify exact locked runtime dependencies without installing editable Prosper.
                $prosperPriorTarget = $env:UV_PROJECT_ENVIRONMENT
                $prosperPriorVirtual = $env:VIRTUAL_ENV
                try {
                    $env:UV_PROJECT_ENVIRONMENT = Join-Path $prosperProbe '.venv'
                    $env:VIRTUAL_ENV = Join-Path $prosperProbe '.venv'
                    & $prosperExecutable -m uv sync --locked --offline --no-dev --no-install-project --python $prosperProbePython
                    if ($LASTEXITCODE -ne 0) { throw 'Locked runtime dependency installation failed.' }
                } finally {
                    $env:UV_PROJECT_ENVIRONMENT = $prosperPriorTarget
                    $env:VIRTUAL_ENV = $prosperPriorVirtual
                }
                & $prosperExecutable -m uv pip install --offline --no-deps --python $prosperProbePython $prosperWheels[0].FullName
                if ($LASTEXITCODE -ne 0) { throw 'Wheel install failed.' }
                & $prosperExecutable -m uv pip check --python $prosperProbePython
                if ($LASTEXITCODE -ne 0) { throw 'Wheel runtime dependency check failed.' }
                Push-Location -LiteralPath $prosperProbe
                try {
                    & $prosperProbePython -I -c "import sys, prosper; from pathlib import Path; from importlib.metadata import version; p = Path(prosper.__file__).resolve(); assert p.is_relative_to(Path(sys.prefix).resolve()), p; assert p.with_name('py.typed').is_file(); print('Wheel import OK:', version('prosper-local'), p)"
                    if ($LASTEXITCODE -ne 0) { throw 'Wheel import failed.' }
                } finally { Pop-Location }
            }
        }
    } finally { Pop-Location }
} finally {
    foreach ($prosperKey in $prosperOverrides.Keys) {
        [Environment]::SetEnvironmentVariable($prosperKey, $prosperPrevious[$prosperKey], 'Process')
    }
}
