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

## 安装 systemd

```bash
sudo cp deploy/quant-websocket.service /etc/systemd/system/quant-websocket.service
sudo cp deploy/quant-optimizer.service /etc/systemd/system/quant-optimizer.service
sudo cp deploy/quant-optimizer.timer /etc/systemd/system/quant-optimizer.timer
sudo cp deploy/quant-altcoin-optimizer.service /etc/systemd/system/quant-altcoin-optimizer.service
sudo cp deploy/quant-altcoin-optimizer.timer /etc/systemd/system/quant-altcoin-optimizer.timer
sudo cp deploy/quant-altcoin-testnet.service /etc/systemd/system/quant-altcoin-testnet.service
sudo cp deploy/quant-altcoin-testnet.timer /etc/systemd/system/quant-altcoin-testnet.timer
sudo systemctl daemon-reload
```

## 启动服务

```bash
sudo systemctl enable --now quant-websocket.service
sudo systemctl enable --now quant-optimizer.timer
sudo systemctl enable --now quant-altcoin-optimizer.timer
sudo systemctl enable --now quant-altcoin-testnet.timer
```

## 山寨币 Testnet 限价挂单

`quant-altcoin-testnet.timer` 每 15 分钟运行一次。

它只提交 Binance Futures Testnet/Demo 限价挂单：

- 不使用市价单。
- 使用 post-only。
- 买单低于信号价约 `0.1%`。
- 卖单高于信号价约 `0.1%`。

查看日志：

```bash
journalctl -u quant-altcoin-testnet.service -n 100
tail -f /opt/quant-futures-bot/quant_futures_bot/logs/altcoin_testnet.log
cat /opt/quant-futures-bot/quant_futures_bot/data/altcoin_testnet_latest.json
```

停止山寨币挂单：

```bash
sudo systemctl stop quant-altcoin-testnet.timer
```

## 查看全部 timer

```bash
systemctl list-timers | grep quant
```
