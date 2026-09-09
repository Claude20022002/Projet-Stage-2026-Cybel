# =============================================================================
#  Reclaiming Closed Service Robots - IEEE ICRA 2027
#  Windows build script. Same targets as the Makefile, for machines without make.
#
#    .\build.ps1            build the PDF and report the page count
#    .\build.ps1 pages      page count only (hard limit: 8)
#    .\build.ps1 stats      recompute every interval quoted in the paper
#    .\build.ps1 assets     regenerate the redacted photographs
#    .\build.ps1 check      build, then run the pre-submission checks
#    .\build.ps1 clean      remove build artefacts
# =============================================================================
param([string]$Target = "all")

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Main  = "main"
$Limit = 8

function Invoke-Build {
    pdflatex -interaction=nonstopmode "$Main.tex" | Out-Null
    bibtex $Main | Out-Null
    pdflatex -interaction=nonstopmode "$Main.tex" | Out-Null
    pdflatex -interaction=nonstopmode "$Main.tex" | Out-Null
}

function Get-PageCount {
    $bytes = [System.IO.File]::ReadAllBytes("$PSScriptRoot\$Main.pdf")
    $text  = [System.Text.Encoding]::Latin1.GetString($bytes)
    ([regex]::Matches($text, '/Type\s*/Page[^s]')).Count
}

function Show-Pages {
    $n = Get-PageCount
    if ($n -le $Limit) {
        Write-Host "pages: $n / $Limit max" -ForegroundColor Green
    } else {
        Write-Host "pages: $n / $Limit max  -- OVER THE LIMIT" -ForegroundColor Red
        exit 1
    }
}

# Each check is a name and a regex that must NOT match anywhere in the sources.
function Invoke-Checks {
    $sources = @("$Main.tex", "preamble.tex", "references.bib") +
               (Get-ChildItem sections, figures, tables -Filter *.tex | ForEach-Object FullName)

    $log = Get-Content "$Main.log" -Raw
    $failed = $false

    foreach ($probe in @(
        @{ Name = "LaTeX errors";                    Pattern = '(?m)^!' },
        @{ Name = "unresolved citations/references"; Pattern = '(Citation|Reference) .* undefined' }
    )) {
        if ($log -match $probe.Pattern) {
            Write-Host "FAIL  $($probe.Name)" -ForegroundColor Red; $failed = $true
        } else {
            Write-Host "ok    $($probe.Name)" -ForegroundColor Green
        }
    }

    # Identity checks ignore LaTeX comment lines: the real names and URL are
    # deliberately kept there, commented out, for the camera-ready version.
    foreach ($probe in @(
        @{ Name = "leftover placeholders"; Pattern = 'TODO|FIXME|\\ph\{' },
        @{ Name = "institution / robot model";
           Pattern = 'hestim|casablanca|morocco|ciot|ty1251|welcomepatrol|sentrymove|cerim' },
        @{ Name = "author identity (double-blind)";
           Pattern = 'lusamote|kimfuta|tula|claude20022002|Projet-Stage-2026' },
        @{ Name = "unfilled anonymous repository link";
           Pattern = 'ANONYMOUS-REPO-ID' }
    )) {
        $hits = Select-String -Path $sources -Pattern $probe.Pattern |
                Where-Object { $_.Line -notmatch '^\s*%' }
        if ($hits) {
            Write-Host "FAIL  $($probe.Name)" -ForegroundColor Red
            $hits | ForEach-Object { Write-Host "        $($_.Path):$($_.LineNumber)" }
            $failed = $true
        } else {
            Write-Host "ok    $($probe.Name)" -ForegroundColor Green
        }
    }

    if ($failed) { exit 1 }
}

switch ($Target) {
    "all"    { Invoke-Build; Show-Pages }
    "pages"  { Show-Pages }
    "stats"  { python tools/stats.py }
    "assets" { python tools/prepare_assets.py }
    "check"  { Invoke-Build; Show-Pages; Invoke-Checks }
    "clean"  {
        Remove-Item -Force -ErrorAction SilentlyContinue `
            "$Main.pdf", "$Main.aux", "$Main.bbl", "$Main.blg", `
            "$Main.log", "$Main.out", "$Main.fdb_latexmk", "$Main.fls"
        Write-Host "cleaned"
    }
    default  { Write-Host "unknown target: $Target"; exit 1 }
}
