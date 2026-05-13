@echo off
set "PYTHON_EXE=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
if not exist "%PYTHON_EXE%" (
  echo Python not found: %PYTHON_EXE%
  echo Please install Python 3.11+ or update PYTHON_EXE in this file.
  exit /b 1
)
if "%BINANCE_TESTNET_API_KEY%"=="" (
  echo Missing BINANCE_TESTNET_API_KEY environment variable.
  exit /b 1
)
if "%BINANCE_TESTNET_API_SECRET%"=="" (
  echo Missing BINANCE_TESTNET_API_SECRET environment variable.
  exit /b 1
)
set "EXECUTION_MODE=testnet"
"%PYTHON_EXE%" -m quant_futures_bot.altcoin_paper_monitor --run-once --top 5 --execution-mode testnet --confirm-exchange-orders YES --order-type limit --maker-offset 0.001 --crash-drop-pct 0.08 --crash-breadth-ratio 0.6 --crash-short-trailing-pct 0.03
