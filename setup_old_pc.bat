@echo off
REM AI 财务助手 — 老电脑一键部署
REM 用法：1. 把整个项目文件夹拷到老电脑
REM       2. 双击此文件
REM       3. 复制 .env 文件过来（含 API Key）

echo ========================================
echo   AI 财务助手 - 老电脑部署
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Python，请先安装: https://python.org
    pause
    exit /b 1
)
echo [OK] Python 已安装

REM 安装依赖
echo [*] 安装 Python 依赖...
pip install akshare openai pandas python-dotenv requests matplotlib -q
echo [OK] 依赖安装完成

REM 检查 .env
if not exist .env (
    echo [WARN] 未找到 .env 文件！
    echo       请从主电脑复制 .env 到当前目录
    echo       内容: DEEPSEEK_API_KEY + WECOM_WEBHOOK_KEY
)

REM 配置定时任务（每周五 15:30）
echo.
echo [*] 配置定时任务（每周一至周五 15:30）...
set BAT_PATH=%~dp0run_auto.bat

schtasks /create /tn "AI_Finance_Auto" /tr "%BAT_PATH%" /sc daily /st 15:30 /f >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] 定时任务已配置（每日 15:30）
) else (
    echo [WARN] 定时任务配置失败，请手动运行：
    echo       schtasks /create /tn "AI_Finance_Auto" /tr "%BAT_PATH%" /sc daily /st 15:30
)

echo.
echo ========================================
echo   部署完成！
echo   每日 15:30 自动运行体检 → 企微推送
echo   手动测试: python scripts/auto_runner.py
echo ========================================
pause
