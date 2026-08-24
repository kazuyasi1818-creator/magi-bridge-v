param(
  [string]$Date = (Get-Date -Format 'yyyyMMdd'),
  [string]$Root = 'C:\MAGI\KEIBA\REALTIME',
  [string]$Sid = 'MAGI_KEIBA_RT_V5'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red; exit 2 }

$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) { $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$Collector = Join-Path $ScriptDir 'keiba_jvlink_realtime_capture_v3.py'
$Verifier = Join-Path $ScriptDir 'keiba_verify_first_capture_v2.py'
$HandoffMaker = Join-Path $ScriptDir 'keiba_make_capture_handoff_v2.py'

Write-Host "=== KEIBA JV-Link first forward capture / Gate v5 semantics ==="
Write-Host "Date: $Date"
Write-Host "Root: $Root"
if ($env:OS -ne 'Windows_NT') { Fail 'Windows is required for JV-Link.' }
if ($Date -notmatch '^\d{8}$') { Fail '-Date must be YYYYMMDD.' }
foreach ($p in @($Collector,$Verifier,$HandoffMaker)) { if (-not (Test-Path $p)) { Fail "required script missing: $p" } }
if (-not (Get-Command py.exe -ErrorAction SilentlyContinue)) { Fail 'Python launcher not found. Python 3.14 x64 is required for the preferred official route.' }

& py -3.14 -c "import sys,platform; assert sys.maxsize > 2**32; import win32com.client,pythoncom; jv=win32com.client.Dispatch('JVDTLab.JVLink'); print(sys.version); print(platform.platform()); print('JV-Link COM OK')"
if ($LASTEXITCODE -ne 0) { Fail 'Python 3.14 x64 / pywin32 / 64-bit JV-Link COM is not ready.' }

New-Item -ItemType Directory -Force -Path $Root | Out-Null
$clockDir = Join-Path $Root 'LOG'; New-Item -ItemType Directory -Force -Path $clockDir | Out-Null
$clockFile = Join-Path $clockDir ("clock_audit_" + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.json')
$tz = [System.TimeZoneInfo]::Local
@{
  recorded_at_local=(Get-Date).ToString('o')
  recorded_at_utc=(Get-Date).ToUniversalTime().ToString('o')
  timezone_id=$tz.Id
  utc_offset=(Get-Date).ToString('zzz')
  computer_name=$env:COMPUTERNAME
  date_key=$Date
  gate_contract='KEIBA_PRE_RACE_SNAPSHOT_CONTRACT_V5'
  provenance_builder='keiba_build_snapshot_provenance_v4.py'
  gate_checker='keiba_snapshot_gate_check_v5.py'
  verifier='keiba_verify_first_capture_v2.py'
  handoff_maker='keiba_make_capture_handoff_v2.py'
} | ConvertTo-Json | Set-Content -Encoding UTF8 $clockFile

Write-Host '[1/4] Capturing official 0B11 / 0B14 once...'
& py -3.14 $Collector --date $Date --root $Root --sid $Sid --once
if ($LASTEXITCODE -ne 0) { Fail "collector exited $LASTEXITCODE" }

Write-Host '[2/4] Verifying current-run append-only raw bytes / SHA / JV status...'
$reportPath = Join-Path $clockDir ("first_capture_verify_" + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.json')
& py -3.14 $Verifier --root $Root --date $Date --clock-file $clockFile --out $reportPath
$verifyExit = $LASTEXITCODE

Write-Host '[3/4] Creating Gate-v5 redacted handoff JSON (no raw JV-Data values)...'
$handoffDir = Join-Path $Root 'HANDOFF'; New-Item -ItemType Directory -Force -Path $handoffDir | Out-Null
$handoffPath = Join-Path $handoffDir ("KEIBA_REAL_CAPTURE_HANDOFF_" + $Date + '_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.json')
& py -3.14 $HandoffMaker --root $Root --date $Date --out $handoffPath
if ($LASTEXITCODE -ne 0) { Fail "handoff generator exited $LASTEXITCODE" }
try {
  $handoffObj = Get-Content -Raw $handoffPath | ConvertFrom-Json
  if (-not $handoffObj.gate_v5_lineage_verified) { Fail 'Handoff does not prove Gate v5 lineage.' }
  if ($handoffObj.raw_jvdata_included -or $handoffObj.parsed_feature_values_included) { Fail 'Redacted handoff unexpectedly includes prohibited data.' }
} catch {
  Fail "handoff validation failed: $($_.Exception.Message)"
}

Write-Host '[4/4] Result'; Get-Content $reportPath
Write-Host ''
Write-Host "Handoff file to send ChatGPT: $handoffPath" -ForegroundColor Cyan
Write-Host 'RAW_APPEND_ONLY remains local and is not included in the handoff.'
if ($verifyExit -eq 0) { Write-Host '[PASS] Current-run 0B11 and 0B14 plumbing verified with Gate v5 lineage. Next: local snapshot provenance v4 + Gate v5.' -ForegroundColor Green; exit 0 }
if ($verifyExit -eq 3) { Write-Host '[WAIT] Capture plumbing ran, but both required realtime dataspecs did not yet contain records in this run. Retry at an appropriate JRA race-time window.' -ForegroundColor Yellow; exit 3 }
Fail "verification exited $verifyExit"
