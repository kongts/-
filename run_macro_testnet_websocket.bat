@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
  set "PYTHON_EXE=python"
)
"%PYTHON_EXE%" -m quant_futures_bot.macro_websocket_monitor --top 0 --candle-limit 300 --print-seconds 5 --maintenance-seconds 30 --leader-refresh-seconds 60 --live-signal-seconds 60
