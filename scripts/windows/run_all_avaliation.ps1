param(
  [string]$Instances = "1,2,3,4",
  [switch]$NewWindows
)

$ErrorActionPreference = "Stop"

Push-Location (Split-Path $PSScriptRoot -Parent | Split-Path -Parent)
try {
  $runScript = Join-Path (Get-Location) "scripts\\windows\\run_avaliation.ps1"
  if (-not (Test-Path $runScript)) {
    throw "Nao encontrei: $runScript"
  }

  $ids = $Instances.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" } | ForEach-Object { [int]$_ }
  $totalInstances = $ids.Count

  foreach ($id in $ids) {
    if ($id -le 0) { throw "INSTANCE_ID invalido: $id" }

    if ($NewWindows) {
      $cmd = "`$env:INSTANCE_ID=$id; `$env:INSTANCES_TOTAL=$totalInstances; `$env:WINDOW_COLUMNS=$totalInstances; & '$runScript'"
      Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-NoExit",
        "-Command", $cmd
      ) | Out-Null
    } else {
      Start-Job -Name "avaliation_$id" -ScriptBlock {
        param($instanceId, $scriptPath, $instancesTotal)
        $env:INSTANCE_ID = "$instanceId"
        $env:INSTANCES_TOTAL = "$instancesTotal"
        $env:WINDOW_COLUMNS = "$instancesTotal"
        & $scriptPath
      } -ArgumentList $id, $runScript, $totalInstances | Out-Null
    }
  }

  if (-not $NewWindows) {
    Write-Host "Jobs iniciados: $($ids -join ', ')"
    Write-Host "Ver logs: Receive-Job -Name avaliation_1 -Keep"
    Write-Host "Parar: Stop-Job -Name avaliation_1"
  }
} finally {
  Pop-Location
}
