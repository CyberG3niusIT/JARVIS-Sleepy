<#
.SYNOPSIS
  Gezielter pytest-Lauf in WSL (Ubuntu-24.04) fuer den Main-Worktree.
.EXAMPLE
  .\wsl-pytest.ps1 tests/unit/test_privacy_audio_reset.py tests/unit/test_turn_assembler.py
  .\wsl-pytest.ps1 -All        # nur explizit: tests/unit + tests/routing ohne hardware/wsl
#>
[CmdletBinding()]
param(
    [switch]$All,
    [int]$Tail = 40,
    [Parameter(ValueFromRemainingArguments)][string[]]$Tests
)
$ErrorActionPreference = 'Stop'

if (-not $All -and (-not $Tests -or $Tests.Count -eq 0)) {
    Write-Host 'Verwendung: wsl-pytest.ps1 <testdatei> [<testdatei> ...] [-Tail N]'
    Write-Host '            wsl-pytest.ps1 -All   (ganze Suite, nur bewusst)'
    Write-Host 'Beispiel:   wsl-pytest.ps1 tests/unit/test_privacy_audio_reset.py'
    exit 2
}

$mainRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ($mainRoot -notmatch '^([A-Za-z]):[\\/](.*)$') { throw "Unerwarteter Pfad: $mainRoot" }
$wslRoot = '/mnt/' + $Matches[1].ToLower() + '/' + $Matches[2].Replace('\', '/')

if ($All) {
    $targets = ''
    $extra = '-m "not hardware and not wsl"'
} else {
    foreach ($t in $Tests) {
        if ($t -notmatch '^[\w./\-:\[\]]+$') { throw "Ungueltiges Testargument: $t" }
    }
    $targets = ($Tests | ForEach-Object { "'" + $_.Replace('\', '/') + "'" }) -join ' '
    $extra = ''
}

$cmd = "cd '$wslRoot' && /home/alex/jarvis-venv/bin/python3 -m pytest $targets $extra -q -p no:cacheprovider 2>&1 | tail -n $Tail; exit `${PIPESTATUS[0]}"
$env:MSYS_NO_PATHCONV = '1'
& wsl.exe -d Ubuntu-24.04 -e bash -c $cmd
exit $LASTEXITCODE
