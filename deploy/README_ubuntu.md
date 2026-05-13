# Ubuntu 云服务器部署

以下命令默认项目部署到：

```bash
/opt/quant-futures-bot
```

## 1. 安装依赖

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip curl
```

## 2. 测试服务器能否访问 Binance

```bash
curl https://testnet.binancefuture.com/fapi/v1/time
curl https://fapi.binance.com/fapi/v1/time
```

能返回 `serverTime` 才继续部署。

## 3. 拉取项目

```bash
sudo mkdir -p /opt/quant-futures-bot
sudo chown "$USER":"$USER" /opt/quant-futures-bot
git clone https://github.com/kongts/-.git /opt/quant-futures-bot
cd /opt/quant-futures-bot
```

## 4. 创建 Python 环境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 5. 配置 Testnet API

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

## 6. 手动测试

先优化策略：

```bash
source .venv/bin/activate
python -m quant_futures_bot.strategy_optimizer
```

再跑一轮盯盘：

```bash
python -m quant_futures_bot.live_monitor --max-cycles 1 --poll-seconds 10
```

看到 `execution_mode=testnet`，说明配置生效。

## 7. 安装 systemd 服务

```bash
sudo cp deploy/quant-monitor.service /etc/systemd/system/
sudo cp deploy/quant-optimizer.service /etc/systemd/system/
sudo cp deploy/quant-optimizer.timer /etc/systemd/system/
sudo systemctl daemon-reload
```

启动实时盯盘：

```bash
sudo systemctl enable --now quant-monitor.service
```

启动每 4 小时自动优化：

```bash
sudo systemctl enable --now quant-optimizer.timer
```

## 8. 查看运行状态

```bash
sudo systemctl status quant-monitor.service
sudo systemctl status quant-optimizer.timer
```

查看实时日志：

```bash
journalctl -u quant-monitor.service -f
```

查看优化器日志：

```bash
journalctl -u quant-optimizer.service -n 100
```

## 9. 停止服务

```bash
sudo systemctl stop quant-monitor.service
sudo systemctl stop quant-optimizer.timer
```

## 10. 更新项目

```bash
cd /opt/quant-futures-bot
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart quant-monitor.service
```

