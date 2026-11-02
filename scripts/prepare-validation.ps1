$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$cacheRoot = Join-Path $projectRoot 'validation/cache'
New-Item -ItemType Directory -Force $cacheRoot | Out-Null
$corpusRoot = Join-Path $cacheRoot 'flac-test-files'
python (Join-Path $PSScriptRoot 'fetch-corpus.py')
if ($LASTEXITCODE -ne 0) { throw 'Corpus download failed' }
$flacExe = Join-Path $cacheRoot 'libflac/flac-1.5.0-win/Win64/flac.exe'
if (-not (Test-Path $flacExe)) {
    gh release download 1.5.0 -R xiph/flac -p flac-1.5.0-win.zip -D $cacheRoot
    if ($LASTEXITCODE -ne 0) { throw 'libFLAC download failed' }
    Expand-Archive -LiteralPath (Join-Path $cacheRoot 'flac-1.5.0-win.zip') -DestinationPath (Join-Path $cacheRoot 'libflac') -Force
}
& $flacExe --version
Get-Content (Join-Path $corpusRoot 'source.json') | ConvertFrom-Json | Select-Object sha
Get-FileHash -Algorithm SHA256 (Join-Path $cacheRoot 'flac-1.5.0-win.zip')
python (Join-Path $PSScriptRoot 'validate.py') generate
if ($LASTEXITCODE -ne 0) { throw 'Independent fixture generation failed' }
