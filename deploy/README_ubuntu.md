# Ubuntu 云服务器部署与运维

默认项目目录：

```bash
/opt/quant-futures-bot
```

默认 Python：

```bash
/opt/miniconda/envs/quant-bot/bin/python
```

## 服务总览

| 服务 | 类型 | 建议 | 说明 |
| --- | --- | --- | --- |
| `quant-websocket.service` | 常驻服务 | 推荐 | 主流币 BTC/ETH/SOL WebSocket 监控并向 Testnet/Demo 下单 |
| `quant-optimizer.timer` | 定时器 | 推荐 | 每 4 小时优化主流币策略 |
| `quant-altcoin-optimizer.timer` | 定时器 | 推荐 | 每 1 小时优化山寨币策略 |
| `quant-altcoin-websocket.service` | 常驻服务 | 推荐 | 山寨币 WebSocket 监控、每 60 秒实时信号检查、限价挂单 |
| `quant-macro-optimizer.timer` | 定时器 | 推荐 | 每 4 小时优化宏观映射策略 |
| `quant-macro-websocket.service` | 常驻服务 | 推荐 | 宏观映射 WebSocket 监控、每 60 秒实时信号检查、限价挂单 |
| `quant-altcoin-paper.timer` | 定时器 | 可选 | 山寨币本地 paper 模拟，不向交易所下单 |
| `quant-altcoin-testnet.timer` | 定时器 | 备用 | 旧版 15 分钟一次山寨币 Testnet 检查，不建议和 WebSocket 同时开启 |

注意：`quant-altcoin-websocket.service` 和 `quant-altcoin-testnet.timer` 不要同时开启，避免两套山寨币服务同时提交订单。

## 更新项目

```bash
cd /opt/quant-futures-bot
git pull origin main
/opt/miniconda/envs/quant-bot/bin/pip install -r requirements.txt
```

如果更新了 `deploy/*.service` 或 `deploy/*.timer`，需要重新安装 systemd 文件：

```bash
cd /opt/quant-futures-bot
sudo cp -v deploy/*.service /etc/systemd/system/
sudo cp -v deploy/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
```

一行更新并重启山寨币/宏观 WebSocket：

```bash
cd /opt/quant-futures-bot && git pull origin main && sudo cp -v deploy/quant-altcoin-websocket.service deploy/quant-macro-websocket.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl restart quant-altcoin-websocket.service quant-macro-websocket.service
```

## 配置 API

编辑 `.env`：

```bash
nano /opt/quant-futures-bot/.env
```

示例：

```bash
EXECUTION_MODE=testnet
BINANCE_TESTNET_API_KEY=你的_testnet_key
BINANCE_TESTNET_API_SECRET=你的_testnet_secret
INVERT_EXECUTION_SIGNALS=0
```

`INVERT_EXECUTION_SIGNALS=0` 表示正向执行策略信号；如需临时反向执行，改为 `1` 后重启服务。

## 推荐启动组合

```bash
sudo systemctl enable --now quant-websocket.service
sudo systemctl enable --now quant-optimizer.timer
sudo systemctl enable --now quant-altcoin-optimizer.timer
sudo systemctl enable --now quant-altcoin-websocket.service
sudo systemctl enable --now quant-macro-optimizer.timer
sudo systemctl enable --now quant-macro-websocket.service
```

只运行山寨币 paper 模拟：

```bash
sudo systemctl enable --now quant-altcoin-paper.timer
```

## 一行查看状态

```bash
systemctl is-active quant-websocket.service quant-altcoin-websocket.service quant-macro-websocket.service quant-altcoin-optimizer.timer quant-macro-optimizer.timer
```

详细状态：

```bash
systemctl status quant-websocket.service
systemctl status quant-altcoin-websocket.service
systemctl status quant-macro-websocket.service
systemctl status quant-altcoin-optimizer.timer
systemctl status quant-macro-optimizer.timer
```

## 查看账户和持仓

```bash
cd /opt/quant-futures-bot
/opt/miniconda/envs/quant-bot/bin/python -m quant_futures_bot.account_watch
```

输出包含：

- 账户权益、钱包余额、可用余额、占用保证金
- 未实现盈亏
- 当前真实持仓
- 当前未成交订单数量
- 最近 24 小时、7 天、30 天已实现盈亏、手续费、资金费

## 全部平仓

先 dry-run 预览，不撤单也不下单：

```bash
cd /opt/quant-futures-bot
/opt/miniconda/envs/quant-bot/bin/python -m quant_futures_bot.close_all_positions
```

正式执行：先撤未成交挂单，再用 `reduceOnly` 市价单平掉所有真实持仓。

```bash
cd /opt/quant-futures-bot
/opt/miniconda/envs/quant-bot/bin/python -m quant_futures_bot.close_all_positions --confirm YES
```

如果要彻底避免机器人马上重新开仓，先停服务：

```bash
sudo systemctl stop quant-websocket.service quant-altcoin-websocket.service quant-macro-websocket.service
```

平仓后检查：

```bash
/opt/miniconda/envs/quant-bot/bin/python -m quant_futures_bot.account_watch
```

看到 `No open positions.` 且 `Open Orders` 为 `0` 或无挂单即可。

## 实时开仓检查

山寨币和宏观 WebSocket 默认带：

```bash
--live-signal-seconds 60
```

含义：

- WebSocket 实时盯价格；
- 每 60 秒用当前最新行情执行一次策略检查；
- 原来的 K 线收线检查仍保留；
- 日志会出现 `live signal check`。

查看山寨币实时日志：

```bash
journalctl -u quant-altcoin-websocket.service -f | egrep "live signal check|strategy_cycle|testnet_order|signal_rejected|pending_order|symbol_paused|summary|error"
```

查看宏观实时日志：

```bash
journalctl -u quant-macro-websocket.service -f | egrep "live signal check|strategy_cycle|testnet_order|signal_rejected|pending_order|symbol_paused|summary|error"
```

## 主流币服务

启动：

```bash
sudo systemctl enable --now quant-websocket.service
sudo systemctl enable --now quant-optimizer.timer
```

日志：

```bash
journalctl -u quant-websocket.service -f
journalctl -u quant-optimizer.service -n 100 --no-pager
```

手动优化一次：

```bash
sudo systemctl start quant-optimizer.service
```

停止：

```bash
sudo systemctl stop quant-websocket.service quant-optimizer.timer quant-optimizer.service
```

## 山寨币服务

启动：

```bash
sudo systemctl enable --now quant-altcoin-optimizer.timer
sudo systemctl enable --now quant-altcoin-websocket.service
```

状态：

```bash
systemctl status quant-altcoin-optimizer.timer quant-altcoin-optimizer.service
systemctl status quant-altcoin-websocket.service
```

实时日志：

```bash
journalctl -u quant-altcoin-optimizer.service -f
journalctl -u quant-altcoin-websocket.service -f
tail -f /opt/quant-futures-bot/quant_futures_bot/logs/altcoin_strategy.log
tail -f /opt/quant-futures-bot/quant_futures_bot/logs/altcoin_testnet.log
```

手动优化一次：

```bash
sudo systemctl start --no-block quant-altcoin-optimizer.service
```

清理本地山寨币状态和暂停记录：仅在确认交易所真实无仓位后使用。

```bash
cd /opt/quant-futures-bot && sudo systemctl stop quant-altcoin-websocket.service && mv quant_futures_bot/data/altcoin_testnet_state.json quant_futures_bot/data/altcoin_testnet_state.json.bak.$(date +%s) 2>/dev/null; mv quant_futures_bot/data/altcoin_testnet_runtime_state.json quant_futures_bot/data/altcoin_testnet_runtime_state.json.bak.$(date +%s) 2>/dev/null; sudo systemctl start quant-altcoin-websocket.service
```

当前山寨币筛选参数：

- `min_score=0`
- `max_leaders=30`
- `min_trades=4`
- `min_side_ratio=0`
- `fold_count=4`
- `min_profitable_fold_ratio=0.25`
- 默认回测候选已扩展到动量突破、成交量突破、波动突破、10/20/40 突破、MA 回撤、RSI 动量、均值回归。
- systemd 默认使用 `--strategy-workers 4` 并行回测策略；CPU 较小可改成 `2`，CPU 充足可手动改成 `6` 或 `8`。

## 宏观映射服务

宏观映射会自动寻找 Binance USDT 合约中实际存在的黄金、白银、美股、指数、商品等映射合约；不存在的标的会跳过。

启动：

```bash
sudo systemctl enable --now quant-macro-optimizer.timer
sudo systemctl enable --now quant-macro-websocket.service
```

状态：

```bash
systemctl status quant-macro-optimizer.timer quant-macro-optimizer.service
systemctl status quant-macro-websocket.service
```

实时日志：

```bash
journalctl -u quant-macro-optimizer.service -f
journalctl -u quant-macro-websocket.service -f
tail -f /opt/quant-futures-bot/quant_futures_bot/logs/macro_strategy.log
tail -f /opt/quant-futures-bot/quant_futures_bot/logs/macro_testnet.log
```

手动优化一次：

```bash
sudo systemctl start --no-block quant-macro-optimizer.service
```

## 常用文件

主流币：

```bash
cat /opt/quant-futures-bot/quant_futures_bot/data/selected_strategy.json
cat /opt/quant-futures-bot/quant_futures_bot/data/state.json
```

山寨币：

```bash
cat /opt/quant-futures-bot/quant_futures_bot/data/altcoin_strategy_latest.json
cat /opt/quant-futures-bot/quant_futures_bot/data/altcoin_testnet_latest.json
cat /opt/quant-futures-bot/quant_futures_bot/data/altcoin_testnet_runtime_state.json
```

宏观映射：

```bash
cat /opt/quant-futures-bot/quant_futures_bot/data/macro_strategy_latest.json
cat /opt/quant-futures-bot/quant_futures_bot/data/macro_testnet_latest.json
cat /opt/quant-futures-bot/quant_futures_bot/data/macro_testnet_runtime_state.json
```

## 常见问题

### 服务在跑但不开仓

检查：

```bash
journalctl -u quant-altcoin-websocket.service -n 300 --no-pager | egrep "live signal check|strategy_cycle|testnet_order|signal_rejected|pending_order|symbol_paused|summary|error"
```

常见原因：

- `signals=0`：当前策略没有信号；
- `signal_rejected ... symbol margin ratio exceeded`：保证金比例或仓位限制太严；
- `pending_order_timeout_cancelled`：post-only 限价单没有成交；
- `symbol_paused`：同一标的连续 3 次挂单失败，已暂停；
- `local_positions` 有持仓但 `exchange_positions=-`：本地状态残留，先用 `account_watch` 确认真仓位，再清状态。

### 清理优化器锁

山寨币：

```bash
sudo systemctl stop quant-altcoin-optimizer.service && rm -f /opt/quant-futures-bot/quant_futures_bot/data/altcoin_optimizer.lock && sudo systemctl start --no-block quant-altcoin-optimizer.service
```

宏观：

```bash
sudo systemctl stop quant-macro-optimizer.service && rm -f /opt/quant-futures-bot/quant_futures_bot/data/macro_optimizer.lock && sudo systemctl start --no-block quant-macro-optimizer.service
```

## 停止全部交易相关服务

```bash
sudo systemctl stop quant-websocket.service quant-optimizer.timer quant-optimizer.service
sudo systemctl stop quant-altcoin-optimizer.timer quant-altcoin-optimizer.service quant-altcoin-websocket.service
sudo systemctl stop quant-altcoin-paper.timer quant-altcoin-paper.service quant-altcoin-testnet.timer quant-altcoin-testnet.service
sudo systemctl stop quant-macro-optimizer.timer quant-macro-optimizer.service quant-macro-websocket.service
```
