@echo off
REM 每日情报简报 — Windows Task Scheduler
REM 用法:
REM   run_briefing.bat           早间全量简报
REM   run_briefing.bat --midday  午间补充

cd /d %~dp0

set CONDA_PATH=C:\Users\Haoze\anaconda3
set ENV_NAME=deepseek_v4_api

if "%1"=="--midday" (
    call %CONDA_PATH%\Scripts\activate.bat %ENV_NAME% && python scripts\auto_runner.py --briefing --midday
) else (
    call %CONDA_PATH%\Scripts\activate.bat %ENV_NAME% && python scripts\auto_runner.py --briefing
)
