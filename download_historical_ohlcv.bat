@echo off
setlocal
cd /d "%~dp0"
python -m quant_futures_bot.historical_data --start 2022-01-01 --end 2026-01-01 --timeframes 15m,30m,1h,4h,6h --include-main --include-altcoin-latest --include-macro-latest

