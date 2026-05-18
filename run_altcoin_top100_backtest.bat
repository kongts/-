@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
  set "PYTHON_EXE=python"
)
"%PYTHON_EXE%" -m quant_futures_bot.altcoin_top_volume_backtest --top 100 --limit 1000 --timeframes 15m,30m --show 30 --min-trades 4 --min-side-ratio 0 --fold-count 4 --min-profitable-fold-ratio 0.25
