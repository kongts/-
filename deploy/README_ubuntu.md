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
sudo cp deploy/quant-altcoin-paper.service /etc/systemd/system/quant-altcoin-paper.service
sudo cp deploy/quant-altcoin-paper.timer /etc/systemd/system/quant-altcoin-paper.timer
sudo cp deploy/quant-altcoin-testnet.service /etc/systemd/system/quant-altcoin-testnet.service
sudo cp deploy/quant-altcoin-testnet.timer /etc/systemd/system/quant-altcoin-testnet.timer

sudo systemctl daemon-reload
```

## 全部服务命令

### 主策略 WebSocket

用途：实时盯 BTC/ETH/SOL，读取 Testnet 账户，按主策略下单。

启动：

```bash
sudo systemctl enable --now quant-websocket.service
```

查看状态：

```bash
systemctl status quant-websocket.service
```

查看日志：

```bash
journalctl -u quant-websocket.service -f
```

停止：

```bash
sudo systemctl stop quant-websocket.service
```

禁用开机自启：

```bash
sudo systemctl disable quant-websocket.service
```

### 主策略优化

用途：每 4 小时优化 BTC/ETH/SOL 主策略。

启动：

```bash
sudo systemctl enable --now quant-optimizer.timer
```

查看状态：

```bash
systemctl status quant-optimizer.timer
systemctl status quant-optimizer.service
```

查看日志：

```bash
journalctl -u quant-optimizer.service -n 100
```

手动运行一次：

```bash
sudo systemctl start quant-optimizer.service
```

停止：

```bash
sudo systemctl stop quant-optimizer.timer
sudo systemctl stop quant-optimizer.service
```

禁用开机自启：

```bash
sudo systemctl disable quant-optimizer.timer
```

### 山寨币策略优化

用途：每 1 小时抓取 Binance USDT 合约交易量前 100，滚动回测山寨币激进策略。

启动：

```bash
sudo systemctl enable --now quant-altcoin-optimizer.timer
```

查看状态：

```bash
systemctl status quant-altcoin-optimizer.timer
systemctl status quant-altcoin-optimizer.service
```

查看日志：

```bash
journalctl -u quant-altcoin-optimizer.service -n 100
tail -f /opt/quant-futures-bot/quant_futures_bot/logs/altcoin_strategy.log
```

手动运行一次：

```bash
sudo systemctl start quant-altcoin-optimizer.service
```

停止：

```bash
sudo systemctl stop quant-altcoin-optimizer.timer
sudo systemctl stop quant-altcoin-optimizer.service
```

禁用开机自启：

```bash
sudo systemctl disable quant-altcoin-optimizer.timer
```

### 山寨币 Paper 模拟

用途：每 15 分钟按最新山寨币策略做本地模拟，不向交易所下单。

启动：

```bash
sudo systemctl enable --now quant-altcoin-paper.timer
```

查看状态：

```bash
systemctl status quant-altcoin-paper.timer
systemctl status quant-altcoin-paper.service
```

查看日志：

```bash
journalctl -u quant-altcoin-paper.service -n 100
tail -f /opt/quant-futures-bot/quant_futures_bot/logs/altcoin_paper.log
```

手动运行一次：

```bash
sudo systemctl start quant-altcoin-paper.service
```

停止：

```bash
sudo systemctl stop quant-altcoin-paper.timer
sudo systemctl stop quant-altcoin-paper.service
```

禁用开机自启：

```bash
sudo systemctl disable quant-altcoin-paper.timer
```

### 山寨币 Testnet 限价挂单

用途：每 15 分钟按最新山寨币策略向 Binance Futures Demo/Testnet 提交 post-only 限价挂单。

启动：

```bash
sudo systemctl enable --now quant-altcoin-testnet.timer
```

查看状态：

```bash
systemctl status quant-altcoin-testnet.timer
systemctl status quant-altcoin-testnet.service
```

查看日志：

```bash
journalctl -u quant-altcoin-testnet.service -n 100
tail -f /opt/quant-futures-bot/quant_futures_bot/logs/altcoin_testnet.log
```

手动运行一次：

```bash
sudo systemctl start quant-altcoin-testnet.service
```

停止：

```bash
sudo systemctl stop quant-altcoin-testnet.timer
sudo systemctl stop quant-altcoin-testnet.service
```

禁用开机自启：

```bash
sudo systemctl disable quant-altcoin-testnet.timer
```

## 一键查看所有服务状态

```bash
systemctl status quant-websocket.service
systemctl status quant-optimizer.timer
systemctl status quant-altcoin-optimizer.timer
systemctl status quant-altcoin-paper.timer
systemctl status quant-altcoin-testnet.timer
```

## 一键停止所有交易相关服务

```bash
sudo systemctl stop quant-websocket.service
sudo systemctl stop quant-optimizer.timer
sudo systemctl stop quant-optimizer.service
sudo systemctl stop quant-altcoin-optimizer.timer
sudo systemctl stop quant-altcoin-optimizer.service
sudo systemctl stop quant-altcoin-paper.timer
sudo systemctl stop quant-altcoin-paper.service
sudo systemctl stop quant-altcoin-testnet.timer
sudo systemctl stop quant-altcoin-testnet.service
```

## 推荐启动组合

主策略和山寨币 Testnet 挂单：

```bash
sudo systemctl enable --now quant-websocket.service
sudo systemctl enable --now quant-optimizer.timer
sudo systemctl enable --now quant-altcoin-optimizer.timer
sudo systemctl enable --now quant-altcoin-testnet.timer
```

只模拟山寨币，不向交易所下单：

```bash
sudo systemctl enable --now quant-altcoin-paper.timer
```

## 山寨币 Testnet 规则

山寨币 Testnet 只做限价挂单：

- `--order-type limit`
- `--maker-offset 0.001`
- post-only 提交，避免直接吃单。
- 买单低于信号价约 `0.1%`。
- 卖单高于信号价约 `0.1%`。
- 每轮先同步交易所余额、持仓、未成交挂单。
- 开仓挂单超过 `180` 秒未成交会撤单。
- 平仓挂单超过 `60` 秒未成交会撤单并重新评估。
- 同一币种连续 `3` 次挂单失败会暂停该币种。

手动运行完整命令：

```bash
/opt/miniconda/envs/quant-bot/bin/python -m quant_futures_bot.altcoin_paper_monitor --run-once --top 5 --candle-limit 220 --execution-mode testnet --confirm-exchange-orders YES --order-type limit --maker-offset 0.001 --crash-watch-drop-pct 0.03 --crash-watch-breadth-ratio 0.6 --crash-short-trailing-pct 0.03 --open-order-timeout-seconds 180 --close-order-timeout-seconds 60 --max-order-failures 3
```

看到下面内容，表示已经向交易所测试盘提交限价挂单：

```text
testnet_order ... type=limit ... status=submitted post_only=YES
```

## 瀑布预警

山寨币模块默认使用：

```bash
--crash-watch-drop-pct 0.03
--crash-watch-breadth-ratio 0.6
--crash-short-trailing-pct 0.03
```

含义：

- 至少 `60%` 的交易币种最近 4 根 K 线跌超 `3%`，进入 crash watch。
- crash watch 下，空单不按固定 `6%` 止盈。
- 空单继续下跌就继续持有。
- 从最大浮盈回撤 `3%` 时，才挂单平空。
- 止损仍然保留。

## 常用排查

查看 CPU：

```bash
top
ps aux --sort=-%cpu | head -20
```

查看最新山寨币策略：

```bash
cat /opt/quant-futures-bot/quant_futures_bot/data/altcoin_strategy_latest.json
```

查看山寨币 Testnet 最新状态：

```bash
cat /opt/quant-futures-bot/quant_futures_bot/data/altcoin_testnet_latest.json
cat /opt/quant-futures-bot/quant_futures_bot/data/altcoin_testnet_runtime_state.json
```
