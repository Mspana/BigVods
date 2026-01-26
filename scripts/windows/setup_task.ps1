# PowerShell script to set up the VOD Archiver as a scheduled task
# Run this script as Administrator

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptPath
$vbsPath = Join-Path $scriptPath "run_hidden.vbs"
$taskName = "TwitchVODArchiver"

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Please run this script as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'"
    pause
    exit 1
}

# Remove existing task if it exists
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Create the scheduled task
Write-Host "Creating scheduled task: $taskName" -ForegroundColor Cyan

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$vbsPath`"" -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Automatically archives Twitch VODs to YouTube"

Write-Host ""
Write-Host "Task created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "The archiver will now start automatically when Windows boots."
Write-Host ""
Write-Host "To start it now without rebooting, run:" -ForegroundColor Cyan
Write-Host "  Start-ScheduledTask -TaskName '$taskName'"
Write-Host ""
Write-Host "To check status:" -ForegroundColor Cyan
Write-Host "  Get-ScheduledTask -TaskName '$taskName' | Select-Object State"
Write-Host ""
Write-Host "To stop it:" -ForegroundColor Cyan
Write-Host "  Stop-ScheduledTask -TaskName '$taskName'"
Write-Host ""
Write-Host "To remove the task:" -ForegroundColor Cyan
Write-Host "  Unregister-ScheduledTask -TaskName '$taskName'"
Write-Host ""
pause
