# Quant Futures Bot

这是一个 Binance USDT 合约量化交易项目，当前按三个板块运行：

| 板块 | 标的 | 用途 | 是否下单 |
| --- | --- | --- | --- |
| 主流币 | BTC / ETH / SOL | 稳定运行、低频策略、4H/6H 回测优化 | `quant-websocket.service` 会向 Testnet/Demo 下单 |
| 山寨币 | Binance USDT 合约成交量前 100 | 激进策略，15m/30m，按评分筛出所有达标组合 | `quant-altcoin-websocket.service` 会向 Testnet/Demo 限价挂单 |
| 宏观映射 | 黄金、白银、美股、指数等 Binance 上实际存在的映射合约 | 1h/4h 趋势/突破/均值回归策略 | `quant-macro-websocket.service` 会向 Testnet/Demo 限价挂单 |

> 宏观映射不是直接连接美股券商，而是在 Binance USDT 合约里自动寻找实际存在的映射合约，例如 PAXG、XAU、XAG、NVDA、TSLA、MSTR 等。如果交易所没有某个映射合约，系统会自动跳过。

## 安装

```bash
pip install -r requirements.txt
```

服务器 `.env`：

```bash
EXECUTION_MODE=testnet
BINANCE_TESTNET_API_KEY=你的_testnet_key
BINANCE_TESTNET_API_SECRET=你的_testnet_secret
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
python -m quant_futures_bot.altcoin_top_volume_backtest --top 100 --limit 1000 --timeframes 15m,30m --show 30 --min-trades 8 --min-side-ratio 0.20 --fold-count 4 --min-profitable-fold-ratio 1.0 --fee-rate 0.0002 --funding-cost-rate-per-8h 0.0001
```

山寨币滚动优化：

```bash
python -m quant_futures_bot.auto_altcoin_optimizer --run-once --top 100 --limit 1000 --timeframes 15m,30m --show 30 --min-score 1.0 --max-leaders 0
```

宏观映射回测优化：

```bash
python -m quant_futures_bot.macro_optimizer --run-once --top 50 --limit 1000 --timeframes 1h,4h --show 30 --min-score 1.0 --max-leaders 0
```

查看账户、持仓、浮盈浮亏、已实现盈亏：

```bash
python -m quant_futures_bot.account_watch
```

## 三板块架构

### 1. 主流币

- 标的：`BTC/USDT:USDT`、`ETH/USDT:USDT`、`SOL/USDT:USDT`
- 优化周期：每 4 小时
- 运行方式：WebSocket 实时盯盘，K 线收盘时运行策略
- 策略候选：趋势、突破、RSI、均值回归等
- 策略文件：`quant_futures_bot/data/selected_strategy.json`
- 状态文件：`quant_futures_bot/data/state.json`

### 2. 山寨币

- 标的：Binance USDT 合约 24h 成交量前 100，排除 BTC/ETH/稳定币/宏观映射类标的
- 时间周期：`15m`、`30m`
- 策略候选：短周期动量突破、成交量突破、波动率扩张突破
- 优化周期：每 1 小时
- 运行范围：所有 `score >= 1.0` 的组合，不再限制前 5
- 策略文件：`quant_futures_bot/data/altcoin_strategy_latest.json`
- Testnet 状态：`quant_futures_bot/data/altcoin_testnet_latest.json`
- 日志：`quant_futures_bot/logs/altcoin_strategy.log`、`quant_futures_bot/logs/altcoin_testnet.log`

山寨币筛选默认要求：

- 回测长度：`1000` 根 K 线
- 至少 `8` 笔平仓交易
- 多空不能严重偏科，较少方向交易占比不低于 `20%`
- 最近 `4` 段样本必须全部盈利
- 回测扣除 maker 手续费 `0.02%` 和保守资金费每 8 小时 `0.01%`
- 输出拆分 `L/S`、`Lpnl`、`Spnl`、`side`、`folds`

### 3. 宏观映射

- 标的：交易所实际支持的黄金、白银、美股、指数、商品映射合约
- 时间周期：`1h`、`4h`
- 策略候选：MA 趋势、20/40 突破、20 均值回归
- 优化周期：每 4 小时
- 运行范围：所有 `score >= 1.0` 的组合
- 策略文件：`quant_futures_bot/data/macro_strategy_latest.json`
- Testnet 状态：`quant_futures_bot/data/macro_testnet_latest.json`
- 日志：`quant_futures_bot/logs/macro_strategy.log`、`quant_futures_bot/logs/macro_testnet.log`

宏观映射筛选默认要求：

- 回测长度：`1000` 根 K 线
- 至少 `6` 笔平仓交易
- 较少方向交易占比不低于 `10%`
- 最近 `4` 段样本至少 `75%` 盈利
- 默认止损 `2%`、止盈 `5%`

## 交易规则

山寨币和宏观映射 Testnet 实盘模拟都只做限价挂单：

- 不使用市价单
- 默认 post-only
- 买单低于信号价约 `0.1%`
- 卖单高于信号价约 `0.1%`
- 开仓挂单超过 `180` 秒未成交会撤单
- 平仓挂单超过 `60` 秒未成交会撤单并重新评估
- 同一币种连续 `3` 次挂单失败会暂停该标的
- 每轮运行先同步交易所余额、持仓、未成交订单，再决定是否继续挂单

瀑布风险控制：

- 默认最近 4 根 K 线里，至少 `60%` 的交易标的跌超 `3%`，进入 crash watch
- crash watch 下，空单不再按固定止盈过早平仓，而是启用追踪止盈
- 空单继续盈利时继续持有，从最大浮盈回撤超过 `3%` 才挂单平空
- 止损仍然保留

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

查看关键服务：

```bash
systemctl status quant-websocket.service
systemctl status quant-altcoin-websocket.service
systemctl status quant-macro-websocket.service
systemctl status quant-altcoin-optimizer.timer
systemctl status quant-macro-optimizer.timer
```

停止全部交易相关服务：

```bash
sudo systemctl stop quant-websocket.service quant-optimizer.timer quant-optimizer.service
sudo systemctl stop quant-altcoin-optimizer.timer quant-altcoin-optimizer.service quant-altcoin-websocket.service
sudo systemctl stop quant-macro-optimizer.timer quant-macro-optimizer.service quant-macro-websocket.service
```
