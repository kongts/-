# Ubuntu 云服务器部署

默认目录：

```bash
/opt/quant-futures-bot
```

## 更新项目

```bash
cd /opt/quant-futures-bot
git pull
/opt/miniconda/envs/quant-bot/bin/pip install -r requirements.txt
```

## 配置 `.env`

```bash
cp deploy/env.example .env
nano .env
```

填写：

```bash
EXECUTION_MODE=testnet
BINANCE_TESTNET_API_KEY=你的testnet_key
BINANCE_TESTNET_API_SECRET=你的testnet_secret
```

## 安装 systemd

```bash
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

## 启动服务

主策略 Testnet：

```bash
sudo systemctl enable --now quant-websocket.service
```

BTC/ETH/SOL 主策略优化：

```bash
sudo systemctl enable --now quant-optimizer.timer
```

山寨币每 1 小时滚动回测：

```bash
sudo systemctl enable --now quant-altcoin-optimizer.timer
```

山寨币 Testnet 交易所下单：

```bash
sudo systemctl enable --now quant-altcoin-testnet.timer
```

山寨币 paper 模拟：

```bash
sudo systemctl enable --now quant-altcoin-paper.timer
```

## 查看日志

```bash
journalctl -u quant-websocket.service -f
journalctl -u quant-optimizer.service -n 100
journalctl -u quant-altcoin-optimizer.service -n 100
journalctl -u quant-altcoin-testnet.service -n 100
journalctl -u quant-altcoin-paper.service -n 100
```

山寨币策略文件：

```bash
tail -f /opt/quant-futures-bot/quant_futures_bot/logs/altcoin_strategy.log
tail -f /opt/quant-futures-bot/quant_futures_bot/logs/altcoin_testnet.log
cat /opt/quant-futures-bot/quant_futures_bot/data/altcoin_strategy_latest.json
cat /opt/quant-futures-bot/quant_futures_bot/data/altcoin_testnet_latest.json
```

## 查看 timer

```bash
systemctl list-timers | grep quant
```

## 停止服务

停止山寨币 Testnet 下单：

```bash
sudo systemctl stop quant-altcoin-testnet.timer
```

停止全部：

```bash
sudo systemctl stop quant-websocket.service
sudo systemctl stop quant-optimizer.timer
sudo systemctl stop quant-altcoin-optimizer.timer
sudo systemctl stop quant-altcoin-testnet.timer
sudo systemctl stop quant-altcoin-paper.timer
```
