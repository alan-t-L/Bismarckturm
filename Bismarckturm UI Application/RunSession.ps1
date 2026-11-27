<#
.SYNOPSIS
    Run window for the Bismarckturm UI (acts as the app's own "profile").

.DESCRIPTION
    Started by BismarckturmUI.ps1 with -NoProfile, so the user's $PROFILE (for
    example a full-screen window setting) is NOT applied. This script sets a
    normal window size and title, switches to the working folder, then runs the
    command that the UI generated and validated. The window stays open
    afterwards so output, warnings and errors can be read.
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$WorkingFolder,

    [Parameter(Mandatory = $true)]
    [string]$CommandFile
)

$ErrorActionPreference = 'Continue'

# Window size and title (ignored quietly if the host does not allow resizing).
try {
    $ui = $Host.UI.RawUI
    $max = $ui.MaxPhysicalWindowSize
    $width = [math]::Min(120, $max.Width)
    $height = [math]::Min(40, $max.Height)

    $current = $ui.WindowSize
    if ($current.Width -gt $width -or $current.Height -gt $height) {
        $ui.WindowSize = New-Object System.Management.Automation.Host.Size(
            [math]::Min($current.Width, $width), [math]::Min($current.Height, $height))
    }
    $ui.BufferSize = New-Object System.Management.Automation.Host.Size($width, 3000)
    $ui.WindowSize = New-Object System.Management.Automation.Host.Size($width, $height)
    $ui.WindowTitle = 'Bismarckturm - model generator'
}
catch {
    # Not fatal: continue with the default window.
}

# Read the command, then delete the temporary file straight away.
$commandText = Get-Content -LiteralPath $CommandFile -Raw
Remove-Item -LiteralPath $CommandFile -Force -ErrorAction SilentlyContinue

Set-Location -LiteralPath $WorkingFolder

Write-Host 'Bismarckturm - running this command:' -ForegroundColor Cyan
Write-Host ''
Write-Host $commandText
Write-Host ''
Write-Host ('-' * 70) -ForegroundColor DarkGray

try {
    & ([scriptblock]::Create($commandText))
}
catch {
    Write-Host ''
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ''
Write-Host ('-' * 70) -ForegroundColor DarkGray
Write-Host 'Finished. This window stays open; type "exit" to close it.' -ForegroundColor Cyan
