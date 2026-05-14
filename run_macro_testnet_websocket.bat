@echo off
setlocal
cd /d "%~dp0"
python -m quant_futures_bot.macro_websocket_monitor --top 0 --candle-limit 300 --print-seconds 5 --maintenance-seconds 30 --leader-refresh-seconds 60

