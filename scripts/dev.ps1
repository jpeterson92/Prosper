[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('bootstrap', 'sync', 'check', 'package')]
    [string]$Command,
    [string]$Python = 'python',
    [string]$Uv = 'uv'
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
        } else {
            if (-not (Test-Path -LiteralPath $prosperExecutable)) { throw 'Run bootstrap or sync first.' }
            & $prosperExecutable -m uv sync --locked --offline --python $prosperExecutable
            if ($LASTEXITCODE -ne 0) { throw 'Offline locked sync failed; run sync first.' }
            if ($Command -eq 'check') {
                & $prosperExecutable -m ruff check src tests scripts
                if ($LASTEXITCODE -ne 0) { throw 'Ruff lint failed.' }
                & $prosperExecutable -m ruff format --check src tests scripts
                if ($LASTEXITCODE -ne 0) { throw 'Ruff formatting failed.' }
                & $prosperExecutable -m mypy --config-file pyproject.toml
                if ($LASTEXITCODE -ne 0) { throw 'Strict mypy failed.' }
                $prosperTestTemp = Join-Path $prosperSource ('.local\pytest\' + [Guid]::NewGuid().ToString('N'))
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $prosperTestTemp) | Out-Null
                & $prosperExecutable -m pytest --basetemp $prosperTestTemp
                if ($LASTEXITCODE -ne 0) { throw 'pytest qualification failed.' }
                & $prosperExecutable scripts/check_project.py
                if ($LASTEXITCODE -ne 0) { throw 'Project structure checks failed.' }
            } else {
                # A fresh wheel-only environment catches src-layout/package omissions.
                $prosperProbe = Join-Path $prosperSource ('.local\package-check\' + [Guid]::NewGuid().ToString('N'))
                & $prosperExecutable -m uv build --wheel --offline --out-dir (Join-Path $prosperProbe 'dist')
                if ($LASTEXITCODE -ne 0) { throw 'Wheel build failed.' }
                & $prosperExecutable -m uv venv --python $prosperExecutable (Join-Path $prosperProbe '.venv')
                if ($LASTEXITCODE -ne 0) { throw 'Wheel probe environment creation failed.' }
                $prosperWheels = @(Get-ChildItem -LiteralPath (Join-Path $prosperProbe 'dist') -Filter '*.whl')
                if ($prosperWheels.Count -ne 1) { throw 'Expected exactly one built wheel.' }
                $prosperProbePython = Join-Path $prosperProbe '.venv\Scripts\python.exe'
                & $prosperExecutable -m uv pip install --offline --no-deps --python $prosperProbePython $prosperWheels[0].FullName
                if ($LASTEXITCODE -ne 0) { throw 'Wheel install failed.' }
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
