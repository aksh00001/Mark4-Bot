$BotDir = "c:\Users\akshu\OneDrive\Desktop\TESTapp"
$VbsPath = Join-Path $BotDir "silent_start.vbs"
$TaskName = "JARVIS_Sentinel_Admin"

# 1. Clean up old non-admin triggers
$StartupFolder = [System.Environment]::GetFolderPath("Startup")
$OldLnk = Join-Path $StartupFolder "TelegramBot.lnk"
if (Test-Path $OldLnk) { Remove-Item $OldLnk -Force }

# 2. Create the Admin Task (Run with Highest Privileges)
# This task runs wscript.exe invisibly
$Action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VbsPath`"" -WorkingDirectory $BotDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force

Write-Host "✅ [ADMIN PROTOCOL ESTABLISHED]" -ForegroundColor Cyan
Write-Host "The bot is now configured to start as Administrator at every logon."
Write-Host "You will never see a UAC prompt again, and it will have Full Rights."
