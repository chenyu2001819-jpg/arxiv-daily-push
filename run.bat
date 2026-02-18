@echo off
chcp 65001 >nul
echo ==========================================
echo    arXiv 每日文章推送智能体
echo ==========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请确保 Python 已安装并添加到 PATH
    pause
    exit /b 1
)

REM 检查依赖
if not exist "venv" (
    echo [信息] 创建虚拟环境...
    python -m venv venv
)

echo [信息] 激活虚拟环境...
call venv\Scripts\activate.bat

echo [信息] 安装依赖...
pip install -q -r requirements.txt

echo.
echo 请选择操作：
echo   1. 立即执行并发送邮件
echo   2. 仅生成本地报告（不发送邮件）
echo   3. 测试邮件配置
echo   4. 启动定时调度器
choice /c 1234 /n /m "请输入选项 (1-4): "

if errorlevel 4 goto scheduler
if errorlevel 3 goto test_email
if errorlevel 2 goto no_email
if errorlevel 1 goto with_email

:with_email
echo.
echo [信息] 启动智能体（将发送邮件）...
python arxiv_agent.py
goto end

:no_email
echo.
echo [信息] 启动智能体（不发送邮件）...
python arxiv_agent.py --no-email
goto end

:test_email
echo.
echo [信息] 测试邮件配置...
python test_email.py
goto end

:scheduler
echo.
echo [信息] 启动定时调度器...
python scheduler.py

:end
echo.
echo ==========================================
echo 按任意键退出...
pause >nul
