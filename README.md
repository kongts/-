# Quant Futures Bot

Binance Futures Testnet/Demo 量化交易项目。当前分成四条运行线：

- `quant-websocket.service`：主策略 WebSocket 盯盘和 Testnet 下单。
- `quant-optimizer.timer`：每 4 小时优化 BTC/ETH/SOL 主策略。
- `quant-altcoin-optimizer.timer`：每 1 小时滚动回测山寨币激进策略。
- `quant-altcoin-testnet.timer`：每 15 分钟按最新山寨币排名向 Binance Futures Testnet/Demo 下单。

## 安装

```bash
pip install -r requirements.txt
```

服务器 `.env`：

```bash
EXECUTION_MODE=testnet
BINANCE_TESTNET_API_KEY=你的testnet_key
BINANCE_TESTNET_API_SECRET=你的testnet_secret
```

不要把真实 key 提交到 Git。

## 主策略运行

本地单次 Testnet：

```bat
run_testnet_once.bat
```

WebSocket 长期盯盘：

```bat
run_testnet_websocket.bat
```

服务器：

```bash
sudo systemctl enable --now quant-websocket.service
journalctl -u quant-websocket.service -f
```

## 主策略优化

```bat
optimize_strategy.bat
```

服务器每 4 小时自动运行：

```bash
sudo systemctl enable --now quant-optimizer.timer
journalctl -u quant-optimizer.service -n 100
```

输出：

```text
quant_futures_bot/data/selected_strategy.json
```

## 山寨币激进策略回测

扫描 Binance USDT 永续成交额前 100 山寨币，测试：

- `alt_momentum_12`
- `alt_volume_breakout`
- `alt_volatility_breakout`

默认参数：

- 周期：`15m,30m`
- K 线：`--limit 500`
- 止损：`2.5%`
- 止盈：`6%`
- 杠杆：`2x`
- 单币保证金占比：`3%`

手动运行：

```bash
python -m quant_futures_bot.altcoin_top_volume_backtest --top 100 --limit 500 --timeframes 15m,30m --show 30
```

服务器每 1 小时滚动回测：

```bash
sudo systemctl enable --now quant-altcoin-optimizer.timer
journalctl -u quant-altcoin-optimizer.service -n 100
tail -f quant_futures_bot/logs/altcoin_strategy.log
```

最新排名：

```bash
cat quant_futures_bot/data/altcoin_strategy_latest.json
```

## 山寨币 Testnet 下单

山寨币 Testnet 服务会读取：

```text
quant_futures_bot/data/altcoin_strategy_latest.json
```

然后选择排名前 5 的币，按对应策略和周期向 Binance Futures Testnet/Demo 发真实测试盘订单。它不会连接真实主网。

本地手动运行一次：

```bat
run_altcoin_testnet_once.bat
```

服务器每 15 分钟运行：

```bash
sudo systemctl enable --now quant-altcoin-testnet.timer
```

查看下单日志：

```bash
journalctl -u quant-altcoin-testnet.service -n 100
tail -f quant_futures_bot/logs/altcoin_testnet.log
```

看到类似下面内容，表示已经向交易所测试盘发单：

```text
testnet_fill symbol=SUI/USDT:USDT action=OPEN_LONG ... exchange_order_id=123456789
```

查看最新 Testnet 山寨币状态：

```bash
cat quant_futures_bot/data/altcoin_testnet_latest.json
cat quant_futures_bot/data/altcoin_testnet_state.json
```

## 山寨币 Paper 模拟

如果只想本地模拟、不向交易所发单：

```bat
run_altcoin_paper_once.bat
```

服务器：

```bash
sudo systemctl enable --now quant-altcoin-paper.timer
journalctl -u quant-altcoin-paper.service -n 100
tail -f quant_futures_bot/logs/altcoin_paper.log
```

## 常用数据文件

```text
quant_futures_bot/data/state.json
quant_futures_bot/data/selected_strategy.json
quant_futures_bot/data/altcoin_strategy_latest.json
quant_futures_bot/data/altcoin_testnet_latest.json
quant_futures_bot/data/altcoin_testnet_state.json
quant_futures_bot/data/altcoin_paper_latest.json
quant_futures_bot/data/altcoin_paper_state.json
quant_futures_bot/logs/altcoin_strategy.log
quant_futures_bot/logs/altcoin_testnet.log
quant_futures_bot/logs/altcoin_paper.log
```

## 服务器部署更新

```bash
cd /opt/quant-futures-bot
git pull
/opt/miniconda/envs/quant-bot/bin/pip install -r requirements.txt

sudo cp deploy/quant-websocket.service /etc/systemd/system/quant-websocket.service
sudo cp deploy/quant-optimizer.service /etc/systemd/system/quant-optimizer.service
sudo cp deploy/quant-optimizer.timer /etc/systemd/system/quant-optimizer.timer
sudo cp deploy/quant-altcoin-optimizer.service /etc/systemd/system/quant-altcoin-optimizer.service
sudo cp deploy/quant-altcoin-optimizer.timer /etc/systemd/system/quant-altcoin-optimizer.timer
sudo cp deploy/quant-altcoin-testnet.service /etc/systemd/system/quant-altcoin-testnet.service
sudo cp deploy/quant-altcoin-testnet.timer /etc/systemd/system/quant-altcoin-testnet.timer
sudo systemctl daemon-reload
```

启动：

```bash
sudo systemctl enable --now quant-websocket.service
sudo systemctl enable --now quant-optimizer.timer
sudo systemctl enable --now quant-altcoin-optimizer.timer
sudo systemctl enable --now quant-altcoin-testnet.timer
```

停止山寨币 Testnet 下单：

```bash
sudo systemctl stop quant-altcoin-testnet.timer
```
