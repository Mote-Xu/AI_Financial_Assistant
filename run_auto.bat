@echo off
REM AI 财务助手 — 定时自动运行
REM 支持 conda 或纯 pip 环境，自动检测

cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set NO_PROXY=*

REM 尝试 conda 环境（主电脑）
if exist "C:\Users\Haoze\anaconda3\Scripts\activate.bat" (
    call C:\Users\Haoze\anaconda3\Scripts\activate.bat deepseek_v4_api
    goto :run
)

REM 尝试系统 Python（老电脑/纯 pip）
python --version >nul 2>&1
if %errorlevel% equ 0 goto :run

echo [ERROR] 未找到 Python，请先安装
exit /b 1

:run
python scripts\auto_runner.py --prompt monthly_review
echo [%date% %time%] Auto run completed >> auto_run.log
