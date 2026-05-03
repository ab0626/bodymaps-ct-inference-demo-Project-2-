<#
 Runs pytest without loading stray third‑party pytest entry points from the global site-packages
 (e.g. broken web3 / ethereum plugins).

 Usage (from backend/):

   powershell -ExecutionPolicy Bypass -File .\scripts\run_tests.ps1
#>
$ErrorActionPreference = "Stop"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
python -m pip install -r requirements-dev.txt -q
Push-Location $PSScriptRoot\..
python -m pytest tests -v --tb=short
exit $LASTEXITCODE
