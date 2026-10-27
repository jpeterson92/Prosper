[CmdletBinding()]
param(
    [ValidateSet('initialize', 'start')]
    [string]$Command = 'start',
    [Parameter(Mandatory = $true)]
    [string]$Workspace
)
$ErrorActionPreference = 'Stop'
$prosperPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $prosperPython -PathType Leaf)) {
    throw 'Installed Python is missing. Rebuild the artifact; do not reset your workspace.'
}
# Keep the console visible for the public local URL and Ctrl+C shutdown. No
# tokens, runtime paths or saved portfolio facts are written to launcher logs.
$prosperArgs = @('-I', '-m', 'prosper.launch', $Command, '--artifact', $PSScriptRoot, '--workspace', $Workspace)
& $prosperPython @prosperArgs
if ($LASTEXITCODE -ne 0) { throw 'Local launch refused. Existing workspace was not reset.' }
