# Quant Futures Bot

Binance Futures Demo/Testnet 量化交易项目。

当前主要运行线：

- `quant-websocket.service`：BTC/ETH/SOL 主策略 WebSocket 盯盘与 Testnet 下单。
- `quant-optimizer.timer`：每 4 小时优化 BTC/ETH/SOL 主策略。
- `quant-altcoin-optimizer.timer`：每 1 小时滚动回测山寨币激进策略。
- `quant-altcoin-testnet.timer`：每 15 分钟按最新山寨币排名向 Testnet 提交限价挂单。

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

手动回测 Binance USDT 合约交易量前 100：

```bash
python -m quant_futures_bot.altcoin_top_volume_backtest --top 100 --limit 500 --timeframes 15m,30m --show 30
```

服务器每 1 小时滚动回测：

```bash
sudo systemctl enable --now quant-altcoin-optimizer.timer
journalctl -u quant-altcoin-optimizer.service -n 100
tail -f quant_futures_bot/logs/altcoin_strategy.log
```

最新排名文件：

```bash
cat quant_futures_bot/data/altcoin_strategy_latest.json
```

## 山寨币 Testnet 限价挂单

山寨币 Testnet 服务读取：

```text
quant_futures_bot/data/altcoin_strategy_latest.json
```

然后选择排名前 5 的币，按对应策略向 Binance Futures Demo/Testnet 提交订单。

重要规则：

- 只做限价挂单，不使用市价单。
- 使用 post-only 参数，避免直接吃单。
- 买单价格约低于信号价 `0.1%`。
- 卖单价格约高于信号价 `0.1%`。
- 挂单提交后不会立刻记为本地成交。
- 是否成交以交易所测试盘实际订单和持仓为准。

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

## 瀑布行情风控

山寨币模块现在有 crash mode：

- 默认判断：本轮交易币种里，至少 `60%` 的币最近 4 根 K 线跌幅达到 `8%`，进入瀑布模式。
- 普通模式：空单达到 `6%` 浮盈会固定止盈。
- 瀑布模式：空单不再按 `6%` 固定止盈，而是启用 `3%` 追踪止盈。
- 也就是说，空单继续盈利时会继续持有；从最大浮盈回撤超过 `3%` 时，才挂单平空。
- 止损仍然保留，默认亏损 `2.5%` 会触发平仓信号。

相关参数：

```bash
--crash-drop-pct 0.08
--crash-breadth-ratio 0.6
--crash-short-trailing-pct 0.03
```

日志出现下面内容，表示进入瀑布模式：

```text
crash_mode=ON symbols=5 avg_recent_drop=-10.25% trigger_drop=8.00% short_trailing=3.00%
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
