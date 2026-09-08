<#
.SYNOPSIS
    Vision Stream Bridge Windows Background Service Manager.
.DESCRIPTION
    Installs, uninstalls, starts, stops, and monitors the Vision server as an automatic background service.
.PARAMETER Action
    install, uninstall, start, stop, restart, status
#>

param (
    [Parameter(Position = 0, Mandatory = $false)]
    [ValidateSet("install", "uninstall", "start", "stop", "restart", "status")]
    [string]$Action = "status"
)

$TaskName = "VisionStreamBridge"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VbsPath = Join-Path $ScriptDir "run_hidden.vbs"
$PidFile = Join-Path $ScriptDir "service.pid"
$LogFile = Join-Path $ScriptDir "service.log"
$StartupShortcut = Join-Path ([Environment]::GetFolderPath("Startup")) "VisionStreamBridge.lnk"
$HttpPort = 8765

function Get-RunningProcess {
    if (Test-Path $PidFile) {
        $pidVal = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($pidVal) {
            $proc = Get-Process -Id ([int]$pidVal) -ErrorAction SilentlyContinue
            if ($proc) { return $proc }
        }
    }
    # Fallback: check process bound to port 8765
    $conn = Get-NetTCPConnection -LocalPort $HttpPort -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        if ($proc) { return $proc }
    }
    return $null
}

function Start-ServiceInstance {
    Write-Host "[*] Starting Vision Stream Bridge background service..." -ForegroundColor Cyan
    $proc = Get-RunningProcess
    if ($proc) {
        Write-Host "[!] Service is already running with PID: $($proc.Id)" -ForegroundColor Yellow
        return
    }

    Start-Process -FilePath "wscript.exe" -ArgumentList "`"$VbsPath`"" -WorkingDirectory $ScriptDir
    Start-Sleep -Seconds 2

    $proc = Get-RunningProcess
    if ($proc) {
        Write-Host "[+] Service started successfully (PID: $($proc.Id))" -ForegroundColor Green
    } else {
        Write-Host "[!] Service launched. Checking initial status..." -ForegroundColor Yellow
    }
}

function Stop-ServiceInstance {
    Write-Host "[*] Stopping Vision Stream Bridge background service..." -ForegroundColor Cyan
    $proc = Get-RunningProcess
    if ($proc) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        Write-Host "[+] Terminated process PID: $($proc.Id)" -ForegroundColor Green
    } else {
        Write-Host "[-] No active service process found." -ForegroundColor Gray
    }

    if (Test-Path $PidFile) {
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
}

function Show-ServiceStatus {
    Write-Host "============================================================" -ForegroundColor DarkCyan
    Write-Host "         VISION STREAM BRIDGE SERVICE STATUS                " -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor DarkCyan

    $proc = Get-RunningProcess
    $scheduledTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    $hasStartup = Test-Path $StartupShortcut

    if ($scheduledTask) {
        Write-Host "  Windows Task   : Registered ($($scheduledTask.State))" -ForegroundColor Green
    } else {
        Write-Host "  Windows Task   : Not Registered" -ForegroundColor Gray
    }

    if ($hasStartup) {
        Write-Host "  Startup Shortcut: Installed (Auto-start on Windows login)" -ForegroundColor Green
    } else {
        Write-Host "  Startup Shortcut: None" -ForegroundColor Gray
    }

    if ($proc) {
        Write-Host "  Process Status : RUNNING (PID: $($proc.Id))" -ForegroundColor Green
        Write-Host "  Memory Usage   : $([math]::Round($proc.WorkingSet64 / 1MB, 2)) MB" -ForegroundColor White
        Write-Host "  Uptime Started : $($proc.StartTime)" -ForegroundColor White

        try {
            $apiStatus = Invoke-RestMethod -Uri "http://127.0.0.1:$HttpPort/api/status" -TimeoutSec 2 -ErrorAction Stop
            Write-Host "`n  Proxy Endpoints:" -ForegroundColor Cyan
            Write-Host "    - MJPEG Stream     : $($apiStatus.proxy_urls.mjpeg_stream)" -ForegroundColor White
            Write-Host "    - WebSocket Proxy  : $($apiStatus.proxy_urls.websocket_proxy)" -ForegroundColor White
            Write-Host "    - Frame Snapshot   : $($apiStatus.proxy_urls.snapshot)" -ForegroundColor White
            Write-Host "    - Phone Connected  : $($apiStatus.metrics.phone_connected)" -ForegroundColor $(if ($apiStatus.metrics.phone_connected) { "Green" } else { "Yellow" })
        } catch {
            Write-Host "  [!] Server port $HttpPort open, but /api/status not yet responding." -ForegroundColor Yellow
        }
    } else {
        Write-Host "  Process Status : STOPPED" -ForegroundColor Red
    }

    if (Test-Path $LogFile) {
        Write-Host "`n--- Recent Service Logs (service.log) ---" -ForegroundColor DarkGray
        Get-Content $LogFile -Tail 6 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    }
    Write-Host "============================================================" -ForegroundColor DarkCyan
}

function Install-ServiceInstance {
    Write-Host "[*] Installing Vision Stream Bridge as a 24/7 background service..." -ForegroundColor Cyan

    # 1. Register Windows Scheduled Task (Runs hidden on user login / startup)
    try {
        $action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VbsPath`"" -WorkingDirectory $ScriptDir
        $trigger = New-ScheduledTaskTrigger -AtLogOn
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 365)
        $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

        Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force -ErrorAction Stop | Out-Null
        Write-Host "[+] Registered Windows Scheduled Task: $TaskName" -ForegroundColor Green
    } catch {
        Write-Host "[*] Scheduled task requires elevation. Falling back to Windows Startup service." -ForegroundColor Yellow
    }

    # 2. Create Windows Startup Shortcut (Ensures auto-start on every login)
    try {
        $wshShell = New-Object -ComObject WScript.Shell
        $shortcut = $wshShell.CreateShortcut($StartupShortcut)
        $shortcut.TargetPath = "wscript.exe"
        $shortcut.Arguments = "`"$VbsPath`""
        $shortcut.WorkingDirectory = $ScriptDir
        $shortcut.WindowStyle = 7 # Minimized/Hidden
        $shortcut.Description = "Vision Stream Bridge Background Video Proxy Service"
        $shortcut.Save()
        Write-Host "[+] Created Windows Startup shortcut: $StartupShortcut" -ForegroundColor Green
    } catch {
        Write-Host "[!] Could not create Startup folder shortcut: $_" -ForegroundColor Yellow
    }

    # 3. Start the service now
    Start-ServiceInstance
    Show-ServiceStatus
}

function Uninstall-ServiceInstance {
    Write-Host "[*] Uninstalling Vision Stream Bridge background service..." -ForegroundColor Cyan

    # 1. Stop running process
    Stop-ServiceInstance

    # 2. Remove Windows Scheduled Task
    try {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "[+] Removed Scheduled Task: $TaskName" -ForegroundColor Green
    } catch {}

    # 3. Remove Startup Shortcut
    if (Test-Path $StartupShortcut) {
        Remove-Item $StartupShortcut -Force -ErrorAction SilentlyContinue
        Write-Host "[+] Removed Startup shortcut" -ForegroundColor Green
    }

    Write-Host "[+] Uninstallation complete." -ForegroundColor Green
}

switch ($Action) {
    "install"   { Install-ServiceInstance }
    "uninstall" { Uninstall-ServiceInstance }
    "start"     { Start-ServiceInstance }
    "stop"      { Stop-ServiceInstance }
    "restart"   { Stop-ServiceInstance; Start-Sleep -Seconds 2; Start-ServiceInstance }
    "status"    { Show-ServiceStatus }
}
