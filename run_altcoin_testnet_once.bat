@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
  set "PYTHON_EXE=python"
)
set "EXECUTION_MODE=testnet"
"%PYTHON_EXE%" -m quant_futures_bot.altcoin_paper_monitor --run-once --top 0 --execution-mode testnet --confirm-exchange-orders YES --order-type limit --maker-offset 0.001 --crash-watch-drop-pct 0.03 --crash-watch-breadth-ratio 0.6 --crash-short-trailing-pct 0.03 --open-order-timeout-seconds 180 --close-order-timeout-seconds 60 --max-order-failures 3 --max-hold-bars-15m 8 --max-hold-bars-30m 6 --extended-hold-bars-15m 4 --extended-hold-bars-30m 3 --min-profit-to-extend 0.03 --trailing-after-max-hold-pct 0.03
