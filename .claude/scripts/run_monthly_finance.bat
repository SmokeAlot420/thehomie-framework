@echo off
REM Monthly finance report runner for Windows Task Scheduler
REM This script runs the monthly finance report via UV
REM Schedule: 1st of each month at 8 AM

cd /d "%~dp0"

REM Run monthly finance report using UV
uv run python memory_monthly_finance.py

REM Log the run
echo %date% %time% - Monthly finance report completed >> monthly_finance_runs.log
