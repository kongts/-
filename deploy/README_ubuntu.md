# Ubuntu 云服务器部署

默认部署目录：

```bash
/opt/quant-futures-bot
```

## 1. 更新项目

```bash
cd /opt/quant-futures-bot
git pull
/opt/miniconda/envs/quant-bot/bin/pip install -r requirements.txt
```

## 2. 配置 `.env`

```bash
cd /opt/quant-futures-bot
cp deploy/env.example .env
nano .env
```

填写：

```bash
EXECUTION_MODE=testnet
BINANCE_TESTNET_API_KEY=你的testnet_key
BINANCE_TESTNET_API_SECRET=你的testnet_secret
```

## 3. 测试网络

Binance：

```bash
curl https://testnet.binancefuture.com/fapi/v1/time
curl https://fapi.binance.com/fapi/v1/time
```

OKX：

```bash
curl -s https://www.okx.com/api/v5/public/time
curl -s "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT-SWAP"
```

## 4. 手动测试

```bash
cd /opt/quant-futures-bot
source /opt/miniconda/etc/profile.d/conda.sh
conda activate quant-bot
set -a; source .env; set +a

python -m quant_futures_bot.strategy_optimizer
python -m quant_futures_bot.websocket_monitor --print-seconds 5
python -m quant_futures_bot.auto_altcoin_optimizer --run-once --top 20 --limit 300 --show 10
python -m quant_futures_bot.altcoin_paper_monitor --run-once --top 5
```

看到 `websocket_tick` 说明 WebSocket 行情正常。看到 `altcoin top-volume aggressive strategy backtest` 说明山寨币策略回测正常。看到 `paper_summary` 说明山寨币 paper 模拟盘状态正常。

## 5. 安装 systemd 服务

```bash
sudo cp deploy/quant-websocket.service /etc/systemd/system/quant-websocket.service
sudo cp deploy/quant-optimizer.service /etc/systemd/system/quant-optimizer.service
sudo cp deploy/quant-optimizer.timer /etc/systemd/system/quant-optimizer.timer
sudo cp deploy/quant-altcoin-optimizer.service /etc/systemd/system/quant-altcoin-optimizer.service
sudo cp deploy/quant-altcoin-optimizer.timer /etc/systemd/system/quant-altcoin-optimizer.timer
sudo cp deploy/quant-altcoin-paper.service /etc/systemd/system/quant-altcoin-paper.service
sudo cp deploy/quant-altcoin-paper.timer /etc/systemd/system/quant-altcoin-paper.timer
sudo systemctl daemon-reload
```

## 6. 启动服务

```bash
sudo systemctl enable --now quant-websocket.service
sudo systemctl enable --now quant-optimizer.timer
sudo systemctl enable --now quant-altcoin-optimizer.timer
sudo systemctl enable --now quant-altcoin-paper.timer
```

## 7. 查看日志

主交易 WebSocket：

```bash
journalctl -u quant-websocket.service -f
```

BTC/ETH/SOL 主策略优化：

```bash
journalctl -u quant-optimizer.service -n 100
```

山寨币激进策略：

```bash
journalctl -u quant-altcoin-optimizer.service -n 100
tail -f /opt/quant-futures-bot/quant_futures_bot/logs/altcoin_strategy.log
cat /opt/quant-futures-bot/quant_futures_bot/data/altcoin_strategy_latest.json
```

山寨币 paper 模拟盘：

```bash
journalctl -u quant-altcoin-paper.service -n 100
tail -f /opt/quant-futures-bot/quant_futures_bot/logs/altcoin_paper.log
cat /opt/quant-futures-bot/quant_futures_bot/data/altcoin_paper_latest.json
```

## 8. 查看 timer

```bash
systemctl list-timers | grep quant
sudo systemctl status quant-altcoin-optimizer.timer
sudo systemctl status quant-altcoin-paper.timer
```

`quant-altcoin-optimizer.timer` 每 1 小时运行一次。
`quant-altcoin-paper.timer` 每 15 分钟运行一次。

## 9. 停止服务

```bash
sudo systemctl stop quant-websocket.service
sudo systemctl stop quant-optimizer.timer
sudo systemctl stop quant-altcoin-optimizer.timer
sudo systemctl stop quant-altcoin-paper.timer
```

## 10. 常见问题

如果 `git pull` 被本地改动挡住，先看：

```bash
git status
```

如果只是部署模板文件被改过，并且不需要保留：

```bash
git restore deploy/quant-optimizer.service
git pull
```

如果 systemd 找不到新服务，重新复制并 reload：

```bash
sudo cp deploy/quant-altcoin-optimizer.service /etc/systemd/system/quant-altcoin-optimizer.service
sudo cp deploy/quant-altcoin-optimizer.timer /etc/systemd/system/quant-altcoin-optimizer.timer
sudo cp deploy/quant-altcoin-paper.service /etc/systemd/system/quant-altcoin-paper.service
sudo cp deploy/quant-altcoin-paper.timer /etc/systemd/system/quant-altcoin-paper.timer
sudo systemctl daemon-reload
```
