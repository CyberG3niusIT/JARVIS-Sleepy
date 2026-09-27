[CmdletBinding()]
param(
    [string]$Configuration = 'Release',
    [string]$OutputDirectory = (Join-Path $PSScriptRoot 'artifacts\publish')
)

$ErrorActionPreference = 'Stop'
$projectPath = Join-Path $PSScriptRoot 'Jarvis.ControlHub.csproj'
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputDirectory)
$allowedRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'artifacts'))
if (-not $resolvedOutput.StartsWith($allowedRoot + [System.IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Publish-Ziel muss innerhalb von '$allowedRoot' liegen."
}

$dotnet = Join-Path $env:USERPROFILE '.dotnet\dotnet.exe'
if (-not (Test-Path -LiteralPath $dotnet -PathType Leaf)) {
    $dotnet = (Get-Command dotnet -ErrorAction Stop).Source
}

New-Item -ItemType Directory -Path $resolvedOutput -Force | Out-Null
& $dotnet publish $projectPath --configuration $Configuration --runtime win-x64 --self-contained true `
    -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:DebugType=embedded `
    -p:PublishDir="$resolvedOutput\"
if ($LASTEXITCODE -ne 0) {
    throw "dotnet publish fehlgeschlagen (Exit-Code $LASTEXITCODE)."
}

$executable = Join-Path $resolvedOutput 'Jarvis.ControlHub.exe'
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw 'dotnet publish war erfolgreich, aber Jarvis.ControlHub.exe fehlt im Ausgabeordner.'
}
Write-Output $executable
