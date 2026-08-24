param(
  [string]$Date = (Get-Date -Format 'yyyyMMdd'),
  [string]$Root = 'C:\MAGI\KEIBA\REALTIME',
  [string]$Sid = 'MAGI_KEIBA_RT_V2'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red; exit 2 }

Write-Host "=== KEIBA JV-Link first forward capture v2 ==="
Write-Host "Date: $Date"
Write-Host "Root: $Root"
if ($env:OS -ne 'Windows_NT') { Fail 'Windows is required for JV-Link.' }
if ($Date -notmatch '^\d{8}$') { Fail '-Date must be YYYYMMDD.' }
if (-not (Get-Command py.exe -ErrorAction SilentlyContinue)) { Fail 'Python launcher not found. Python 3.14 x64 is required for the preferred official route.' }

& py -3.14 -c "import sys,platform; assert sys.maxsize > 2**32; import win32com.client,pythoncom; jv=win32com.client.Dispatch('JVDTLab.JVLink'); print(sys.version); print(platform.platform()); print('JV-Link COM OK')"
if ($LASTEXITCODE -ne 0) { Fail 'Python 3.14 x64 / pywin32 / 64-bit JV-Link COM is not ready.' }

New-Item -ItemType Directory -Force -Path $Root | Out-Null
$clockDir = Join-Path $Root 'LOG'; New-Item -ItemType Directory -Force -Path $clockDir | Out-Null
$clockFile = Join-Path $clockDir ("clock_audit_" + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.json')
$tz = [System.TimeZoneInfo]::Local
@{recorded_at_local=(Get-Date).ToString('o');recorded_at_utc=(Get-Date).ToUniversalTime().ToString('o');timezone_id=$tz.Id;utc_offset=(Get-Date).ToString('zzz');computer_name=$env:COMPUTERNAME;date_key=$Date} | ConvertTo-Json | Set-Content -Encoding UTF8 $clockFile

Write-Host '[1/3] Capturing official 0B11 / 0B14 once...'
& py -3.14 scripts\keiba_jvlink_realtime_capture_v2.py --date $Date --root $Root --sid $Sid --once
if ($LASTEXITCODE -ne 0) { Fail "collector exited $LASTEXITCODE" }

Write-Host '[2/3] Verifying append-only raw bytes / SHA / JV status...'
$reportPath = Join-Path $clockDir ("first_capture_verify_" + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.json')
& py -3.14 scripts\keiba_verify_first_capture_v1.py --root $Root --date $Date --out $reportPath
$verifyExit = $LASTEXITCODE

Write-Host '[3/3] Result'; Get-Content $reportPath
if ($verifyExit -eq 0) { Write-Host '[PASS] First real capture plumbing verified. Next: build snapshot provenance v2 and run Gate v3.' -ForegroundColor Green; exit 0 }
if ($verifyExit -eq 3) { Write-Host '[WAIT] Plumbing works but no usable realtime records were available. Retry for a JRA race date within the realtime retention window.' -ForegroundColor Yellow; exit 3 }
Fail "verification exited $verifyExit"
