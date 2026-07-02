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

function Start-App {
    Write-Titre "Lancement de l'application CYBEL Accueil (TEST)"
    adb shell am start -n com.cybel.visitorkiosk.test/.MainActivity | Out-Null
    Write-Host "[OK] Application lancee" -ForegroundColor Green
}

function Show-Logs {
    Write-Titre "Dernieres lignes du journal backend"
    $log = adb shell "cat $TermuxHome/cybel-test-uvicorn.log 2>/dev/null | tail -40" 2>&1
    Write-Host ($log | Out-String)
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
        "reparer"    { if (-not (Test-Adb)) { exit 1 }; Repair-Deps | Out-Null; if (Restart-Backend) { exit 0 } else { exit 1 } }
        "lancer"     { if (-not (Test-Adb)) { exit 1 }; Start-App; exit 0 }
        "logs"       { if (-not (Test-Adb)) { exit 1 }; Show-Logs; exit 0 }
        "ip"         { if (-not (Test-Adb)) { exit 1 }; $ip = Get-IpTablette; Write-Host "IP tablette : $ip"; exit 0 }
    }
}
finally {
    Pop-Location
}
