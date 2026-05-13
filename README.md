# Quant Futures Bot

这是一个运行在 Binance Futures Testnet/Demo 上的量化交易项目。当前最新使用方式是：

- `quant-websocket.service`：WebSocket 实时盯盘、同步测试盘账户、执行当前主策略。
- `quant-optimizer.timer`：每 4 小时优化 BTC/ETH/SOL 的主策略。
- `quant-altcoin-optimizer.timer`：每 1 小时滚动回测山寨币激进策略，输出排名和日志。
- `quant-altcoin-paper.timer`：每 15 分钟按最新山寨币排名跑 paper 模拟盘状态。

测试盘会真实向 Binance Futures Testnet/Demo 发订单，但不会动真实资金。

## 1. 安装依赖

```bash
pip install -r requirements.txt
```

## 2. 配置 Testnet API

Windows 临时设置：

```bat
set BINANCE_TESTNET_API_KEY=你的testnet_api_key
set BINANCE_TESTNET_API_SECRET=你的testnet_api_secret
```

Linux 服务器使用 `.env`：

```bash
EXECUTION_MODE=testnet
BINANCE_TESTNET_API_KEY=你的testnet_key
BINANCE_TESTNET_API_SECRET=你的testnet_secret
```

不要把真实 key 提交到 Git。

## 3. WebSocket 实时盯盘

本地运行：

```bat
run_testnet_websocket.bat
```

服务器长期运行：

```bash
sudo systemctl enable --now quant-websocket.service
journalctl -u quant-websocket.service -f
```

日志含义：

```text
websocket_tick
```

实时价格心跳，说明 WebSocket 行情正常。

```text
strategy_cycle
```

启动或 4H/6H 周期换线后执行了一轮主策略。

```text
signals / rejected / orders_created / fills_created
```

分别表示策略信号数、风控拒绝数、创建订单数、成交数。

## 4. 主策略优化

手动优化 BTC/ETH/SOL：

```bat
optimize_strategy.bat
```

服务器自动优化：

```bash
sudo systemctl enable --now quant-optimizer.timer
journalctl -u quant-optimizer.service -n 100
```

主策略优化结果写入：

```text
quant_futures_bot/data/selected_strategy.json
```

当前主策略只使用 `4h` 和 `6h` 周期。

## 5. 山寨币激进策略

山寨币激进策略用于扫描 Binance USDT 永续合约成交额前 100 的山寨币，测试：

- 短周期动量突破：`alt_momentum_12`
- 成交量放大突破：`alt_volume_breakout`
- 波动率扩张突破：`alt_volatility_breakout`

默认参数：

- 回测周期：`15m,30m`
- 每周期 K 线数量：`--limit 500`
- 止损：`2.5%`
- 止盈：`6%`
- 杠杆：`2x`
- 单币保证金占比：`3%`
- 自动更新频率：每 1 小时

手动运行一次：

```bash
python -m quant_futures_bot.altcoin_top_volume_backtest --top 100 --limit 500 --timeframes 15m,30m --show 30
```

Windows 每 1 小时滚动运行：

```bat
auto_altcoin_optimize_every_1h.bat
```

服务器每 1 小时自动运行：

```bash
sudo systemctl enable --now quant-altcoin-optimizer.timer
```

查看山寨币策略运行日志：

```bash
journalctl -u quant-altcoin-optimizer.service -n 100
tail -f quant_futures_bot/logs/altcoin_strategy.log
```

查看最新山寨币策略排名摘要：

```bash
cat quant_futures_bot/data/altcoin_strategy_latest.json
```

完整 CSV 结果：

```text
quant_futures_bot/data/altcoin_top100_rolling_backtest.csv
```

注意：目前山寨币激进策略默认只做滚动回测和排名输出，不会自动接管实盘/测试盘下单。主交易仍由 `quant-websocket.service` 的当前主策略执行。

## 6. 山寨币 paper 模拟盘运行情况

山寨币 paper 模拟盘会读取：

```text
quant_futures_bot/data/altcoin_strategy_latest.json
```

然后选排名前 5 的币，按对应策略、周期和风控参数做 paper 模拟开平仓。它不会向交易所下单，只用于观察山寨币策略实际滚动运行后的权益、持仓、信号和成交情况。

本地手动运行一次：

```bat
run_altcoin_paper_once.bat
```

服务器每 15 分钟自动运行：

```bash
sudo systemctl enable --now quant-altcoin-paper.timer
```

查看运行日志：

```bash
journalctl -u quant-altcoin-paper.service -n 100
tail -f quant_futures_bot/logs/altcoin_paper.log
```

查看最新 paper 状态：

```bash
cat quant_futures_bot/data/altcoin_paper_latest.json
```

查看 paper 持仓状态文件：

```bash
cat quant_futures_bot/data/altcoin_paper_state.json
```

## 7. 数据文件

常用文件：

```text
quant_futures_bot/data/state.json
quant_futures_bot/data/selected_strategy.json
quant_futures_bot/data/altcoin_strategy_latest.json
quant_futures_bot/data/altcoin_paper_latest.json
quant_futures_bot/data/altcoin_paper_state.json
quant_futures_bot/data/altcoin_top100_rolling_backtest.csv
quant_futures_bot/logs/error.log
quant_futures_bot/logs/altcoin_strategy.log
quant_futures_bot/logs/altcoin_paper.log
```

`state.json` 可以查看当前账户权益、持仓、系统状态、最大回撤、连续亏损次数。

## 8. 云服务器部署

完整 Ubuntu 部署说明：

```text
deploy/README_ubuntu.md
```

常用更新命令：

```bash
cd /opt/quant-futures-bot
git pull
/opt/miniconda/envs/quant-bot/bin/pip install -r requirements.txt

sudo cp deploy/quant-websocket.service /etc/systemd/system/quant-websocket.service
sudo cp deploy/quant-optimizer.service /etc/systemd/system/quant-optimizer.service
sudo cp deploy/quant-optimizer.timer /etc/systemd/system/quant-optimizer.timer
sudo cp deploy/quant-altcoin-optimizer.service /etc/systemd/system/quant-altcoin-optimizer.service
sudo cp deploy/quant-altcoin-optimizer.timer /etc/systemd/system/quant-altcoin-optimizer.timer
sudo cp deploy/quant-altcoin-paper.service /etc/systemd/system/quant-altcoin-paper.service
sudo cp deploy/quant-altcoin-paper.timer /etc/systemd/system/quant-altcoin-paper.timer
sudo systemctl daemon-reload
```

启动所有服务：

```bash
sudo systemctl enable --now quant-websocket.service
sudo systemctl enable --now quant-optimizer.timer
sudo systemctl enable --now quant-altcoin-optimizer.timer
sudo systemctl enable --now quant-altcoin-paper.timer
```

查看服务：

```bash
sudo systemctl status quant-websocket.service
sudo systemctl status quant-optimizer.timer
sudo systemctl status quant-altcoin-optimizer.timer
sudo systemctl status quant-altcoin-paper.timer
```

停止服务：

```bash
sudo systemctl stop quant-websocket.service
sudo systemctl stop quant-optimizer.timer
sudo systemctl stop quant-altcoin-optimizer.timer
sudo systemctl stop quant-altcoin-paper.timer
```

## 9. 安全提醒

`.env`、数据库、状态文件、CSV 结果和日志都不应提交到 Git。项目已在 `.gitignore` 中排除这些运行时文件。
