param(
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

Push-Location (Split-Path $PSScriptRoot -Parent | Split-Path -Parent)
try {
  if (-not (Test-Path ".venv")) {
    & $Python -m venv .venv
  }

  $venvPython = Join-Path (Get-Location) ".venv\\Scripts\\python.exe"
  if (-not (Test-Path $venvPython)) {
    throw "Nao encontrei o python do venv em $venvPython"
  }

  & $venvPython -m pip install --upgrade pip
  & $venvPython -m pip install -r requirements.txt

  Write-Host "OK: ambiente pronto."
  Write-Host "Proximo passo:"
  Write-Host "  .\\.venv\\Scripts\\python.exe vote.py"
} finally {
  Pop-Location
}

