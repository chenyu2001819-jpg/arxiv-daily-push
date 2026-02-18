# arXiv Agent Windows 定时任务设置脚本
# 以管理员身份运行 PowerShell 后执行此脚本

$TaskName = "ArxivDailyAgent"
$WorkingDir = $PSScriptRoot
$PythonPath = (Get-Command python).Source

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  arXiv Agent Windows 定时任务设置" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 检查是否以管理员身份运行
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "[错误] 请以管理员身份运行 PowerShell！" -ForegroundColor Red
    Write-Host "提示: 右键点击 PowerShell 图标，选择'以管理员身份运行'"
    exit 1
}

# 检查文件是否存在
if (-NOT (Test-Path "$WorkingDir\scheduler.py")) {
    Write-Host "[错误] 未找到 scheduler.py，请确保在工作目录中运行此脚本" -ForegroundColor Red
    exit 1
}

# 检查邮件配置
$ConfigFile = "$WorkingDir\config.yaml"
if (Test-Path $ConfigFile) {
    $ConfigContent = Get-Content $ConfigFile -Raw
    if ($ConfigContent -match 'enabled:\s*true') {
        Write-Host "[信息] 检测到邮件推送已启用" -ForegroundColor Green
    } else {
        Write-Host "[警告] 邮件推送未启用（config.yaml 中 email.enabled = false）" -ForegroundColor Yellow
        Write-Host "如需邮件推送，请先编辑 config.yaml 启用邮件功能" -ForegroundColor Yellow
    }
}

Write-Host "[信息] 工作目录: $WorkingDir" -ForegroundColor Green
Write-Host "[信息] Python 路径: $PythonPath" -ForegroundColor Green
Write-Host ""

# 删除旧任务（如果存在）
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "[信息] 删除已存在的任务..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# 询问执行时间
Write-Host "请设置每日执行时间（24小时制，格式 HH:MM，默认 09:00）:" -ForegroundColor Cyan
$TimeInput = Read-Host "执行时间"
if ([string]::IsNullOrWhiteSpace($TimeInput)) {
    $TimeInput = "09:00"
}

# 设置任务参数
$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument "scheduler.py --run-once" -WorkingDirectory $WorkingDir

# 设置触发器
$Trigger = New-ScheduledTaskTrigger -Daily -At $TimeInput

# 设置任务设置
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# 注册任务
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "arXiv 每日文章推送智能体 - 自动抓取论文并邮件推送" | Out-Null

Write-Host ""
Write-Host "[成功] 定时任务已创建！" -ForegroundColor Green
Write-Host ""
Write-Host "任务详情：" -ForegroundColor Cyan
Write-Host "  - 任务名称: $TaskName"
Write-Host "  - 执行时间: 每天 $TimeInput"
Write-Host "  - 执行命令: python scheduler.py --run-once"
Write-Host "  - 工作目录: $WorkingDir"
Write-Host ""
Write-Host "管理命令：" -ForegroundColor Cyan
Write-Host "  - 查看任务: Get-ScheduledTask -TaskName $TaskName"
Write-Host "  - 立即运行: Start-ScheduledTask -TaskName $TaskName"
Write-Host "  - 删除任务: Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
Write-Host "  - 查看日志: Get-Content logs/scheduler_`$(Get-Date -Format 'yyyyMM').log -Tail 50"
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan

# 询问是否立即运行
$runNow = Read-Host "是否立即运行一次？(Y/N，默认 N)"
if ($runNow -eq "Y" -or $runNow -eq "y") {
    Write-Host "[信息] 正在启动任务..." -ForegroundColor Yellow
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "[信息] 任务已启动！" -ForegroundColor Green
    Write-Host "[信息] 请查看 daily_papers 目录获取结果，查看 logs 目录获取日志" -ForegroundColor Green
}

Write-Host ""
Write-Host "提示: 任务将在后台运行，即使没有登录也会执行。" -ForegroundColor Green
Write-Host "      邮件推送结果请查看邮箱或本地日志文件。" -ForegroundColor Green
