param(
  [string]$Date = (Get-Date -Format 'yyyyMMdd'),
  [string]$Root = 'C:\MAGI\KEIBA\REALTIME',
  [string]$Sid = 'MAGI_KEIBA_RT_V5'
)

$ErrorActionPreference = 'Stop'
$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) { $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$Current = Join-Path $ScriptDir 'keiba_jvlink_first_capture_v2.ps1'
if (-not (Test-Path $Current)) {
  Write-Host '[FAIL] Current Gate v5 launcher script is missing.' -ForegroundColor Red
  exit 2
}
Write-Host '[INFO] Legacy entrypoint redirected to current Gate v5 first-capture flow.' -ForegroundColor Yellow
& $Current -Date $Date -Root $Root -Sid $Sid
exit $LASTEXITCODE
