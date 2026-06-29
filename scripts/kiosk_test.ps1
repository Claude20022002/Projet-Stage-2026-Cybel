#Requires -Version 5.1
<#
.SYNOPSIS
  Démarrage et dépannage du kiosque visiteur TEST (CybelVisitorKioskTest, port 8001).

.DESCRIPTION
  Script « une commande » pour le contrôleur labo. Évite les pièges PowerShell (lignes coupées, tar Android, etc.).

.EXAMPLE
  .\scripts\kiosk_test.ps1 demarrer

.EXAMPLE
  .\scripts\kiosk_test.ps1 status

.EXAMPLE
  .\scripts\kiosk_test.ps1 redemarrer
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
$Bash = "/data/data/com.termux/files/usr/bin/bash"
$EnvBlock = "export HOME=$TermuxHome CYBEL_HOME=$CybelTest PATH=/data/data/com.termux/files/usr/bin:/system/bin"

function Write-Titre {
    param([string] $Texte)
    Write-Host ""
    Write-Host ("─" * 50) -ForegroundColor DarkGray
    Write-Host $Texte -ForegroundColor Cyan
    Write-Host ("─" * 50) -ForegroundColor DarkGray
}

function Invoke-Termux {
    param([string] $Commande)
    $full = "$EnvBlock && $Commande"
    $raw = adb shell $full 2>&1
    if ($LASTEXITCODE -ne 0 -and -not $raw) {
        throw "adb shell a échoué (code $LASTEXITCODE). Câble USB branché ? adb devices"
    }
    return ($raw | Out-String).TrimEnd()
}

function Test-Adb {
    $devices = adb devices 2>&1 | Out-String
    if ($devices -notmatch "`tdevice") {
        Write-Host "[ERREUR] Aucune tablette détectée par ADB." -ForegroundColor Red
        Write-Host "  → Branchez le câble USB, déverrouillez la tablette, acceptez le débogage USB." -ForegroundColor Yellow
        return $false
    }
    Write-Host "[OK] Tablette connectée (ADB)" -ForegroundColor Green
    return $true
}

function Get-IpTablette {
    $out = adb shell "ip -4 addr show wlan0 2>/dev/null | awk '/inet /{print `$2}' | cut -d/ -f1 | head -1" 2>&1
    return ($out | Out-String).Trim()
}

function Test-Backend {
    $out = Invoke-Termux "$Bash $CybelTest/scripts/termux/start_cybel_test.sh 2>&1 | tail -5"
    if ($out -match "OK — health check") {
        Write-Host "[OK] Backend actif sur le port 8001" -ForegroundColor Green
        if ($out -match "http://[\d\.]+:8001") {
            $m = [regex]::Match($out, "http://[\d\.]+:8001/kiosk/")
            if ($m.Success) {
                Write-Host "  → URL kiosque : $($m.Value)" -ForegroundColor DarkGray
            }
        }
        return $true
    }
    Write-Host "[!!] Backend absent ou en erreur" -ForegroundColor Yellow
    return $false
}

function Restart-Backend {
    Write-Titre "Redémarrage du backend (port 8001)"
    $out = Invoke-Termux "$Bash $CybelTest/scripts/termux/stop_cybel_test.sh 2>/dev/null; $Bash $CybelTest/scripts/termux/start_cybel_test.sh"
    Write-Host $out
    if ($out -match "OK — health check") {
        Write-Host "[OK] Backend redémarré" -ForegroundColor Green
        return $true
    }
    Write-Host "[ERREUR] Le backend n'a pas répondu au test de santé." -ForegroundColor Red
    return $false
}

function Repair-Deps {
    Write-Titre "Réparation des dépendances Python (bootstrap lite)"
    $out = Invoke-Termux "$Bash $CybelTest/scripts/termux/bootstrap_lite.sh"
    Write-Host $out
    if ($out -match "deps OK") {
        Write-Host "[OK] Dépendances installées" -ForegroundColor Green
        return $true
    }
    Write-Host "[!!] Bootstrap terminé avec avertissements — on tente quand même le redémarrage" -ForegroundColor Yellow
    return $true
}

function Start-App {
    Write-Titre "Lancement de l'application CYBEL Accueil (TEST)"
    adb shell am start -n com.cybel.visitorkiosk.test/.MainActivity | Out-Null
    Write-Host "[OK] Application lancée" -ForegroundColor Green
}

function Show-Logs {
    Write-Titre "Dernières lignes du journal backend"
    $log = adb shell "cat $TermuxHome/cybel-test-uvicorn.log 2>/dev/null | tail -40" 2>&1
    Write-Host ($log | Out-String)
}

function Show-Status {
    Write-Titre "État du kiosque TEST"
    if (-not (Test-Adb)) { return 1 }

    $ip = Get-IpTablette
    if ($ip) {
        Write-Host "IP tablette (Wi-Fi labo) : $ip" -ForegroundColor DarkGray
        Write-Host "  (Cette adresse change avec le DHCP — c'est normal.)" -ForegroundColor DarkGray
        Write-Host "Adresse robot depuis Termux : 192.168.20.22 (ne pas confondre)" -ForegroundColor DarkGray
    }

    $ok = $false
    try {
        $health = Invoke-Termux "/data/data/com.termux/files/usr/bin/python -c `"import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8001/api/health', timeout=3).read().decode())`" 2>/dev/null"
        if ($health -match '"status"\s*:\s*"ok"') {
            Write-Host "[OK] Backend répond : $health" -ForegroundColor Green
            $ok = $true
        }
    }
    catch { }

    if (-not $ok) {
        Write-Host "[!!] Backend port 8001 : pas de réponse" -ForegroundColor Yellow
        Write-Host "  → Lancez : .\scripts\kiosk_test.ps1 redemarrer" -ForegroundColor Yellow
    }
    return $(if ($ok) { 0 } else { 1 })
}

function Start-Full {
    Write-Titre "Démarrage complet du kiosque TEST"
    Write-Host "Étape 1/4 — Vérifier la connexion USB..." -ForegroundColor White
    if (-not (Test-Adb)) { return 1 }

    Write-Host "Étape 2/4 — Vérifier le backend..." -ForegroundColor White
    $backendOk = $false
    try {
        $health = Invoke-Termux "/data/data/com.termux/files/usr/bin/python -c `"import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8001/api/health', timeout=3).read().decode())`" 2>/dev/null"
        $backendOk = $health -match '"status"\s*:\s*"ok"'
    }
    catch { }

    if (-not $backendOk) {
        Write-Host "  Backend arrêté — redémarrage..." -ForegroundColor Yellow
        if (-not (Restart-Backend)) {
            Write-Host "  Échec — réparation des dépendances..." -ForegroundColor Yellow
            Repair-Deps | Out-Null
            if (-not (Restart-Backend)) {
                Write-Host ""
                Write-Host "[ERREUR] Impossible de démarrer le backend." -ForegroundColor Red
                Write-Host "  → Consultez les logs : .\scripts\kiosk_test.ps1 logs" -ForegroundColor Yellow
                Write-Host "  → Puis contactez le référent technique si le problème persiste." -ForegroundColor Yellow
                return 1
            }
        }
    }
    else {
        Write-Host "[OK] Backend déjà actif" -ForegroundColor Green
    }

    Write-Host "Étape 3/4 — Lancer l'application..." -ForegroundColor White
    Start-App

    Write-Host "Étape 4/4 — Terminé" -ForegroundColor White
    $ip = Get-IpTablette
    Write-Host ""
    Write-Host "Le kiosque devrait s'afficher sur la tablette." -ForegroundColor Green
    if ($ip) {
        Write-Host "URL (réseau labo) : http://${ip}:8001/kiosk/" -ForegroundColor DarkGray
    }
    Write-Host ""
    Write-Host "Si l'écran reste blanc ou affiche une erreur :" -ForegroundColor Yellow
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
