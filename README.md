# Quant Futures Bot

这是一个 Binance USDT-M Futures 量化交易项目，当前按三个板块运行：

| 板块 | 标的 | 用途 | 是否下单 |
| --- | --- | --- | --- |
| 主流币 | BTC / ETH / SOL | 低频策略，按 4h/6h 回测优化 | `quant-websocket.service` 可向 Testnet/Demo 下单 |
| 山寨币 | Binance USDT 合约成交量前 100 | 激进短周期策略，15m/30m，按评分筛选 leaders | `quant-altcoin-websocket.service` 向 Testnet/Demo 限价挂单 |
| 宏观映射 | 黄金、白银、美股、指数等 Binance 上实际存在的映射合约 | 1h/4h 趋势、突破、均值回归策略 | `quant-macro-websocket.service` 向 Testnet/Demo 限价挂单 |

> 宏观映射不是直接连接美股券商，而是在 Binance USDT 合约里自动寻找实际存在的映射合约；交易所不存在的标的会自动跳过。

## 当前关键行为

- 默认使用正向执行：回测/优化按原始策略筛选，实盘执行也按原始策略方向开平仓。
- 山寨币和宏观 WebSocket 默认每 60 秒执行一次实时信号检查，同时保留 15m/30m 或 1h/4h 收线检查。
- 山寨币和宏观 Testnet 默认只用 post-only 限价单，不使用市价开仓。
- 如果同一标的连续 3 次挂单超时，会暂停该标的，记录在 runtime state JSON 中。
- 全部平仓命令已内置：先撤未成交挂单，再用 `reduceOnly` 市价单平掉所有真实持仓。

如需临时启用反向执行，在 `.env` 中加入：

```bash
INVERT_EXECUTION_SIGNALS=1
```

## 安装

```bash
pip install -r requirements.txt
```

服务器 `.env` 示例：

```bash
EXECUTION_MODE=testnet
BINANCE_TESTNET_API_KEY=你的_testnet_key
BINANCE_TESTNET_API_SECRET=你的_testnet_secret
INVERT_EXECUTION_SIGNALS=0
```

## 本地常用命令

主流币回测：

```bash
python -m quant_futures_bot.backtest
```

主流币优化：

```bash
python -m quant_futures_bot.strategy_optimizer
```

山寨币成交量前 100 回测：

```bash
python -m quant_futures_bot.altcoin_top_volume_backtest --top 100 --limit 1000 --timeframes 15m,30m --show 30 --min-trades 4 --min-side-ratio 0 --fold-count 4 --min-profitable-fold-ratio 0.25 --fee-rate 0.0002 --funding-cost-rate-per-8h 0.0001
```

山寨币滚动优化：

```bash
python -m quant_futures_bot.auto_altcoin_optimizer --run-once --top 100 --limit 1000 --timeframes 15m,30m --show 30 --min-score 0 --max-leaders 30
```

山寨币 2h K 线回测：

```bash
python -m quant_futures_bot.auto_altcoin_optimizer --run-once --top 100 --limit 800 --timeframes 2h --strategy-workers 4 --max-hold-bars-2h 12 --extended-hold-bars-2h 6 --show 30
```

宏观映射回测优化：

```bash
python -m quant_futures_bot.macro_optimizer --run-once --top 50 --limit 1000 --timeframes 1h,4h --show 30 --min-score 1.0 --max-leaders 0
```

宏观 2h K 线回测：

```bash
python -m quant_futures_bot.macro_optimizer --run-once --top 50 --limit 800 --timeframes 2h --strategy-workers 4 --max-hold-bars-2h 12 --extended-hold-bars-2h 6 --show 30
```

查看账户、持仓、挂单和已实现盈亏：

```bash
python -m quant_futures_bot.account_watch
```

全部平仓，真实执行前建议先 dry-run：

```bash
python -m quant_futures_bot.close_all_positions
python -m quant_futures_bot.close_all_positions --confirm YES
```

下载历史 K 线：

```bash
python -m quant_futures_bot.historical_data --start 2022-01-01 --end 2026-01-01 --timeframes 15m,30m,1h,4h,6h --include-main --include-altcoin-latest --include-macro-latest
```

下载成交量前 100 山寨币的 `30m/2h` K 线并用本地缓存回测：

```bash
python -m quant_futures_bot.historical_data --no-include-main --include-altcoin-top-volume --top 100 --start 2025-01-01 --end 2026-05-19 --timeframes 30m,2h
python -m quant_futures_bot.auto_altcoin_optimizer --run-once --top 100 --limit 800 --timeframes 30m,2h --strategy-workers 4 --data-root quant_futures_bot/data/historical_ohlcv/binance_usdt_futures
```

下载成交量前 100 山寨币自 2022 年以来的 `2h` K 线，并按 `2022-01-01` 到当前时间回测：

```bash
python -m quant_futures_bot.historical_data --no-include-main --include-altcoin-top-volume --top 100 --start 2022-01-01 --end now --timeframes 2h
python -m quant_futures_bot.auto_altcoin_optimizer --run-once --top 100 --limit 30000 --timeframes 2h --strategy-workers 4 --data-root quant_futures_bot/data/historical_ohlcv/binance_usdt_futures --data-start 2022-01-01 --data-end now --min-trades 8 --fold-count 8 --min-profitable-fold-ratio 0.50
```

Windows 可直接运行对应 `.bat`：

```bat
run_offline_once.bat
run_backtest.bat
run_altcoin_top100_backtest.bat
run_close_all_positions.bat
```

## 三个板块

### 1. 主流币

- 标的：`BTC/USDT:USDT`、`ETH/USDT:USDT`、`SOL/USDT:USDT`
- 优化周期：每 4 小时
- 运行方式：WebSocket 实时监控，K 线收线时执行策略
- 策略候选：MA 趋势、RSI、突破、均值回归等
- 策略文件：`quant_futures_bot/data/selected_strategy.json`
- 状态文件：`quant_futures_bot/data/state.json`

### 2. 山寨币

- 标的：Binance USDT 合约成交量前 100，排除部分主流币、稳定币和宏观映射类标的
- 时间周期：默认 `15m`、`30m`；手动回测可用 `2h`
- 策略候选：短周期动量突破、成交量突破、波动率扩张突破、10/20/40 突破、MA 回撤、RSI 动量、均值回归
- 优化周期：每 1 周，先增量下载本地 `2h` K 线缓存，再从 2022-01-01 回测筛选
- 实时执行：默认每 60 秒执行一次 live signal check，同时保留 15m/30m 收线检查
- 运行范围：最多 30 个 `score >= 0` 的组合
- 策略文件：`quant_futures_bot/data/altcoin_strategy_latest.json`
- Testnet 状态：`quant_futures_bot/data/altcoin_testnet_latest.json`
- Runtime 状态：`quant_futures_bot/data/altcoin_testnet_runtime_state.json`
- 日志：`quant_futures_bot/logs/altcoin_strategy.log`、`quant_futures_bot/logs/altcoin_testnet.log`

默认筛选要求：

- 回测长度：`1000` 根 K 线
- 至少 `4` 笔平仓交易
- 允许单边策略：`min_side_ratio=0`
- 最近 `4` 段样本至少 `25%` 盈利
- 扣除 maker 手续费 `0.02%` 和保守资金费每 8 小时 `0.01%`
- 可用 `--strategy-workers 4` 并行回测策略，加快扩展候选后的优化速度。

### 3. 宏观映射

- 标的：交易所实际支持的黄金、白银、美股、指数、商品映射合约
- 时间周期：默认 `1h`、`4h`；手动回测可用 `2h`
- 策略候选：MA 趋势、RSI、20/40/80 突破、MA 回撤、RSI 动量、10/20/30 均值回归
- 优化周期：每 4 小时
- 实时执行：默认每 60 秒执行一次 live signal check，同时保留 1h/4h 收线检查
- 运行范围：所有 `score >= 1.0` 的组合
- 策略文件：`quant_futures_bot/data/macro_strategy_latest.json`
- Testnet 状态：`quant_futures_bot/data/macro_testnet_latest.json`
- Runtime 状态：`quant_futures_bot/data/macro_testnet_runtime_state.json`
- 日志：`quant_futures_bot/logs/macro_strategy.log`、`quant_futures_bot/logs/macro_testnet.log`

默认筛选要求：

- 回测长度：`1000` 根 K 线
- 至少 `6` 笔平仓交易
- 较少方向交易占比不低于 `10%`
- 最近 `4` 段样本至少 `75%` 盈利
- 默认止损 `2%`，止盈 `5%`
- 可用 `--strategy-workers 4` 并行回测策略，加快扩展候选后的优化速度。

## 交易规则

山寨币和宏观 Testnet 交易默认只做限价挂单：

- 不使用市价开仓
- 默认 post-only
- 买单低于信号价约 `0.1%`
- 卖单高于信号价约 `0.1%`
- 开仓挂单超过 `180` 秒未成交会撤单
- 平仓挂单超过 `60` 秒未成交会撤单并重新评估
- 同一标的连续 `3` 次挂单失败会暂停
- 每轮运行先同步交易所余额、持仓、未成交订单，再决定是否继续挂单

瀑布风险控制：

- 默认最近 4 根 K 线里，至少 `60%` 的交易标的跌超 `3%` 时进入 crash watch
- crash watch 下，空单不再按固定止盈过早平仓，而是启用追踪止盈
- 空单持续盈利时继续持有，从最大浮盈回撤超过 `3%` 才挂单平空
- 止损仍然保留

## 常用状态检查

查看是否启用反向执行，输出 `False` 表示当前是正向策略：

```bash
python -c "from quant_futures_bot import config; print(config.INVERT_EXECUTION_SIGNALS)"
```

查看山寨币运行状态：

```bash
cat quant_futures_bot/data/altcoin_testnet_latest.json
cat quant_futures_bot/data/altcoin_testnet_runtime_state.json
```

查看宏观运行状态：

```bash
cat quant_futures_bot/data/macro_testnet_latest.json
cat quant_futures_bot/data/macro_testnet_runtime_state.json
```

关键日志关键词：

```bash
strategy_cycle
live signal check
testnet_order
signal_rejected
pending_order
symbol_paused
summary
error
```

## 本地历史数据

历史 K 线存放在：

```bash
quant_futures_bot/data/historical_ohlcv/binance_usdt_futures/
```

optimizer 加上 `--data-root quant_futures_bot/data/historical_ohlcv/binance_usdt_futures` 后，会优先读取本地 `csv.gz` K 线；如果某个 symbol/timeframe 没有缓存，才回退到交易所拉取。

目录结构：

```text
historical_ohlcv/
  binance_usdt_futures/
    manifest.json
    15m/BTC_USDT_USDT.csv.gz
    30m/BTC_USDT_USDT.csv.gz
    1h/BTC_USDT_USDT.csv.gz
    4h/BTC_USDT_USDT.csv.gz
    6h/BTC_USDT_USDT.csv.gz
```

## 服务器服务

完整 Ubuntu 部署和服务命令见：

```bash
deploy/README_ubuntu.md
```

推荐运行组合：

```bash
sudo systemctl enable --now quant-websocket.service
sudo systemctl enable --now quant-optimizer.timer
sudo systemctl enable --now quant-altcoin-optimizer.timer
sudo systemctl enable --now quant-altcoin-websocket.service
sudo systemctl enable --now quant-macro-optimizer.timer
sudo systemctl enable --now quant-macro-websocket.service
```
