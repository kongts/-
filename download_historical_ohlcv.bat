@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
  set "PYTHON_EXE=python"
)
"%PYTHON_EXE%" -m quant_futures_bot.historical_data --start 2022-01-01 --end 2026-01-01 --timeframes 15m,30m,1h,4h,6h --include-main --include-altcoin-latest --include-macro-latest

