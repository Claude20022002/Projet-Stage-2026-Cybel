#Requires -Version 5.1
<#
.SYNOPSIS
  Demarrage et depannage du kiosque visiteur TEST (CybelVisitorKioskTest, port 8001).

.DESCRIPTION
  Script une commande pour le controleur labo. Evite les pieges PowerShell (lignes coupees, tar Android).

.EXAMPLE
  .\scripts\kiosk_test.ps1 demarrer

.EXAMPLE
  .\scripts\kiosk_test.ps1 status
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("demarrer", "status", "redemarrer", "reparer", "lancer", "logs", "ip")]
    [string] $Action = "demarrer"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$TermuxHome = "/data/data/com.termux/files/home"
$CybelTest = "$TermuxHome/cybel-test"
$CybelMain = "$TermuxHome/cybel"
$Bash = "/data/data/com.termux/files/usr/bin/bash"
$TermuxUid = 10092   # adb shell tourne en root — su TermuxUid pour pkg/pip
$EnvBlock     = "export HOME=$TermuxHome CYBEL_HOME=$CybelTest PATH=/data/data/com.termux/files/usr/bin:/data/data/com.termux/files/usr/bin/applets:/system/bin"
$EnvBlockMain = "export HOME=$TermuxHome CYBEL_HOME=$CybelMain PATH=/data/data/com.termux/files/usr/bin:/data/data/com.termux/files/usr/bin/applets:/system/bin"

function Write-Titre {
    param([string] $Texte)
    Write-Host ""
    Write-Host ("=" * 50) -ForegroundColor DarkGray
    Write-Host $Texte -ForegroundColor Cyan
    Write-Host ("=" * 50) -ForegroundColor DarkGray
}

function Invoke-Termux {
    param([string] $Commande)
    $full = "$EnvBlock && $Commande"
    $raw = adb shell "su $TermuxUid -c `"$full`"" 2>&1
    if ($LASTEXITCODE -ne 0 -and -not $raw) {
        throw "adb shell a echoue (code $LASTEXITCODE). Cable USB branche ? adb devices"
    }
    return ($raw | Out-String).TrimEnd()
}

function Invoke-TermuxMain {
    param([string] $Commande)
    $full = "$EnvBlockMain && $Commande"
    $raw = adb shell "su $TermuxUid -c `"$full`"" 2>&1
    return ($raw | Out-String).TrimEnd()
}

function Test-Adb {
    $devices = adb devices 2>&1 | Out-String
    if ($devices -notmatch "`tdevice") {
        Write-Host "[ERREUR] Aucune tablette detectee par ADB." -ForegroundColor Red
        Write-Host "  -> Branchez le cable USB, deverrouillez la tablette, acceptez le debogage USB." -ForegroundColor Yellow
        return $false
    }
    Write-Host "[OK] Tablette connectee (ADB)" -ForegroundColor Green
    return $true
}

function Get-IpTablette {
    # awk absent dans certains contextes ADB — utilise grep + sed
    $out = adb shell "ip -4 addr show wlan0 2>/dev/null | grep 'inet ' | head -1 | sed 's/.*inet \([0-9.]*\)\/.*/\1/'" 2>&1
    return ($out | Out-String).Trim()
}

function Test-BackendHealth {
    $out = Invoke-Termux "$Bash $CybelTest/scripts/termux/start_cybel_test.sh 2>&1"
    return ($out -match '(?i)(health check|deja actif)')
}

function Restart-Backend {
    Write-Titre "Redemarrage du backend (port 8001)"
    $out = Invoke-Termux "$Bash $CybelTest/scripts/termux/stop_cybel_test.sh 2>/dev/null; $Bash $CybelTest/scripts/termux/start_cybel_test.sh"
    Write-Host $out
    if ($out -match '(?i)health check') {
        Write-Host "[OK] Backend redemarre" -ForegroundColor Green
        return $true
    }
    Write-Host "[ERREUR] Le backend n'a pas repondu au test de sante." -ForegroundColor Red
    return $false
}

function Repair-Deps {
    Write-Titre "Reparation des dependances Python (bootstrap lite)"
    $out = Invoke-Termux "$Bash $CybelTest/scripts/termux/bootstrap_lite.sh"
    Write-Host $out
    if ($out -match "deps OK") {
        Write-Host "[OK] Dependances installees" -ForegroundColor Green
        return $true
    }
    Write-Host "[!!] Bootstrap termine avec avertissements - on tente quand meme le redemarrage" -ForegroundColor Yellow
    return $true
}

function Set-AdbPortForward {
    param([int]$PcPort = 8001, [int]$DevicePort = 8000)
    Write-Host "ADB port forward : PC localhost:$PcPort -> tablette:$DevicePort ..." -ForegroundColor White
    $null = adb forward tcp:$PcPort tcp:$DevicePort 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] ADB forward actif : localhost:$PcPort -> device:$DevicePort" -ForegroundColor Green
        return $true
    }
    Write-Host "[ERREUR] adb forward tcp:${PcPort} tcp:${DevicePort} a echoue" -ForegroundColor Red
    return $false
}

function Find-RunningBackendPort {
    <#
    Android isole les espaces reseau par app : curl depuis adb shell ne peut pas
    atteindre le localhost de Termux. On utilise pgrep (processus globalement visibles)
    puis on lit BACKEND_PORT dans cybel.env pour connaitre le port.
    #>
    $pids = adb shell "pgrep -f cybel_lite 2>/dev/null" 2>&1
    if (-not ($pids -match '\d+')) { return $null }

    # Identifier quel deploiement tourne (main vs test) via la ligne de commande
    $cmdlines = adb shell "cat /proc/$($pids.Split()[0])/cmdline 2>/dev/null | tr '\0' ' '" 2>&1
    if ($cmdlines -match "cybel-test") {
        $envFile = "$CybelTest/scripts/termux/cybel.env"
    } else {
        $envFile = "$CybelMain/scripts/termux/cybel.env"
    }

    # Lire le port depuis cybel.env
    $portLine = adb shell "grep BACKEND_PORT $envFile 2>/dev/null" 2>&1
    if ($portLine -match '(\d+)') { return [int]$Matches[1] }
    return 8000  # defaut Termux CYBEL
}

function Repair-MainBackend {
    Write-Titre "Detection backend actif sur la tablette"

    $port = Find-RunningBackendPort
    if ($port) {
        Write-Host "[OK] Backend detecte sur la tablette (port $port)" -ForegroundColor Green
        return $port
    }

    # Aucun backend actif — demander a l'utilisateur de le demarrer depuis Termux
    Write-Host ""
    Write-Host "[!!] Aucun backend CYBEL en cours sur la tablette." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Sur la tablette, ouvrez Termux et tapez :" -ForegroundColor Cyan
    Write-Host "  cd ~/cybel && bash scripts/termux/start_cybel.sh" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  (ou 'cd ~/cybel-test && bash scripts/termux/start_cybel.sh' selon le deploiement)" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Puis relancez : .\scripts\kiosk_test.ps1 reparer" -ForegroundColor Cyan
    Write-Host ""
    return $null
}

function Test-LocalhostBackend {
    param([int]$Port = 8001, [int]$MaxWaitSec = 20)
    $deadline = (Get-Date).AddSeconds($MaxWaitSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:$Port/api/health" -TimeoutSec 4 -UseBasicParsing -ErrorAction Stop
            if ($resp.StatusCode -eq 200) { return $true }
        } catch { }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Start-App {
    Write-Titre "Lancement de l'application CYBEL Accueil (TEST)"
    adb shell am start -n com.cybel.visitorkiosk.test/.MainActivity | Out-Null
    Write-Host "[OK] Application lancee" -ForegroundColor Green
}

function Show-Logs {
    Write-Titre "Logs backend PRINCIPAL (~/cybel, port 8000)"
    $log = adb shell "cat $TermuxHome/cybel-uvicorn.log 2>/dev/null | tail -40" 2>&1
    Write-Host ($log | Out-String)
    Write-Titre "Logs backend TEST (~/cybel-test, port 8001)"
    $logTest = adb shell "cat $TermuxHome/cybel-test-uvicorn.log 2>/dev/null | tail -20" 2>&1
    Write-Host ($logTest | Out-String)
}

function Show-Status {
    Write-Titre "Etat du kiosque TEST"
    if (-not (Test-Adb)) { return 1 }

    $ip = Get-IpTablette
    if ($ip) {
        Write-Host "IP tablette (Wi-Fi labo) : $ip" -ForegroundColor DarkGray
        Write-Host "  (Cette adresse change avec le DHCP - c'est normal.)" -ForegroundColor DarkGray
        Write-Host "Adresse robot depuis Termux : 192.168.20.22 (ne pas confondre)" -ForegroundColor DarkGray
    }

    $ok = $false
    try {
        if (Test-BackendHealth) {
            Write-Host "[OK] Backend actif sur le port 8001" -ForegroundColor Green
            $ok = $true
        }
    }
    catch { }

    if (-not $ok) {
        Write-Host "[!!] Backend port 8001 : pas de reponse" -ForegroundColor Yellow
        Write-Host "  -> Lancez : .\scripts\kiosk_test.ps1 redemarrer" -ForegroundColor Yellow
    }
    return $(if ($ok) { 0 } else { 1 })
}

function Start-Full {
    Write-Titre "Demarrage complet du kiosque TEST"
    Write-Host "Etape 1/4 - Verifier la connexion USB..." -ForegroundColor White
    if (-not (Test-Adb)) { return 1 }

    Write-Host "Etape 2/4 - Verifier le backend..." -ForegroundColor White
    $backendOk = $false
    try {
        $backendOk = Test-BackendHealth
    }
    catch { }

    if (-not $backendOk) {
        Write-Host "  Backend arrete - redemarrage..." -ForegroundColor Yellow
        if (-not (Restart-Backend)) {
            Write-Host "  Echec - reparation des dependances..." -ForegroundColor Yellow
            Repair-Deps | Out-Null
            if (-not (Restart-Backend)) {
                Write-Host ""
                Write-Host "[ERREUR] Impossible de demarrer le backend." -ForegroundColor Red
                Write-Host "  -> Consultez les logs : .\scripts\kiosk_test.ps1 logs" -ForegroundColor Yellow
                Write-Host "  -> Puis contactez le referent technique si le probleme persiste." -ForegroundColor Yellow
                return 1
            }
        }
    }
    else {
        Write-Host "[OK] Backend deja actif" -ForegroundColor Green
    }

    Write-Host "Etape 3/4 - Lancer l'application..." -ForegroundColor White
    Start-App

    Write-Host "Etape 4/4 - Termine" -ForegroundColor White
    $ip = Get-IpTablette
    Write-Host ""
    Write-Host "Le kiosque devrait s'afficher sur la tablette." -ForegroundColor Green
    if ($ip) {
        Write-Host "URL (reseau labo) : http://${ip}:8001/kiosk/" -ForegroundColor DarkGray
    }
    Write-Host ""
    Write-Host "Si l'ecran reste blanc ou affiche une erreur :" -ForegroundColor Yellow
    Write-Host "  .\scripts\kiosk_test.ps1 redemarrer" -ForegroundColor Yellow
    return 0
}

Push-Location (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
try {
    switch ($Action) {
        "demarrer"   { exit (Start-Full) }
        "status"     { exit (Show-Status) }
        "redemarrer" { if (-not (Test-Adb)) { exit 1 }; if (Restart-Backend) { exit 0 } else { exit 1 } }
        "reparer"    {
            if (-not (Test-Adb)) { exit 1 }

            # 1. Detecter quel backend tourne sur la tablette (sans rien tuer)
            $devicePort = Repair-MainBackend
            if (-not $devicePort) { exit 1 }

            # 2. ADB port forward : PC:8001 -> tablette:<port detecte>
            Set-AdbPortForward -PcPort 8001 -DevicePort $devicePort | Out-Null

            # 3. Verifier l'acces depuis le PC
            Write-Host "Verification sante via localhost:8001 ..." -ForegroundColor White
            if (Test-LocalhostBackend -Port 8001 -MaxWaitSec 10) {
                Write-Host "[OK] Backend accessible sur http://localhost:8001 (forward -> tablette:$devicePort)" -ForegroundColor Green
                Write-Host ""
                Write-Host "  Lancez la collecte tour avec :" -ForegroundColor Cyan
                Write-Host "  python scripts/collect_paper_data.py --phase tour --host localhost --backend-port 8001 --tour-trials 3" -ForegroundColor Yellow
                exit 0
            } else {
                Write-Host "[ERREUR] ADB forward configure mais backend non accessible" -ForegroundColor Red
                Write-Host "  .\scripts\kiosk_test.ps1 logs" -ForegroundColor Yellow
                exit 1
            }
        }
        "lancer"     { if (-not (Test-Adb)) { exit 1 }; Start-App; exit 0 }
        "logs"       { if (-not (Test-Adb)) { exit 1 }; Show-Logs; exit 0 }
        "ip"         { if (-not (Test-Adb)) { exit 1 }; $ip = Get-IpTablette; Write-Host "IP tablette : $ip"; exit 0 }
    }
}
finally {
    Pop-Location
}
