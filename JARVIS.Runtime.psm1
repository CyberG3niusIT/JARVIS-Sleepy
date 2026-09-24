Set-StrictMode -Version Latest

$script:JarvisDistro = 'Ubuntu-24.04'
$script:JarvisRuntimeInvoker = $null
$script:JarvisKeepaliveEnsureInvoker = $null
$script:JarvisKeepaliveStopInvoker = $null

function Get-JarvisKeepaliveIdentity {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$RepositoryRoot)

    $bytes = [System.Text.Encoding]::UTF8.GetBytes($RepositoryRoot.ToLowerInvariant())
    $hash = [System.BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes)).Replace('-', '').ToLowerInvariant().Substring(0, 16)
    [pscustomobject]@{
        Marker = "jarvis_keepalive_$hash"
        StateDirectory = Join-Path (Join-Path $env:LOCALAPPDATA 'JARVIS\Runtime') $hash
    }
}

function Get-JarvisKeepaliveProcesses {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Marker)

    $wsl = (Get-Command 'wsl.exe' -ErrorAction Stop).Source
    $escapedMarker = [System.Text.RegularExpressions.Regex]::Escape($Marker)
    $allProcesses = @(Get-CimInstance -ClassName Win32_Process -Filter "Name = 'wsl.exe'" -ErrorAction Stop)
    $matches = @($allProcesses | Where-Object {
        $_.ExecutablePath -and
        [string]::Equals([System.IO.Path]::GetFullPath($_.ExecutablePath), [System.IO.Path]::GetFullPath($wsl), [System.StringComparison]::OrdinalIgnoreCase) -and
        $_.CommandLine -and
        $_.CommandLine -match "--distribution\s+$([System.Text.RegularExpressions.Regex]::Escape($script:JarvisDistro))\s+--exec\s+/usr/bin/bash\s+-c\s+`"exec\s+-a\s+$escapedMarker\s+/usr/bin/sleep\s+infinity`""
    })
    $matchedIds = @($matches | ForEach-Object { [int]$_.ProcessId })
    @($matches | Where-Object { [int]$_.ParentProcessId -notin $matchedIds })
}

function Ensure-JarvisKeepalive {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$RepositoryRoot)

    if ($null -ne $script:JarvisKeepaliveEnsureInvoker) {
        return [bool](& $script:JarvisKeepaliveEnsureInvoker $RepositoryRoot)
    }

    $identity = Get-JarvisKeepaliveIdentity -RepositoryRoot $RepositoryRoot
    $existing = @(Get-JarvisKeepaliveProcesses -Marker $identity.Marker)
    if ($existing.Count -gt 1) {
        throw 'Mehrere JARVIS-WSL-Keepalives mit derselben Runtime-Identität laufen; es wurde kein weiterer gestartet.'
    }
    if ($existing.Count -eq 1) {
        return $false
    }

    $null = New-Item -ItemType Directory -Path $identity.StateDirectory -Force
    $statePath = Join-Path $identity.StateDirectory 'keepalive.json'
    $state = [ordered]@{
        distribution = $script:JarvisDistro
        marker = $identity.Marker
        processId = $null
        startedUtc = [DateTime]::UtcNow.ToString('o')
    }
    $temporaryStatePath = "$statePath.$([Guid]::NewGuid().ToString('N')).tmp"
    try {
        $state | ConvertTo-Json | Set-Content -LiteralPath $temporaryStatePath -Encoding UTF8
        Move-Item -LiteralPath $temporaryStatePath -Destination $statePath -Force
        $wsl = Get-Command 'wsl.exe' -ErrorAction Stop
        $arguments = @('--distribution', $script:JarvisDistro, '--exec', '/usr/bin/bash', '-c', '"exec -a ' + $identity.Marker + ' /usr/bin/sleep infinity"')
        $process = Start-Process -FilePath $wsl.Source -ArgumentList $arguments -WindowStyle Hidden -PassThru -ErrorAction Stop
        Start-Sleep -Milliseconds 750
        $process.Refresh()
        if ($process.HasExited) {
            throw "Der JARVIS-WSL-Keepalive wurde unmittelbar beendet (exit $($process.ExitCode))."
        }
        $state.processId = $process.Id
        $temporaryStatePath = "$statePath.$([Guid]::NewGuid().ToString('N')).tmp"
        $state | ConvertTo-Json | Set-Content -LiteralPath $temporaryStatePath -Encoding UTF8
        Move-Item -LiteralPath $temporaryStatePath -Destination $statePath -Force
        return $true
    } catch {
        Remove-Item -LiteralPath $temporaryStatePath -Force -ErrorAction SilentlyContinue
        $owned = @(Get-JarvisKeepaliveProcesses -Marker $identity.Marker -ErrorAction SilentlyContinue)
        foreach ($candidate in $owned) {
            if ($state.processId -and [int]$candidate.ProcessId -ne [int]$state.processId) { continue }
            try {
                $null = & (Get-Command 'wsl.exe' -ErrorAction Stop).Source --distribution $script:JarvisDistro --exec /usr/bin/pkill --signal TERM --full --exact "^$($identity.Marker) infinity$" 2>$null
            } catch { }
        }
        Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
        throw
    }
}

function Stop-JarvisKeepalive {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$RepositoryRoot)

    if ($null -ne $script:JarvisKeepaliveStopInvoker) {
        & $script:JarvisKeepaliveStopInvoker $RepositoryRoot
        return
    }

    $identity = Get-JarvisKeepaliveIdentity -RepositoryRoot $RepositoryRoot
    $statePath = Join-Path $identity.StateDirectory 'keepalive.json'
    $owned = @(Get-JarvisKeepaliveProcesses -Marker $identity.Marker)
    if ($owned.Count -gt 1) {
        throw 'Mehrere JARVIS-WSL-Keepalives mit derselben Runtime-Identität laufen; Stop wurde aus Sicherheitsgründen abgebrochen.'
    }
    if ($owned.Count -eq 1) {
        $processId = [int]$owned[0].ProcessId
        $null = & (Get-Command 'wsl.exe' -ErrorAction Stop).Source --distribution $script:JarvisDistro --exec /usr/bin/pkill --signal TERM --full --exact "^$($identity.Marker) infinity$"
        if ($LASTEXITCODE -notin @(0, 1)) {
            throw "Das JARVIS-WSL-Keepalive konnte nicht sauber beendet werden (pkill exit $LASTEXITCODE)."
        }
        for ($attempt = 0; $attempt -lt 50; $attempt++) {
            $stillOwned = @(Get-JarvisKeepaliveProcesses -Marker $identity.Marker)
            if (-not ($stillOwned | Where-Object { [int]$_.ProcessId -eq $processId })) { break }
            Start-Sleep -Milliseconds 100
        }
        if (@(Get-JarvisKeepaliveProcesses -Marker $identity.Marker).Count -gt 0) {
            throw 'Das JARVIS-WSL-Keepalive reagiert nicht auf den sauberen Stop.'
        }
    }
    Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
}

function Invoke-JarvisWsl {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][ValidateSet('start', 'stop', 'restart')][string]$Action,
        [string]$RepositoryRoot = $PSScriptRoot
    )

    $resolvedRoot = (Resolve-Path -LiteralPath $RepositoryRoot -ErrorAction Stop).Path
    $identity = Get-JarvisKeepaliveIdentity -RepositoryRoot $resolvedRoot
    $mutex = [System.Threading.Mutex]::new($false, "Local\JARVIS_Runtime_$($identity.Marker)")
    $hasMutex = $false
    $startedKeepalive = $false
    try {
        try { $hasMutex = $mutex.WaitOne([TimeSpan]::FromMinutes(5)) }
        catch [System.Threading.AbandonedMutexException] { $hasMutex = $true }
        if (-not $hasMutex) { throw 'Ein anderer JARVIS-Lifecycle-Aufruf hat den Lock nicht rechtzeitig freigegeben.' }

        if ($null -ne $script:JarvisRuntimeInvoker) {
            if ($Action -in @('start', 'restart')) {
                $startedKeepalive = Ensure-JarvisKeepalive -RepositoryRoot $resolvedRoot
            }
            & $script:JarvisRuntimeInvoker $Action $resolvedRoot
            if ($Action -eq 'stop') { Stop-JarvisKeepalive -RepositoryRoot $resolvedRoot }
            return
        }
    $wsl = Get-Command 'wsl.exe' -ErrorAction Stop
    $null = & $wsl.Source --distribution $script:JarvisDistro --exec /usr/bin/test -x /usr/bin/bash
    if ($LASTEXITCODE -ne 0) {
        throw "WSL-Distribution '$($script:JarvisDistro)' ist nicht verfügbar oder kein Ubuntu-System."
    }

    $relativeScript = switch ($Action) {
        'start' { 'start.sh' }
        'stop' { 'stop.sh' }
        'restart' { 'restart.sh' }
    }
    $wslPathOutput = & $wsl --distribution $script:JarvisDistro --exec wslpath -u $resolvedRoot
    if ($LASTEXITCODE -ne 0 -or -not $wslPathOutput) {
        throw 'Der Repository-Pfad konnte nicht in einen WSL-Pfad übersetzt werden.'
    }
    $wslRoot = ([string]$wslPathOutput).Trim()
    $null = & $wsl --distribution $script:JarvisDistro --cd $wslRoot --exec /usr/bin/test -f "./$relativeScript"
    if ($LASTEXITCODE -ne 0) {
        throw "Das Lifecycle-Skript '$relativeScript' fehlt im WSL-Checkout."
    }
    $null = & $wsl --distribution $script:JarvisDistro --cd $wslRoot --exec systemctl --user show-environment
    if ($LASTEXITCODE -ne 0) {
        throw 'Der systemd User-Manager in WSL ist nicht erreichbar.'
    }
        if ($Action -in @('start', 'restart')) {
            $startedKeepalive = Ensure-JarvisKeepalive -RepositoryRoot $resolvedRoot
        }
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # Windows PowerShell can promote native stderr to an error record. Keep
        # it non-terminating here so we can preserve the lifecycle's diagnosis.
        $ErrorActionPreference = 'Continue'
        $runtimeOutput = & $wsl.Source --distribution $script:JarvisDistro --cd $wslRoot --exec /usr/bin/bash "./$relativeScript" 2>&1
        $runtimeExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    foreach ($line in @($runtimeOutput)) {
        [Console]::Out.WriteLine([string]$line)
    }
    if ($runtimeExitCode -ne 0) {
        throw "JARVIS-$Action ist fehlgeschlagen (WSL exit $runtimeExitCode)."
    }
        if ($Action -eq 'stop') { Stop-JarvisKeepalive -RepositoryRoot $resolvedRoot }
    } catch {
        if ($startedKeepalive) {
            try { Stop-JarvisKeepalive -RepositoryRoot $resolvedRoot }
            catch { Write-Warning "Der in diesem Startlauf erzeugte Keepalive konnte nicht bereinigt werden: $($_.Exception.Message)" }
        }
        throw
    } finally {
        if ($hasMutex) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
}

function Start-JarvisRuntime {
    [CmdletBinding()]
    param([string]$RepositoryRoot = $PSScriptRoot)
    Invoke-JarvisWsl -Action start -RepositoryRoot $RepositoryRoot
}

function Stop-JarvisRuntime {
    [CmdletBinding()]
    param([string]$RepositoryRoot = $PSScriptRoot)
    Invoke-JarvisWsl -Action stop -RepositoryRoot $RepositoryRoot
}

function Restart-JarvisRuntime {
    [CmdletBinding()]
    param([string]$RepositoryRoot = $PSScriptRoot)
    Invoke-JarvisWsl -Action restart -RepositoryRoot $RepositoryRoot
}

Export-ModuleMember -Function Start-JarvisRuntime, Stop-JarvisRuntime, Restart-JarvisRuntime
