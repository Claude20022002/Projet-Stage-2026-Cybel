#Requires -Version 5.1
<#
.SYNOPSIS
  Vérifications automatiques avant session labo (robot + sync POI + backends kiosque).

.DESCRIPTION
  Enchaîne : ping robot/tablette → sync POI dry-run → health HTTP 8000/8001 → contrôles optionnels ADB/SSH.

.EXAMPLE
  .\scripts\preflight_labo.ps1 -TabletHost 172.16.0.130

.EXAMPLE
  .\scripts\preflight_labo.ps1 -TabletHost 172.16.0.130 -Target test -Verbose
#>
[CmdletBinding()]
param(
    [string] $TabletHost = $(if ($env:CYBEL_TERMUX_HOST) { $env:CYBEL_TERMUX_HOST } else { "172.16.0.130" }),
    [string] $RobotHostEth = "192.168.20.22",
    [string] $RobotHostWifi = "10.42.0.1",
    [int]    $SshPort = $(if ($env:CYBEL_TERMUX_PORT) { [int]$env:CYBEL_TERMUX_PORT } else { 8022 }),
    [string] $SshUser = $(if ($env:CYBEL_TERMUX_USER) { $env:CYBEL_TERMUX_USER } else { "u0_a92" }),
    [ValidateSet("main", "test", "both")]
    [string] $Target = "both",
    [switch] $NoPing,
    [switch] $NoSync,
    [switch] $NoHealth,
    [switch] $NoAdb,
    [int]    $TimeoutSec = 3
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:Results = [System.Collections.Generic.List[object]]::new()
$script:FailCount = 0
$script:WarnCount = 0

function Get-RepoRoot {
    $here = Split-Path -Parent $MyInvocation.MyCommand.Path
    return (Resolve-Path (Join-Path $here "..")).Path
}

function Write-Step([string] $Title) {
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor DarkGray
    Write-Host $Title -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor DarkGray
}

function Add-Result {
    param(
        [string] $Name,
        [ValidateSet("OK", "WARN", "FAIL", "SKIP")]
        [string] $Status,
        [string] $Detail = ""
    )
    switch ($Status) {
        "OK"   { $color = "Green" }
        "WARN" { $color = "Yellow"; $script:WarnCount++ }
        "FAIL" { $color = "Red";   $script:FailCount++ }
        "SKIP" { $color = "DarkGray" }
    }
    $icon = switch ($Status) { "OK" { "[OK]" } "WARN" { "[!!]" } "FAIL" { "[XX]" } "SKIP" { "[--]" } }
    Write-Host "$icon $Name" -ForegroundColor $color
    if ($Detail) { Write-Host "    $Detail" -ForegroundColor DarkGray }
    $script:Results.Add([pscustomobject]@{ Check = $Name; Status = $Status; Detail = $Detail })
}

function Test-HostPing {
    param([string] $HostName, [string] $Label)
    if ($NoPing) {
        Add-Result -Name "Ping $Label" -Status "SKIP" -Detail "NoPing"
        return $false
    }
    try {
        $ok = Test-Connection -ComputerName $HostName -Count 1 -Quiet -ErrorAction Stop
        if ($ok) {
            Add-Result -Name "Ping $Label ($HostName)" -Status "OK"
            return $true
        }
        Add-Result -Name "Ping $Label ($HostName)" -Status "FAIL" -Detail "Hôte injoignable"
        return $false
    }
    catch {
        Add-Result -Name "Ping $Label ($HostName)" -Status "FAIL" -Detail $_.Exception.Message
        return $false
    }
}

function Test-HttpHealth {
    param([string] $BaseUrl, [string] $Label)
    if ($NoHealth) {
        Add-Result -Name "Health $Label" -Status "SKIP" -Detail "NoHealth"
        return $false
    }
    $url = "$BaseUrl/api/health"
    try {
        $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $TimeoutSec -ErrorAction Stop
        if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300) {
            Add-Result -Name "Health $Label" -Status "OK" -Detail $url
            return $true
        }
        Add-Result -Name "Health $Label" -Status "FAIL" -Detail "HTTP $($resp.StatusCode) — $url"
        return $false
    }
    catch {
        Add-Result -Name "Health $Label" -Status "FAIL" -Detail "$url — $($_.Exception.Message)"
        return $false
    }
}

function Invoke-SyncDryRun {
    param([string] $HostName)
    $repo = Get-RepoRoot
    $syncScript = Join-Path $repo "scripts\sync_poi_from_robot.py"
    if (-not (Test-Path $syncScript)) {
        Add-Result -Name "Sync POI dry-run" -Status "FAIL" -Detail "Script introuvable : $syncScript"
        return $false
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        Add-Result -Name "Sync POI dry-run" -Status "FAIL" -Detail "python introuvable dans PATH"
        return $false
    }
    Write-Host "    python sync_poi_from_robot.py --host $HostName --dry-run" -ForegroundColor DarkGray
    Push-Location $repo
    try {
        & $python.Source $syncScript --host $HostName --dry-run 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
        if ($LASTEXITCODE -ne 0) {
            Add-Result -Name "Sync POI dry-run ($HostName)" -Status "FAIL" -Detail "exit code $LASTEXITCODE"
            return $false
        }
        Add-Result -Name "Sync POI dry-run ($HostName)" -Status "OK"
        return $true
    }
    finally {
        Pop-Location
    }
}

function Test-LabTourTargets {
    $repo = Get-RepoRoot
    $path = Join-Path $repo "data\lab_tour.json"
    if (-not (Test-Path $path)) {
        Add-Result -Name "lab_tour.json target_point" -Status "FAIL" -Detail "Fichier absent"
        return
    }
    try {
        $tour = Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json
        $stops = @($tour.stops)
        $withTarget = @($stops | Where-Object { $_.target_point -and $_.target_point.Trim() })
        $count = $withTarget.Count
        if ($count -ge 8) {
            Add-Result -Name "lab_tour.json target_point" -Status "OK" -Detail "$count arrêts avec target_point"
        }
        elseif ($count -gt 0) {
            Add-Result -Name "lab_tour.json target_point" -Status "WARN" -Detail "$count/8 arrêts POI — branche hybrid ?"
        }
        else {
            Add-Result -Name "lab_tour.json target_point" -Status "WARN" -Detail "Aucun target_point — approche coords (main)"
        }
    }
    catch {
        Add-Result -Name "lab_tour.json target_point" -Status "FAIL" -Detail $_.Exception.Message
    }
}

function Test-AdbDevices {
    if ($NoAdb) {
        Add-Result -Name "ADB devices" -Status "SKIP" -Detail "NoAdb"
        return
    }
    $adb = Get-Command adb -ErrorAction SilentlyContinue
    if (-not $adb) {
        Add-Result -Name "ADB devices" -Status "WARN" -Detail "adb absent du PATH"
        return
    }
    try {
        $lines = & adb devices 2>&1
        $devices = @($lines | Select-Object -Skip 1 | Where-Object { $_ -match "device\s*$" })
        if ($devices.Count -gt 0) {
            Add-Result -Name "ADB devices" -Status "OK" -Detail "$($devices.Count) appareil(s) connecté(s)"
        }
        else {
            Add-Result -Name "ADB devices" -Status "WARN" -Detail "Aucun appareil — USB/Wi-Fi ADB ?"
        }
    }
    catch {
        Add-Result -Name "ADB devices" -Status "WARN" -Detail $_.Exception.Message
    }
}

function Test-SshHealth {
    param([int] $Port, [string] $Label)
    if ($NoHealth) { return }
    $ssh = Get-Command ssh -ErrorAction SilentlyContinue
    if (-not $ssh) {
        Add-Result -Name "SSH health $Label" -Status "SKIP" -Detail "ssh absent"
        return
    }
    $cmd = "curl -sf http://127.0.0.1:$Port/api/health && echo OK || echo FAIL"
    try {
        $out = & ssh -p $SshPort -o ConnectTimeout=$TimeoutSec -o BatchMode=yes -o StrictHostKeyChecking=accept-new `
            "${SshUser}@${TabletHost}" $cmd 2>&1
        if ($out -match "OK") {
            Add-Result -Name "SSH health $Label (127.0.0.1:$Port)" -Status "OK"
        }
        else {
            Add-Result -Name "SSH health $Label (127.0.0.1:$Port)" -Status "WARN" -Detail "SSH sans clé ou backend arrêté — tester HTTP direct"
        }
    }
    catch {
        Add-Result -Name "SSH health $Label" -Status "WARN" -Detail $_.Exception.Message
    }
}

# ── Main ────────────────────────────────────────────────────

Write-Host ""
Write-Host "CYBEL — Preflight labo" -ForegroundColor White -BackgroundColor DarkBlue
Write-Host "Repo   : $(Get-RepoRoot)"
Write-Host "Tablette: $TabletHost  |  Robot eth: $RobotHostEth  |  Robot Wi-Fi: $RobotHostWifi"
Write-Host "Cible health: $Target"

Write-Step "1/5 — Connectivité réseau"
$ethOk = Test-HostPing -HostName $RobotHostEth -Label "robot eth0"
$wifiOk = Test-HostPing -HostName $RobotHostWifi -Label "robot Wi-Fi"
if ($TabletHost) {
    Test-HostPing -HostName $TabletHost -Label "tablette Termux" | Out-Null
}

Write-Step "2/5 — Sync POI (dry-run, sans écriture)"
if ($NoSync) {
    Add-Result -Name "Sync POI dry-run" -Status "SKIP" -Detail "NoSync"
}
else {
    $syncOk = $false
    if ($ethOk) {
        $syncOk = Invoke-SyncDryRun -HostName $RobotHostEth
    }
    if (-not $syncOk -and $wifiOk) {
        Write-Host "    Nouvelle tentative via $RobotHostWifi …" -ForegroundColor DarkYellow
        $syncOk = Invoke-SyncDryRun -HostName $RobotHostWifi
    }
    if (-not $syncOk -and -not $ethOk -and -not $wifiOk) {
        Add-Result -Name "Sync POI dry-run" -Status "FAIL" -Detail "Robot injoignable — connectez le PC au Wi-Fi du robot"
    }
}

Write-Step "3/5 — Health backends kiosque (HTTP tablette)"
if ($TabletHost -and -not $NoHealth) {
    if ($Target -in @("main", "both")) {
        Test-HttpHealth -BaseUrl "http://${TabletHost}:8000" -Label "main :8000 (coords)" | Out-Null
    }
    if ($Target -in @("test", "both")) {
        Test-HttpHealth -BaseUrl "http://${TabletHost}:8001" -Label "test :8001 (POI)" | Out-Null
    }
    Test-SshHealth -Port 8000 -Label "main"
    Test-SshHealth -Port 8001 -Label "test"
}
elseif ($NoHealth) {
    Add-Result -Name "Health HTTP" -Status "SKIP" -Detail "NoHealth"
}
else {
    Add-Result -Name "Health HTTP" -Status "WARN" -Detail "Précisez -TabletHost"
}

Write-Step "4/5 — Configuration parcours"
Test-LabTourTargets

Write-Step "5/5 — ADB (optionnel)"
Test-AdbDevices

Write-Step "Résumé"
$ok = @($script:Results | Where-Object Status -eq "OK").Count
$warn = @($script:Results | Where-Object Status -eq "WARN").Count
$fail = @($script:Results | Where-Object Status -eq "FAIL").Count
$skip = @($script:Results | Where-Object Status -eq "SKIP").Count

Write-Host "OK: $ok  |  Avertissements: $warn  |  Échecs: $fail  |  Ignorés: $skip"

if ($fail -gt 0) {
    Write-Host ""
    Write-Host "Échecs critiques :" -ForegroundColor Red
    $script:Results | Where-Object Status -eq "FAIL" | ForEach-Object {
        Write-Host "  - $($_.Check): $($_.Detail)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Prochaines étapes :" -ForegroundColor Cyan
Write-Host "  1. POI dans Sentrymove (noms = target_point lab_tour.json)"
Write-Host "  2. python scripts/sync_poi_from_robot.py --host $RobotHostEth"
Write-Host "  3. python scripts/deploy_termux.py --host $TabletHost --lite-only --target test"
Write-Host "  4. adb install -r android\CybelVisitorKioskTest\out\CybelVisitorKioskTest.apk"
Write-Host ""
Write-Host "Guide complet : docs/labo/TERRAIN.md" -ForegroundColor DarkGray

if ($fail -gt 0) { exit 1 }
if ($warn -gt 0) { exit 2 }
exit 0
