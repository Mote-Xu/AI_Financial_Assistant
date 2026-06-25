@echo off
REM AI 财务助手 — 启动 Web Dashboard + 公网隧道
REM 手机扫码/打开 tunnel URL 即可远程触发体检

cd /d "%~dp0"

:: 尝试 conda
if exist "C:\Users\Haoze\anaconda3\Scripts\activate.bat" (
    call C:\Users\Haoze\anaconda3\Scripts\activate.bat deepseek_v4_api
    goto :run
)

python --version >nul 2>&1
if %errorlevel% equ 0 goto :run

echo [ERROR] 未找到 Python
exit /b 1

:run
set PYTHONIOENCODING=utf-8
set NO_PROXY=*

echo ==============================================
echo   AI 财务助手 - Web Dashboard
echo   本地: http://localhost:5000/control
echo ==============================================

:: 先启动 Flask（后台窗口）
start "AI-Finance-Flask" /min python scripts\webapp.py --prod
timeout /t 3 >nul

:: 再启动公网隧道（前台窗口，显示 URL，Ctrl+C 停止）
python scripts\start_tunnel.py
