@echo off
set "PYTHON_EXE=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
if not exist "%PYTHON_EXE%" (
  echo Python not found: %PYTHON_EXE%
  echo Please install Python 3.11+ or update PYTHON_EXE in this file.
  exit /b 1
)
"%PYTHON_EXE%" -m quant_futures_bot.auto_altcoin_optimizer --interval-minutes 60 --run-once-first --min-score 0 --max-leaders 30 --min-trades 4 --min-side-ratio 0 --fold-count 4 --min-profitable-fold-ratio 0.25
