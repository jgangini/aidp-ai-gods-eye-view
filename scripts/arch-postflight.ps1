$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    & $PSScriptRoot/test.ps1
    if ($LASTEXITCODE -ne 0) { throw 'Product checks failed' }
    sentrux gate .
    if ($LASTEXITCODE -ne 0) { throw 'Sentrux postflight failed' }
    if (Test-Path .sentrux/rules.toml) { sentrux check .; if ($LASTEXITCODE -ne 0) { throw 'Sentrux rules failed' } } else { Write-Output 'Sentrux custom rules: not configured' }
    if (Test-Path graphify-out/GRAPH_REPORT.md) { graphify update .; if ($LASTEXITCODE -ne 0) { throw 'Graphify update failed' } }
} finally { Pop-Location }
