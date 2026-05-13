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
"%PYTHON_EXE%" -m quant_futures_bot.main --cycles 1
