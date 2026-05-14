@echo off
setlocal
cd /d "%~dp0"
python -m quant_futures_bot.macro_optimizer --run-once --top 50 --limit 1000 --timeframes 1h,4h --show 30 --min-score 1.0 --max-leaders 0

