$ErrorActionPreference = 'Stop'
$python = Join-Path (Split-Path -Parent $PSScriptRoot) '.venv/Scripts/python.exe'
& $python $PSScriptRoot/check_product.py
if ($LASTEXITCODE -ne 0) { throw 'Product checks failed' }
