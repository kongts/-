@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
  set "PYTHON_EXE=python"
)
"%PYTHON_EXE%" -m quant_futures_bot.auto_altcoin_optimizer --interval-minutes 60 --run-once-first --min-score 0 --max-leaders 30 --min-trades 4 --min-side-ratio 0 --fold-count 4 --min-profitable-fold-ratio 0.25
