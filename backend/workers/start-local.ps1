# TG Monitor 本地测试启动脚本 (PowerShell)
# 用于在本地测试多Worker架构

param(
    [int]$ApiWorkers = 1,
    [int]$MonitorWorkers = 1
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "TG Monitor 本地测试启动" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "API Workers: $ApiWorkers" -ForegroundColor Yellow
Write-Host "Monitor Workers: $MonitorWorkers" -ForegroundColor Yellow
Write-Host ""

$BackendDir = "D:\xiangmu\tg\tg-monitor\backend"
$ProjectDir = "D:\xiangmu\tg\tg-monitor"

# 创建日志目录
New-Item -ItemType Directory -Force -Path "$ProjectDir\logs" | Out-Null
New-Item -ItemType Directory -Force -Path "$ProjectDir\sessions" | Out-Null

# 创建Monitor Worker的Session目录
for ($i = 0; $i -lt $MonitorWorkers; $i++) {
    New-Item -ItemType Directory -Force -Path "$ProjectDir\sessions\worker_$i" | Out-Null
}

Write-Host "启动服务..." -ForegroundColor Green

# 启动API Workers
$apiProcesses = @()
for ($i = 0; $i -lt $ApiWorkers; $i++) {
    $env:WORKER_ID = $i
    $env:WORKER_TYPE = "api"

    Write-Host "启动 API Worker $i (端口: $($i + 8000))..." -ForegroundColor Yellow
    $process = Start-Process -FilePath "python" -ArgumentList "-m", "app.workers.api_worker" `
        -WorkingDirectory $BackendDir `
        -PassThru `
        -WindowStyle Minimized
    $apiProcesses += $process
    Start-Sleep -Seconds 1
}

# 启动Monitor Workers
$monitorProcesses = @()
for ($i = 0; $i -lt $MonitorWorkers; $i++) {
    $env:WORKER_ID = $i
    $env:WORKER_TYPE = "monitor"

    Write-Host "启动 Monitor Worker $i (端口: $($i + 8010))..." -ForegroundColor Yellow
    $process = Start-Process -FilePath "python" -ArgumentList "-m", "app.workers.monitor_worker" `
        -WorkingDirectory $BackendDir `
        -PassThru `
        -WindowStyle Minimized
    $monitorProcesses += $process
    Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "所有服务已启动!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "API Workers:" -ForegroundColor Yellow
for ($i = 0; $i -lt $ApiWorkers; $i++) {
    Write-Host "  Worker $i: http://localhost:$($i + 8000)" -ForegroundColor White
}
Write-Host ""
Write-Host "Monitor Workers:" -ForegroundColor Yellow
for ($i = 0; $i -lt $MonitorWorkers; $i++) {
    Write-Host "  Worker $i: http://localhost:$($i + 8010 + 1000)/status" -ForegroundColor White
}
Write-Host ""
Write-Host "Nginx (如果配置): http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "按 Ctrl+C 停止所有服务" -ForegroundColor Red
Write-Host ""

# 等待用户中断
try {
    while ($true) {
        Start-Sleep -Seconds 10

        # 检查进程状态
        $runningApi = ($apiProcesses | Where-Object { !$_.HasExited }).Count
        $runningMonitor = ($monitorProcesses | Where-Object { !$_.HasExited }).Count

        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] API: $runningApi/$ApiWorkers, Monitor: $runningMonitor/$MonitorWorkers" -ForegroundColor Gray
    }
} finally {
    Write-Host ""
    Write-Host "停止所有服务..." -ForegroundColor Yellow

    $apiProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
    $monitorProcesses | Stop-Process -Force -ErrorAction SilentlyContinue

    Write-Host "所有服务已停止" -ForegroundColor Green
}
