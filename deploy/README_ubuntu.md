# Ubuntu 云服务器部署与服务管理

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
| `quant-websocket.service` | 常驻服务 | 推荐 | 主流币 BTC/ETH/SOL WebSocket 盯盘并向 Testnet/Demo 下单 |
| `quant-optimizer.timer` | 定时器 | 推荐 | 每 4 小时优化主流币策略 |
| `quant-optimizer.service` | 单次任务 | 自动触发 | 被 `quant-optimizer.timer` 调用，也可手动跑一次 |
| `quant-altcoin-optimizer.timer` | 定时器 | 推荐 | 每 1 小时优化山寨币策略 |
| `quant-altcoin-optimizer.service` | 单次任务 | 自动触发 | 扫描成交量前 100，生成 `altcoin_strategy_latest.json` |
| `quant-altcoin-websocket.service` | 常驻服务 | 推荐 | 山寨币 WebSocket 盯盘，所有达标策略限价挂单 |
| `quant-macro-optimizer.timer` | 定时器 | 推荐 | 每 4 小时优化黄金、白银、美股、指数等映射策略 |
| `quant-macro-optimizer.service` | 单次任务 | 自动触发 | 生成 `macro_strategy_latest.json` |
| `quant-macro-websocket.service` | 常驻服务 | 推荐 | 宏观映射 WebSocket 盯盘并限价挂单 |
| `quant-altcoin-paper.timer` | 定时器 | 可选 | 山寨币本地 paper 模拟，不向交易所下单 |
| `quant-altcoin-testnet.timer` | 定时器 | 备用 | 旧版 15 分钟一次山寨币 Testnet 检查，不建议和 WebSocket 同开 |

注意：`quant-altcoin-websocket.service` 和 `quant-altcoin-testnet.timer` 不要同时开启，避免两套山寨币服务同时提交订单。

## 更新项目

```bash
cd /opt/quant-futures-bot && git pull && /opt/miniconda/envs/quant-bot/bin/pip install -r requirements.txt
```

## 配置 API

编辑 `.env`：

```bash
nano /opt/quant-futures-bot/.env
```

内容示例：

```bash
EXECUTION_MODE=testnet
BINANCE_TESTNET_API_KEY=你的_testnet_key
BINANCE_TESTNET_API_SECRET=你的_testnet_secret
```

## 安装或更新 systemd 文件

一行复制全部服务文件：

```bash
cd /opt/quant-futures-bot && sudo cp -v deploy/*.service /etc/systemd/system/ && sudo cp -v deploy/*.timer /etc/systemd/system/ && sudo systemctl daemon-reload
```

## 推荐启动组合

主流币 + 山寨币 + 宏观映射：

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

## 一键查看状态

```bash
systemctl status quant-websocket.service
systemctl status quant-optimizer.timer
systemctl status quant-altcoin-optimizer.timer
systemctl status quant-altcoin-websocket.service
systemctl status quant-macro-optimizer.timer
systemctl status quant-macro-websocket.service
```

可选和备用服务：

```bash
systemctl status quant-altcoin-paper.timer
systemctl status quant-altcoin-testnet.timer
```

## 一键停止

停止推荐运行组合：

```bash
sudo systemctl stop quant-websocket.service quant-optimizer.timer quant-optimizer.service
sudo systemctl stop quant-altcoin-optimizer.timer quant-altcoin-optimizer.service quant-altcoin-websocket.service
sudo systemctl stop quant-macro-optimizer.timer quant-macro-optimizer.service quant-macro-websocket.service
```

停止全部相关服务：

```bash
sudo systemctl stop quant-websocket.service quant-optimizer.timer quant-optimizer.service
sudo systemctl stop quant-altcoin-optimizer.timer quant-altcoin-optimizer.service quant-altcoin-websocket.service
sudo systemctl stop quant-altcoin-paper.timer quant-altcoin-paper.service quant-altcoin-testnet.timer quant-altcoin-testnet.service
sudo systemctl stop quant-macro-optimizer.timer quant-macro-optimizer.service quant-macro-websocket.service
```

## 主流币服务

启动：

```bash
sudo systemctl enable --now quant-websocket.service
sudo systemctl enable --now quant-optimizer.timer
```

状态：

```bash
systemctl status quant-websocket.service
systemctl status quant-optimizer.timer quant-optimizer.service
```

日志：

```bash
journalctl -u quant-websocket.service -f
journalctl -u quant-optimizer.service -n 100
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

停止：

```bash
sudo systemctl stop quant-altcoin-optimizer.timer quant-altcoin-optimizer.service quant-altcoin-websocket.service
```

清理山寨币优化锁后重新跑：

```bash
sudo systemctl stop quant-altcoin-optimizer.service && rm -f /opt/quant-futures-bot/quant_futures_bot/data/altcoin_optimizer.lock && sudo systemctl start --no-block quant-altcoin-optimizer.service
```

当前山寨币筛选参数：

- `min_score=0`
- `max_leaders=30`
- `min_trades=4`
- `min_side_ratio=0`，允许单边策略
- `fold_count=4`
- `min_profitable_fold_ratio=0.25`

## 宏观映射服务

宏观映射会自动寻找 Binance USDT 合约中实际存在的黄金、白银、美股、指数、商品等映射合约。没有的标的会跳过。

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

停止：

```bash
sudo systemctl stop quant-macro-optimizer.timer quant-macro-optimizer.service quant-macro-websocket.service
```

清理宏观优化锁后重新跑：

```bash
sudo systemctl stop quant-macro-optimizer.service && rm -f /opt/quant-futures-bot/quant_futures_bot/data/macro_optimizer.lock && sudo systemctl start --no-block quant-macro-optimizer.service
```

## 查看账户与持仓

```bash
cd /opt/quant-futures-bot && /opt/miniconda/envs/quant-bot/bin/python -m quant_futures_bot.account_watch
```

输出包含：

- 账户权益、钱包余额、可用余额、占用保证金
- 未实现盈亏
- 当前持仓
- 最近 24 小时、7 天、30 天已实现盈亏
- 手续费、资金费、净盈亏

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

## 下载本地历史 K 线

用于后续本地回测的数据仓库：

```bash
/opt/quant-futures-bot/quant_futures_bot/data/historical_ohlcv/binance_usdt_futures/
```

下载 2022 年 1 月到 2026 年 1 月的 K 线：

```bash
cd /opt/quant-futures-bot && /opt/miniconda/envs/quant-bot/bin/python -m quant_futures_bot.historical_data --start 2022-01-01 --end 2026-01-01 --timeframes 15m,30m,1h,4h,6h --include-main --include-altcoin-latest --include-macro-latest
```

只下载主流币：

```bash
cd /opt/quant-futures-bot && /opt/miniconda/envs/quant-bot/bin/python -m quant_futures_bot.historical_data --start 2022-01-01 --end 2026-01-01 --timeframes 1h,4h,6h --symbols BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT
```

查看索引：

```bash
cat /opt/quant-futures-bot/quant_futures_bot/data/historical_ohlcv/binance_usdt_futures/manifest.json
```

说明：

- 文件格式是 `csv.gz`，不用额外数据库。
- 支持断点续传，重复执行会从已有文件最后一根 K 线后继续下载。
- 如果标的在 2022 年之后才上市，只会保存交易所实际能返回的数据。

## 重要风控

山寨币和宏观映射 Testnet 交易都只做限价挂单：

- 开仓挂单 `180` 秒未成交撤单
- 平仓挂单 `60` 秒未成交撤单并重新评估
- 连续 `3` 次挂单失败暂停该标的
- 每轮先同步交易所余额、持仓、未成交订单

山寨币 crash watch 默认参数：

```bash
--crash-watch-drop-pct 0.03
--crash-watch-breadth-ratio 0.6
--crash-short-trailing-pct 0.03
```

含义：至少 60% 的交易标的最近 4 根 K 线跌超 3% 时，空单切换为追踪止盈，避免在瀑布行情中太早固定止盈。
