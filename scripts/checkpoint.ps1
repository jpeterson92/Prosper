[CmdletBinding()]
param(
    [ValidatePattern('^(auto|[0-9]+)$')]
    [string]$Workers = 'auto',
    [ValidateRange(1, 256)]
    [int]$BrowserWorkers = 4,
    [switch]$ForceFull
)
$ErrorActionPreference = 'Stop'

# Each helper completes before the next starts. Neither stage accepts a test filter.
$prosperPythonArgs = @{ Command = 'checkpoint'; Workers = $Workers }
if ($ForceFull) { $prosperPythonArgs.ForceFull = $true }
Write-Output 'Checkpoint 1/2: full Python checks and package qualification.'
& (Join-Path $PSScriptRoot 'dev.ps1') @prosperPythonArgs
Write-Output 'Checkpoint 2/2: full frontend checks and browser suite.'
& (Join-Path $PSScriptRoot 'frontend.ps1') -Command check -Workers $BrowserWorkers
