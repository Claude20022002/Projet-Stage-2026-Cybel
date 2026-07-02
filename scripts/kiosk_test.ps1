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
$Pip  = "/data/data/com.termux/files/usr/bin/pip"
$Py   = "/data/data/com.termux/files/usr/bin/python"
$EnvBlock     = "export HOME=$TermuxHome CYBEL_HOME=$CybelTest PATH=/data/data/com.termux/files/usr/bin:/system/bin"
$EnvBlockMain = "export HOME=$TermuxHome CYBEL_HOME=$CybelMain PATH=/data/data/com.termux/files/usr/bin:/system/bin"

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
    $raw = adb shell $full 2>&1
    if ($LASTEXITCODE -ne 0 -and -not $raw) {
        throw "adb shell a echoue (code $LASTEXITCODE). Cable USB branche ? adb devices"
    }
    return ($raw | Out-String).TrimEnd()
}

function Invoke-TermuxMain {
    param([string] $Commande)
    $full = "$EnvBlockMain && $Commande"
    $raw = adb shell $full 2>&1
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
    $out = adb shell "ip -4 addr show wlan0 2>/dev/null | awk '/inet /{print `$2}' | cut -d/ -f1 | head -1" 2>&1
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

function Repair-MainBackend {
    Write-Titre "Reparation backend principal (~/cybel, port 8000)"

    # 1. Installer uvicorn + starlette (manquants dans cybel_lite.py)
    Write-Host "Etape 1/3 - Installation uvicorn starlette websockets..." -ForegroundColor White
    $pip = Invoke-TermuxMain "$Pip install uvicorn starlette websockets --quiet 2>&1 | tail -3"
    if ($pip) { Write-Host $pip }

    # 2. Stopper les anciennes instances du backend principal
    Write-Host "Etape 2/3 - Arret du backend existant..." -ForegroundColor White
    Invoke-TermuxMain "pkill -f cybel_lite 2>/dev/null; pkill -f start_cybel 2>/dev/null; echo stopped" | Out-Null
    Start-Sleep -Seconds 2

    # 3. Relancer le backend principal en arriere-plan
    Write-Host "Etape 3/3 - Demarrage backend principal..." -ForegroundColor White
    $startScript = "$CybelMain/scripts/termux/start_cybel.sh"
    $out = Invoke-TermuxMain "if [ -f $startScript ]; then nohup $Bash $startScript > $TermuxHome/cybel-uvicorn.log 2>&1 & sleep 4 && echo launched; else echo noscript; fi"
    if ($out -match "launched") {
        Write-Host "[OK] Backend principal lance via start_cybel.sh" -ForegroundColor Green
        return $true
    }
    # Fallback : lancer cybel_lite.py directement
    Write-Host "[!!] start_cybel.sh absent, lancement direct de cybel_lite.py..." -ForegroundColor Yellow
    $litePy = "$CybelMain/scripts/termux/cybel_lite.py"
    Invoke-TermuxMain "nohup $Py $litePy > $TermuxHome/cybel-uvicorn.log 2>&1 &" | Out-Null
    Start-Sleep -Seconds 4
    return $true
}

function Test-LocalhostBackend {
    param([int]$Port = 8001)
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:$Port/api/health" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        return ($resp.StatusCode -eq 200)
    } catch {
        return $false
    }
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

            # 1. Reparer le backend PRINCIPAL (~/cybel, port 8000)
            Repair-MainBackend | Out-Null

            # 2. ADB port forward : PC:8001 -> tablette:8000 (backend principal)
            Set-AdbPortForward -PcPort 8001 -DevicePort 8000 | Out-Null

            # 3. Verifier l'acces depuis le PC
            Write-Host "Verification sante via localhost:8001 ..." -ForegroundColor White
            Start-Sleep -Seconds 2
            if (Test-LocalhostBackend -Port 8001) {
                Write-Host "[OK] Backend accessible sur http://localhost:8001" -ForegroundColor Green
                Write-Host ""
                Write-Host "  Lancez la collecte tour avec :" -ForegroundColor Cyan
                Write-Host "  python scripts/collect_paper_data.py --phase tour --host localhost --backend-port 8001 --tour-trials 3" -ForegroundColor Yellow
                exit 0
            } else {
                Write-Host "[ERREUR] Backend non accessible sur localhost:8001" -ForegroundColor Red
                Write-Host "  Consultez les logs Termux :" -ForegroundColor Yellow
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
