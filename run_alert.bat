@echo off
REM 市场波动预警 — 每日 14:50 运行
REM 添加到 Windows 任务计划程序：schtasks /create /tn "AI_Finance_Alert" /tr "路径\run_alert.bat" /sc daily /st 14:50

cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set NO_PROXY=*

if exist "C:\Users\Haoze\anaconda3\Scripts\activate.bat" (
    call C:\Users\Haoze\anaconda3\Scripts\activate.bat deepseek_v4_api
    goto :run
)
python --version >nul 2>&1 && goto :run
echo [ERROR] 未找到 Python
exit /b 1

:run
python scripts\auto_runner.py --alert
echo [%date% %time%] Alert check completed >> auto_run.log
