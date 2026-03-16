param(
  [string]$Instances = "1,2,3",
  [switch]$NewWindows
)

$ErrorActionPreference = "Stop"

Push-Location (Split-Path $PSScriptRoot -Parent | Split-Path -Parent)
try {
  $runScript = Join-Path (Get-Location) "scripts\\windows\\run_vote.ps1"
  if (-not (Test-Path $runScript)) {
    throw "Nao encontrei: $runScript"
  }

  $ids = $Instances.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" } | ForEach-Object { [int]$_ }

  foreach ($id in $ids) {
    if ($id -le 0) { throw "INSTANCE_ID invalido: $id" }

    if ($NewWindows) {
      $cmd = "`$env:INSTANCE_ID=$id; & '$runScript'"
      Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-NoExit",
        "-Command", $cmd
      ) | Out-Null
    } else {
      Start-Job -Name "vote_$id" -ScriptBlock {
        param($instanceId, $scriptPath)
        $env:INSTANCE_ID = "$instanceId"
        & $scriptPath
      } -ArgumentList $id, $runScript | Out-Null
    }
  }

  if (-not $NewWindows) {
    Write-Host "Jobs iniciados: $($ids -join ', ')"
    Write-Host "Ver logs: Receive-Job -Name vote_1 -Keep"
    Write-Host "Parar: Stop-Job -Name vote_1"
  }
} finally {
  Pop-Location
}