[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('bootstrap', 'sync', 'check', 'build', 'contracts', 'dev')]
    [string]$Command
)
$ErrorActionPreference = 'Stop'
$prosperRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$prosperTools = Join-Path $prosperRoot '.tools'
$prosperNodeFolder = Join-Path $prosperTools 'node-v24.22.1-win-x64'
$prosperNode = Join-Path $prosperNodeFolder 'node.exe'
$prosperNpm = Join-Path $prosperNodeFolder 'node_modules/npm/bin/npm-cli.js'
if ($Command -eq 'bootstrap' -and -not (Test-Path -LiteralPath $prosperNode)) {
    $prosperDownload = Join-Path $prosperTools 'node-download'
    New-Item -ItemType Directory -Force -Path $prosperDownload | Out-Null
    $prosperArchive = Join-Path $prosperDownload 'node-v24.22.1-win-x64.zip'
    Invoke-WebRequest -UseBasicParsing 'https://nodejs.org/dist/v24.22.1/node-v24.22.1-win-x64.zip' -OutFile $prosperArchive
    if ((Get-FileHash -LiteralPath $prosperArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'd2046d28c2c3dcd211ac5145c0bf30e2047ef9dfb306693c8c6e2eccd8b95fa5') {
        throw 'Node archive checksum mismatch.'
    }
    Expand-Archive -LiteralPath $prosperArchive -DestinationPath $prosperTools
}
if (-not (Test-Path -LiteralPath $prosperNode)) { throw 'Run frontend bootstrap first.' }
if ((& $prosperNode --version) -ne 'v24.22.1') { throw 'Unexpected project Node version.' }
$prosperPreviousPath = $env:PATH
try {
    $env:PATH = $prosperNodeFolder + ';' + $env:PATH
    Push-Location -LiteralPath (Join-Path $prosperRoot 'frontend')
    try {
        if ($Command -in @('bootstrap', 'sync')) {
            & $prosperNode $prosperNpm ci --ignore-scripts --no-audit --no-fund
            if ($LASTEXITCODE -ne 0) { throw 'Locked frontend installation failed.' }
            if ($Command -eq 'bootstrap') {
                & $prosperNode 'node_modules/@playwright/test/cli.js' install chromium
                if ($LASTEXITCODE -ne 0) { throw 'Chromium installation failed.' }
            }
        } elseif ($Command -eq 'check') {
            foreach ($prosperStep in @('contracts:check', 'contracts:negative', 'build', 'test')) {
                & $prosperNode $prosperNpm run $prosperStep
                if ($LASTEXITCODE -ne 0) { throw "Frontend $prosperStep failed." }
            }
        } elseif ($Command -eq 'contracts') {
            & $prosperNode $prosperNpm run contracts:write
            if ($LASTEXITCODE -ne 0) { throw 'Contract generation failed.' }
        } else {
            & $prosperNode $prosperNpm run $Command
            if ($LASTEXITCODE -ne 0) { throw "Frontend $Command failed." }
        }
    } finally { Pop-Location }
} finally { $env:PATH = $prosperPreviousPath }
