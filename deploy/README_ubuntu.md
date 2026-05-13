# Ubuntu 部署说明

项目目录默认：

```bash
/opt/quant-futures-bot
```

Python 环境默认：

```bash
/opt/miniconda/envs/quant-bot/bin/python
```

## 更新项目

```bash
cd /opt/quant-futures-bot
git pull
/opt/miniconda/envs/quant-bot/bin/pip install -r requirements.txt
```

## 环境变量

编辑 `/opt/quant-futures-bot/.env`：

```bash
EXECUTION_MODE=testnet
BINANCE_TESTNET_API_KEY=你的_testnet_key
BINANCE_TESTNET_API_SECRET=你的_testnet_secret
```

## 安装 systemd 服务

```bash
cd /opt/quant-futures-bot

sudo cp deploy/quant-websocket.service /etc/systemd/system/quant-websocket.service
sudo cp deploy/quant-optimizer.service /etc/systemd/system/quant-optimizer.service
sudo cp deploy/quant-optimizer.timer /etc/systemd/system/quant-optimizer.timer
sudo cp deploy/quant-altcoin-optimizer.service /etc/systemd/system/quant-altcoin-optimizer.service
sudo cp deploy/quant-altcoin-optimizer.timer /etc/systemd/system/quant-altcoin-optimizer.timer
sudo cp deploy/quant-altcoin-testnet.service /etc/systemd/system/quant-altcoin-testnet.service
sudo cp deploy/quant-altcoin-testnet.timer /etc/systemd/system/quant-altcoin-testnet.timer

sudo systemctl daemon-reload
```

## 主策略

启动 WebSocket 主策略：

```bash
sudo systemctl enable --now quant-websocket.service
journalctl -u quant-websocket.service -f
```

启动每 4 小时主策略优化：

```bash
sudo systemctl enable --now quant-optimizer.timer
systemctl status quant-optimizer.timer
```

## 山寨币策略

启动每 1 小时山寨币滚动回测：

```bash
sudo systemctl enable --now quant-altcoin-optimizer.timer
systemctl status quant-altcoin-optimizer.timer
```

查看山寨币策略日志：

```bash
journalctl -u quant-altcoin-optimizer.service -n 100
tail -f /opt/quant-futures-bot/quant_futures_bot/logs/altcoin_strategy.log
```

## 山寨币 Testnet 限价挂单

山寨币 Testnet 只做限价挂单：

- `--order-type limit`
- `--maker-offset 0.001`
- post-only 提交，避免直接吃单
- 买单低于信号价约 `0.1%`
- 卖单高于信号价约 `0.1%`

启动每 15 分钟运行一次：

```bash
sudo systemctl enable --now quant-altcoin-testnet.timer
```

手动运行一次：

```bash
/opt/miniconda/envs/quant-bot/bin/python -m quant_futures_bot.altcoin_paper_monitor --run-once --top 5 --candle-limit 220 --execution-mode testnet --confirm-exchange-orders YES --order-type limit --maker-offset 0.001
```

查看挂单日志：

```bash
journalctl -u quant-altcoin-testnet.service -n 100
tail -f /opt/quant-futures-bot/quant_futures_bot/logs/altcoin_testnet.log
```

如果看到：

```text
testnet_order ... type=limit ... status=submitted post_only=YES
```

表示已经向交易所测试盘提交限价挂单。

## 瀑布模式

山寨币模块默认使用：

```bash
--crash-drop-pct 0.08
--crash-breadth-ratio 0.6
--crash-short-trailing-pct 0.03
```

含义：

- 至少 `60%` 的交易币种最近 4 根 K 线跌超 `8%`，进入 crash mode。
- crash mode 下，空单不按固定 `6%` 止盈。
- 空单继续下跌就继续持有。
- 从最大浮盈回撤 `3%` 时，才挂单平空。
- 止损仍然保留。

## 常用排查

查看服务：

```bash
systemctl status quant-websocket.service
systemctl status quant-altcoin-optimizer.timer
systemctl status quant-altcoin-testnet.timer
```

查看 CPU：

```bash
top
ps aux --sort=-%cpu | head -20
```

停止山寨币挂单：

```bash
sudo systemctl stop quant-altcoin-testnet.timer
```
