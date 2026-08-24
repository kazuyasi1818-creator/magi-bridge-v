param(
  [string]$Date = (Get-Date -Format 'yyyyMMdd'),
  [string]$Root = 'C:\MAGI\KEIBA\REALTIME',
  [string]$Sid = 'MAGI_KEIBA_RT_V1'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Fail($msg) {
  Write-Host "[FAIL] $msg" -ForegroundColor Red
  exit 2
}

Write-Host "=== KEIBA JV-Link first forward capture ==="
Write-Host "Date: $Date"
Write-Host "Root: $Root"

if ($env:OS -ne 'Windows_NT') { Fail 'Windows is required for JV-Link.' }
if ($Date -notmatch '^\d{8}$') { Fail '-Date must be YYYYMMDD.' }

$py = Get-Command py.exe -ErrorAction SilentlyContinue
if (-not $py) { Fail 'Python launcher (py.exe) not found. Install Python 3.14 x64 first.' }

& py -3.14 -c "import sys,platform; assert sys.maxsize > 2**32; print(sys.version); print(platform.platform())"
if ($LASTEXITCODE -ne 0) { Fail 'Python 3.14 x64 is not available.' }

& py -3.14 -c "import win32com.client, pythoncom; jv=win32com.client.Dispatch('JVDTLab.JVLink'); print('JV-Link COM object OK:', jv)"
if ($LASTEXITCODE -ne 0) { Fail 'pywin32 or 64-bit JV-Link COM registration is not ready.' }

New-Item -ItemType Directory -Force -Path $Root | Out-Null

$clockDir = Join-Path $Root 'LOG'
New-Item -ItemType Directory -Force -Path $clockDir | Out-Null
$clockFile = Join-Path $clockDir ("clock_audit_" + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.json')
$utc = (Get-Date).ToUniversalTime().ToString('o')
$local = (Get-Date).ToString('o')
$tz = [System.TimeZoneInfo]::Local
@{
  recorded_at_local = $local
  recorded_at_utc = $utc
  timezone_id = $tz.Id
  utc_offset = (Get-Date).ToString('zzz')
  computer_name = $env:COMPUTERNAME
  date_key = $Date
} | ConvertTo-Json | Set-Content -Encoding UTF8 $clockFile

Write-Host '[1/3] Capturing 0B11 / 0B14 once...'
& py -3.14 scripts\keiba_jvlink_realtime_capture_v1.py --date $Date --root $Root --sid $Sid --once
$captureExit = $LASTEXITCODE
if ($captureExit -ne 0) { Fail "collector exited $captureExit" }

Write-Host '[2/3] Verifying append-only raw files / SHA / JV status...'
$reportPath = Join-Path $clockDir ("first_capture_verify_" + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.json')
& py -3.14 scripts\keiba_verify_first_capture_v1.py --root $Root --date $Date --out $reportPath
$verifyExit = $LASTEXITCODE

Write-Host '[3/3] Result'
Get-Content $reportPath
if ($verifyExit -eq 0) {
  Write-Host '[PASS] First capture plumbing verified.' -ForegroundColor Green
  exit 0
}
if ($verifyExit -eq 3) {
  Write-Host '[WAIT] Plumbing ran, but usable realtime records were not yet available. Run again on a JRA race day after realtime data begins.' -ForegroundColor Yellow
  exit 3
}
Fail "verification exited $verifyExit"
