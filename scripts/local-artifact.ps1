[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')]
    [string]$Name
)
$ErrorActionPreference = 'Stop'
$prosperRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$prosperArtifact = Join-Path $prosperRoot ('.local/artifacts/' + $Name)
if (Test-Path -LiteralPath $prosperArtifact) { throw 'Artifact exists. Choose a fresh name.' }
& (Join-Path $PSScriptRoot 'frontend.ps1') -Command build
& (Join-Path $PSScriptRoot 'dev.ps1') -Command package -PackagePath $prosperArtifact
Copy-Item -LiteralPath (Join-Path $prosperRoot 'frontend/dist') -Destination (Join-Path $prosperArtifact 'ui') -Recurse
Copy-Item -LiteralPath (Join-Path $prosperRoot 'apps/Launch.ps1') -Destination $prosperArtifact
Copy-Item -LiteralPath (Join-Path $prosperRoot 'docs/guides/LOCAL_ARTIFACT.md') -Destination (Join-Path $prosperArtifact 'README.md')
$prosperPython = Join-Path $prosperArtifact '.venv/Scripts/python.exe'
# Write readiness last. This manifest describes this artifact, never determines
# compatibility with saved financial records. No source-code-hash data contract.
& $prosperPython -I -c "import hashlib,json,platform,sys; from pathlib import Path; from importlib.metadata import distributions; from prosper.web_assets import WebAssets; p=Path(sys.argv[1]); WebAssets.load(p/'ui'); d={'kind':'prosper-local-v1','ready':True,'name':sys.argv[2],'python':sys.version,'windows':platform.version(),'machine':platform.machine(),'packages':sorted((x.metadata['Name'],x.version) for x in distributions()),'wheel_sha256':hashlib.sha256(next((p/'dist').glob('*.whl')).read_bytes()).hexdigest(),'assets':{str(x.relative_to(p/'ui')):hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted((p/'ui').rglob('*')) if x.is_file()}}; (p/'artifact.json').write_text(json.dumps(d,indent=2)+'\n',encoding='utf8')" $prosperArtifact $Name
if ($LASTEXITCODE -ne 0) { throw 'Artifact finalization failed. Existing workspaces were not changed.' }
Write-Output "Local artifact ready: $prosperArtifact"
Write-Output 'Use Launch.ps1 with an explicit separate Workspace; see its README.md.'
