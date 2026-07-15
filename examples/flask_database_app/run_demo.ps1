param([string]$Python = "python")

$ErrorActionPreference = "Stop"
$demoRoot = $PSScriptRoot
$repoRoot = Resolve-Path (Join-Path $demoRoot "..\..")
$venvRoot = Join-Path $demoRoot ".venv-demo"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    & $Python -m venv $venvRoot
}

& $venvPython -m pip install `
    -e "$repoRoot\packages\slim_report_core[mysql,sqlalchemy]" `
    -e "$repoRoot\packages\slim_report_designer_ui" `
    -e "$repoRoot\packages\slim_report_flask[database]" `
    -r (Join-Path $demoRoot "requirements.txt")

& $venvPython (Join-Path $demoRoot "app.py")
