# Ubuntu 云服务器部署

以下命令默认项目部署到：

```bash
/opt/quant-futures-bot
```

## 1. 拉取项目

```bash
sudo mkdir -p /opt/quant-futures-bot
sudo chown "$USER":"$USER" /opt/quant-futures-bot
git clone https://github.com/kongts/-.git /opt/quant-futures-bot
cd /opt/quant-futures-bot
```

## 2. 安装 Python 环境

如果服务器使用 conda：

```bash
source /opt/miniconda/etc/profile.d/conda.sh
conda create -n quant-bot python=3.11 -y
conda activate quant-bot
pip install -r requirements.txt
```

如果使用 venv：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 3. 配置 Testnet API

不要把真实 key 提交到 Git。服务器上创建 `.env`：

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

## 4. 测试 Binance 网络

```bash
curl https://testnet.binancefuture.com/fapi/v1/time
curl https://fapi.binance.com/fapi/v1/time
```

能返回 `serverTime` 再继续。

## 5. 手动测试

```bash
cd /opt/quant-futures-bot
source /opt/miniconda/etc/profile.d/conda.sh
conda activate quant-bot
set -a; source .env; set +a

python -m quant_futures_bot.strategy_optimizer
python -m quant_futures_bot.websocket_monitor --print-seconds 5
```

看到 `websocket_tick` 说明实时行情已接通。看到 `execution_mode=testnet` 说明 Testnet 配置已生效。

## 6. 安装 systemd 服务

```bash
sudo cp deploy/quant-websocket.service /etc/systemd/system/quant-websocket.service
sudo cp deploy/quant-optimizer.service /etc/systemd/system/quant-optimizer.service
sudo cp deploy/quant-optimizer.timer /etc/systemd/system/quant-optimizer.timer
sudo cp deploy/quant-altcoin-optimizer.service /etc/systemd/system/quant-altcoin-optimizer.service
sudo cp deploy/quant-altcoin-optimizer.timer /etc/systemd/system/quant-altcoin-optimizer.timer
sudo systemctl daemon-reload
```

启动 WebSocket 盯盘：

```bash
sudo systemctl enable --now quant-websocket.service
```

启动每 4 小时自动优化：

```bash
sudo systemctl enable --now quant-optimizer.timer
```

启动每 1 小时山寨币激进策略滚动回测：

```bash
sudo systemctl enable --now quant-altcoin-optimizer.timer
```

## 7. 查看状态和日志

```bash
sudo systemctl status quant-websocket.service
sudo systemctl status quant-optimizer.timer
sudo systemctl status quant-altcoin-optimizer.timer
journalctl -u quant-websocket.service -f
```

查看优化器日志：

```bash
journalctl -u quant-optimizer.service -n 100
journalctl -u quant-altcoin-optimizer.service -n 100
```

## 8. 停止服务

```bash
sudo systemctl stop quant-websocket.service
sudo systemctl stop quant-optimizer.timer
sudo systemctl stop quant-altcoin-optimizer.timer
```

## 9. 更新项目

```bash
cd /opt/quant-futures-bot
git pull
/opt/miniconda/envs/quant-bot/bin/pip install -r requirements.txt
sudo systemctl restart quant-websocket.service
sudo systemctl restart quant-altcoin-optimizer.timer
```
