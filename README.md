# Quant Futures Bot

Binance Futures Demo/Testnet 量化交易项目。

当前主要运行线：

- `quant-websocket.service`：BTC/ETH/SOL 主策略 WebSocket 盯盘与 Testnet 下单。
- `quant-optimizer.timer`：每 4 小时优化 BTC/ETH/SOL 主策略。
- `quant-altcoin-optimizer.timer`：每 1 小时滚动回测山寨币激进策略。
- `quant-altcoin-paper.timer`：每 15 分钟运行山寨币 paper 模拟。
- `quant-altcoin-websocket.service`：WebSocket 实时盯盘所有评分达标的山寨币，并在 K 线收盘时提交 Testnet 限价挂单。
- `quant-altcoin-testnet.timer`：备用周期检查，每 15 分钟运行一次山寨币 Testnet 逻辑。

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
sudo cp deploy/quant-altcoin-paper.service /etc/systemd/system/quant-altcoin-paper.service
sudo cp deploy/quant-altcoin-paper.timer /etc/systemd/system/quant-altcoin-paper.timer
sudo cp deploy/quant-altcoin-websocket.service /etc/systemd/system/quant-altcoin-websocket.service
sudo cp deploy/quant-altcoin-testnet.service /etc/systemd/system/quant-altcoin-testnet.service
sudo cp deploy/quant-altcoin-testnet.timer /etc/systemd/system/quant-altcoin-testnet.timer

sudo systemctl daemon-reload
```

## 全部服务命令

### 主策略 WebSocket 盯盘

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

关闭开机自启：

```bash
sudo systemctl disable quant-websocket.service
```

### 主策略优化定时器

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

关闭开机自启：

```bash
sudo systemctl disable quant-optimizer.timer
```

### 山寨币策略优化定时器

用途：每 1 小时抓取 Binance USDT 合约交易量前 100，滚动回测山寨币激进策略，并把所有 `score >= 1.0` 的组合写入最新策略文件。

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

关闭开机自启：

```bash
sudo systemctl disable quant-altcoin-optimizer.timer
```

### 山寨币 Paper 模拟定时器

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

关闭开机自启：

```bash
sudo systemctl disable quant-altcoin-paper.timer
```

### 山寨币 Testnet WebSocket 盯盘

用途：实时订阅所有评分达标的山寨币 bookTicker；每到对应 15m/30m K 线收盘运行策略；每 30 秒维护挂单超时、撤单和暂停状态。

启动：

```bash
sudo systemctl enable --now quant-altcoin-websocket.service
```

查看状态：

```bash
systemctl status quant-altcoin-websocket.service
```

查看日志：

```bash
journalctl -u quant-altcoin-websocket.service -f
tail -f /opt/quant-futures-bot/quant_futures_bot/logs/altcoin_testnet.log
```

停止：

```bash
sudo systemctl stop quant-altcoin-websocket.service
```

关闭开机自启：

```bash
sudo systemctl disable quant-altcoin-websocket.service
```

### 山寨币 Testnet 限价挂单定时器备用

用途：备用周期检查。现在主运行方式是 `quant-altcoin-websocket.service`，这个 timer 一般不用同时开启，避免两条服务同时提交山寨币订单。

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

关闭开机自启：

```bash
sudo systemctl disable quant-altcoin-testnet.timer
```

## 一键查看所有服务状态

```bash
systemctl status quant-websocket.service
systemctl status quant-optimizer.timer
systemctl status quant-altcoin-optimizer.timer
systemctl status quant-altcoin-paper.timer
systemctl status quant-altcoin-websocket.service
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
sudo systemctl stop quant-altcoin-websocket.service
sudo systemctl stop quant-altcoin-testnet.timer
sudo systemctl stop quant-altcoin-testnet.service
```

## 一键启动推荐组合

只运行主策略和山寨币 Testnet 挂单：

```bash
sudo systemctl enable --now quant-websocket.service
sudo systemctl enable --now quant-optimizer.timer
sudo systemctl enable --now quant-altcoin-optimizer.timer
sudo systemctl enable --now quant-altcoin-websocket.service
```

如果只想模拟山寨币，不向交易所下单，不要启动 `quant-altcoin-websocket.service`，改成：

```bash
sudo systemctl enable --now quant-altcoin-paper.timer
```

## 本地命令

主策略单次 Testnet：

```bat
run_testnet_once.bat
```

主策略 WebSocket：

```bat
run_testnet_websocket.bat
```

山寨币 Testnet 限价挂单单次运行：

```bat
run_altcoin_testnet_once.bat
```

山寨币 Paper 模拟单次运行：

```bat
run_altcoin_paper_once.bat
```

## 山寨币策略规则

山寨币 Testnet 只做限价挂单：

- 运行范围不再限制前 5，而是所有回测 `score >= 1.0` 的组合。
- `--top 0` 表示不限数量，读取 `altcoin_strategy_latest.json` 里的全部达标组合。
- 不使用市价单。
- 使用 post-only 参数，避免直接吃单。
- 买单价格约低于信号价 `0.1%`。
- 卖单价格约高于信号价 `0.1%`。
- 挂单提交后不会立刻记为本地成交。
- 是否成交以交易所测试盘实际订单和持仓为准。
- 每轮先同步交易所余额、持仓、未成交挂单，再决定是否继续下单。
- 开仓挂单超过 `180` 秒未成交会撤单。
- 平仓挂单超过 `60` 秒未成交会撤单并重新评估。
- 同一币种连续 `3` 次挂单失败会暂停该币种。
- `15m` 策略最长持仓 `8` 根 K 线，约 `2` 小时。
- `30m` 策略最长持仓 `6` 根 K 线，约 `3` 小时。
- 超过最长持仓时，如果浮盈不足 `3%`，挂单平仓。
- 超过最长持仓且浮盈达到 `3%`，切换为 `3%` 追踪止盈继续持有。
- 进入追踪止盈后仍有二次最长持仓：`15m` 再延长 `4` 根 K，`30m` 再延长 `3` 根 K。
- 二次最长持仓到期仍未触发追踪止盈，会直接挂单平仓。

看到类似下面内容，表示已提交限价挂单：

```text
testnet_order symbol=SUI/USDT:USDT action=OPEN_LONG type=limit ... exchange_order_id=123456789 status=submitted post_only=YES
```

最新状态文件：

```bash
cat /opt/quant-futures-bot/quant_futures_bot/data/altcoin_testnet_latest.json
cat /opt/quant-futures-bot/quant_futures_bot/data/altcoin_testnet_runtime_state.json
```

## 瀑布预警风控

山寨币模块使用 crash watch：

- 至少 `60%` 的交易币种最近 4 根 K 线跌超 `3%`，进入瀑布预警。
- 普通模式：空单达到 `6%` 浮盈会固定止盈。
- 瀑布预警：空单不再按 `6%` 固定止盈，而是提前启用 `3%` 追踪止盈。
- 空单继续盈利时继续持有；从最大浮盈回撤超过 `3%` 时，才挂单平空。
- 止损仍然保留，默认亏损 `2.5%` 会触发平仓信号。

相关参数：

```bash
--crash-watch-drop-pct 0.03
--crash-watch-breadth-ratio 0.6
--crash-short-trailing-pct 0.03
```

日志出现下面内容，表示进入瀑布预警：

```text
crash_watch=ON symbols=5 avg_recent_drop=-4.25% trigger_drop=3.00% short_trailing=3.00%
```

## 手动回测

主策略回测：

```bash
python -m quant_futures_bot.backtest
```

主策略优化：

```bash
python -m quant_futures_bot.strategy_optimizer
```

山寨币交易量前 100 回测：

```bash
python -m quant_futures_bot.altcoin_top_volume_backtest --top 100 --limit 500 --timeframes 15m,30m --show 30 --fee-rate 0.0002 --funding-cost-rate-per-8h 0.0001
```

山寨币滚动优化：

```bash
python -m quant_futures_bot.auto_altcoin_optimizer --run-once --top 100 --limit 500 --timeframes 15m,30m --show 30 --min-score 1.0 --max-leaders 0 --fee-rate 0.0002 --funding-cost-rate-per-8h 0.0001
```

山寨币回测默认按挂单 maker 手续费 `0.02%` 估算，并按每 8 小时 `0.01%` 的保守资金费成本扣减持仓名义价值。输出里的 `funding` 表示本次回测扣掉的资金费估算值。
