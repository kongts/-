# Quant Futures Bot

这是一个用于 Binance USDT 合约测试盘的量化交易项目。当前主运行方式是：

- WebSocket 实时盯盘价格
- 4H/6H 周期换线时执行策略判断
- Testnet/Demo 账户下单，不动真实资金
- 每个币种可以使用优化器筛选出的独立策略和周期

## 安装

```bat
pip install -r requirements.txt
```

## 回测和策略优化

在线拉取 Binance Futures 历史 K 线回测：

```bat
run_backtest.bat
```

按币种筛选最优策略：

```bat
optimize_strategy.bat
```

优化器会测试 BTC、ETH、SOL 的候选策略，并把结果写入：

```text
quant_futures_bot/data/selected_strategy.json
```

当前只使用 `4h` 和 `6h` 周期。

## 山寨币前 100 激进策略回测

抓取 Binance USDT 永续合约 24h 成交额排名前 100 的山寨币，并测试激进策略：

```bat
run_altcoin_top100_backtest.bat
```

默认设置：

- 排除 BTC、ETH、稳定币、黄金、白银、天然气和股票映射类合约
- 周期：`15m`、`30m`
- 策略：短周期动量突破、成交量放大突破、波动率扩张突破
- 止损：`2.5%`
- 止盈：`6%`
- 单币保证金占比：`3%`
- 杠杆：`2x`

输出文件：

```text
quant_futures_bot/data/altcoin_top100_backtest.csv
```

也可以直接运行模块调整参数：

```bash
python -m quant_futures_bot.altcoin_top_volume_backtest --top 100 --limit 500 --timeframes 15m,30m --show 30
```

## 单次运行

本地 paper 模式单次运行：

```bat
run_live_once.bat
```

Binance Futures Testnet 单次运行：

```bat
run_testnet_once.bat
```

Testnet 运行前需要设置环境变量：

```bat
set BINANCE_TESTNET_API_KEY=你的testnet_api_key
set BINANCE_TESTNET_API_SECRET=你的testnet_api_secret
```

## WebSocket 实时盯盘

持续盯盘只保留 WebSocket 版本：

```bat
run_testnet_websocket.bat
```

它会连接 Binance Futures WebSocket：

- `bookTicker`：实时接收买一卖一价格，默认每 5 秒打印一次价格心跳
- `strategy_timer`：根据当前策略周期判断 4H/6H 是否换线
- 启动时执行一轮策略，用来同步账户权益、持仓、挂单
- 4H/6H 换线时执行一轮策略判断和下单

常见日志：

```text
websocket_tick prices=BTC/USDT:USDT=81078.5500,ETH/USDT:USDT=2314.1850,SOL/USDT:USDT=95.3350 equity=10000.00 status=RUNNING exchange_positions=-
timeframe_closed interval=4h
strategy_cycle reason="4h close"
cycle=2 equity=9998.20 used_margin=600.30 status=RUNNING execution_mode=testnet signals=0 rejected=0 orders_created=0 fills_created=0
```

字段含义：

- `websocket_tick`：实时价格心跳
- `timeframe_closed`：4H/6H 周期换线
- `strategy_cycle`：执行了一轮策略
- `signals`：本轮产生的策略信号数
- `rejected`：本轮被风控拒绝或无可用数量的信号数
- `orders_created`：本轮生成订单数
- `fills_created`：本轮成交数
- `exchange_positions`：从 Binance Testnet 同步到的真实测试盘持仓摘要

## 数据文件

运行后会生成：

```text
quant_futures_bot/data/quant_bot.db
quant_futures_bot/data/state.json
quant_futures_bot/data/selected_strategy.json
quant_futures_bot/logs/error.log
```

`state.json` 可以直接打开查看当前账户状态、持仓、系统状态、最大回撤、连续亏损次数等。

## 云服务器部署

Ubuntu 部署说明见：

```text
deploy/README_ubuntu.md
```

长期运行推荐：

- `quant-websocket.service`：WebSocket 实时盯盘和策略执行
- `quant-optimizer.timer`：每 4 小时自动回测优化策略

## 安全提醒

不要把真实 API key 提交到 Git。`.env`、数据库、状态文件和日志都不应该提交。
