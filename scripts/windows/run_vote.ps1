$ErrorActionPreference = "Stop"

Push-Location (Split-Path $PSScriptRoot -Parent | Split-Path -Parent)
try {
  $venvPython = Join-Path (Get-Location) ".venv\\Scripts\\python.exe"
  if (-not (Test-Path $venvPython)) {
    throw "Venv nao encontrado. Rode primeiro: scripts\\windows\\bootstrap.ps1"
  }
  & $venvPython vote.py
} finally {
  Pop-Location
}

