# Quant Futures Bot

Binance Futures Testnet/Demo 量化交易项目。

当前运行线：

- `quant-websocket.service`：主策略 WebSocket 盯盘和 Testnet 下单。
- `quant-optimizer.timer`：每 4 小时优化 BTC/ETH/SOL 主策略。
- `quant-altcoin-optimizer.timer`：每 1 小时滚动回测山寨币激进策略。
- `quant-altcoin-testnet.timer`：每 15 分钟按最新山寨币排名提交 Testnet 限价挂单。

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

## 主策略

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

## 山寨币策略排名

手动回测：

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

## 山寨币 Testnet 限价挂单

山寨币 Testnet 服务读取：

```text
quant_futures_bot/data/altcoin_strategy_latest.json
```

然后选择排名前 5 的币，按对应策略向 Binance Futures Testnet/Demo 提交订单。

重要规则：

- 只做限价挂单，不用市价单。
- 使用 post-only 参数，避免直接吃单。
- 买单价格约低于信号价 `0.1%`。
- 卖单价格约高于信号价 `0.1%`。
- 挂单提交后不会立刻记为本地成交。
- 是否成交以交易所测试盘实际订单/持仓为准。

本地手动运行一次：

```bat
run_altcoin_testnet_once.bat
```

服务器每 15 分钟运行：

```bash
sudo systemctl enable --now quant-altcoin-testnet.timer
```

查看挂单日志：

```bash
journalctl -u quant-altcoin-testnet.service -n 100
tail -f quant_futures_bot/logs/altcoin_testnet.log
```

看到类似下面内容，表示已经提交限价挂单：

```text
testnet_order symbol=SUI/USDT:USDT action=OPEN_LONG type=limit ... exchange_order_id=123456789 status=submitted post_only=YES
```

最新状态：

```bash
cat quant_futures_bot/data/altcoin_testnet_latest.json
cat quant_futures_bot/data/altcoin_testnet_state.json
```

## 山寨币 Paper 模拟

如果只想模拟，不向交易所提交挂单：

```bat
run_altcoin_paper_once.bat
```

服务器：

```bash
sudo systemctl enable --now quant-altcoin-paper.timer
journalctl -u quant-altcoin-paper.service -n 100
tail -f quant_futures_bot/logs/altcoin_paper.log
```

## 服务器更新部署

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

启动山寨币 Testnet 限价挂单：

```bash
sudo systemctl enable --now quant-altcoin-testnet.timer
```

停止山寨币 Testnet 限价挂单：

```bash
sudo systemctl stop quant-altcoin-testnet.timer
```
