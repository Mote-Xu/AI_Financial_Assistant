@echo off
REM AI 财务助手 — 定时自动运行
REM 添加到 Windows 任务计划程序即可每月/每周自动体检
REM 用法：手动双击运行，或添加到计划任务

cd /d E:\Desktop\AI_Financial_Assistant

REM 激活 conda 环境并运行
call C:\Users\Haoze\anaconda3\Scripts\activate.bat deepseek_v4_api
set PYTHONIOENCODING=utf-8
set NO_PROXY=*

python scripts/auto_runner.py --prompt monthly_review

REM 记录日志
echo [%date% %time%] Auto run completed >> auto_run.log
