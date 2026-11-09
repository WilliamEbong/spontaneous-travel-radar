# PC fallback: run the daily scan from this PC if Google starts blocking GitHub Actions IPs.
# Not registered by default (the day-one block test passed on Actions). To switch hosts:
#   1. In .github/workflows/scan.yml delete the `schedule:` trigger (keep workflow_dispatch and push).
#   2. Add "data/**" to the push `paths:` list so each PC push redeploys Pages.
#   3. Register this script (PowerShell, from the repo root):
#      schtasks /Create /SC DAILY /ST 04:30 /TN "SpontaneousTravelRadar" /TR "powershell -ExecutionPolicy Bypass -File \"$PWD\scripts\run-scan.ps1\""
# radar.main loads SERPAPI_KEY from .env itself.
Set-Location (Split-Path $PSScriptRoot -Parent)
.\.venv\Scripts\python.exe -m radar.main scan
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
git add data hits
git commit -m "chore: data scan $(Get-Date -Format yyyy-MM-dd) (pc)"
git pull --rebase
git push
