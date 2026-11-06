$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    if (Test-Path .sentrux/baseline.json) { sentrux gate . } else { sentrux gate --save . }
    if ($LASTEXITCODE -ne 0) { throw 'Sentrux preflight failed' }
    if (Test-Path .sentrux/rules.toml) { sentrux check .; if ($LASTEXITCODE -ne 0) { throw 'Sentrux rules failed' } }
} finally { Pop-Location }
