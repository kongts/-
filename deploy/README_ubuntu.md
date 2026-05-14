# Ubuntu 云服务器部署与服务管理

默认项目目录：

```bash
/opt/quant-futures-bot
```

默认 Python 环境：

```bash
/opt/miniconda/envs/quant-bot/bin/python
```

## 服务总览

| 服务 | 类型 | 是否推荐开启 | 作用 |
| --- | --- | --- | --- |
| `quant-websocket.service` | 常驻服务 | 推荐 | 主策略 BTC/ETH/SOL WebSocket 盯盘，连接 Testnet，按主策略管理仓位。 |
| `quant-optimizer.timer` | 定时器 | 推荐 | 每 4 小时运行一次主策略优化，更新 BTC/ETH/SOL 最优策略。 |
| `quant-optimizer.service` | 单次任务 | 自动触发 | 被 `quant-optimizer.timer` 调用，也可以手动运行一次。 |
| `quant-altcoin-optimizer.timer` | 定时器 | 推荐 | 每 1 小时扫描 Binance USDT 合约交易量前 100，滚动回测山寨币策略。 |
| `quant-altcoin-optimizer.service` | 单次任务 | 自动触发 | 被 `quant-altcoin-optimizer.timer` 调用，生成 `altcoin_strategy_latest.json`。 |
| `quant-altcoin-websocket.service` | 常驻服务 | 推荐 | 山寨币 Testnet WebSocket 盯盘，读取全部达标策略，使用限价 post-only 挂单。 |
| `quant-altcoin-paper.timer` | 定时器 | 可选 | 山寨币本地 paper 模拟，不向交易所下单。 |
| `quant-altcoin-paper.service` | 单次任务 | 可选 | 被 `quant-altcoin-paper.timer` 调用，也可以手动运行一次。 |
| `quant-altcoin-testnet.timer` | 定时器 | 不建议与 WebSocket 同开 | 旧版每 15 分钟检查一次山寨币 Testnet 挂单，作为备用。 |
| `quant-altcoin-testnet.service` | 单次任务 | 备用 | 被 `quant-altcoin-testnet.timer` 调用。现在主要使用 `quant-altcoin-websocket.service`。 |

注意：`quant-altcoin-websocket.service` 和 `quant-altcoin-testnet.timer` 不要同时开启，否则可能出现两套山寨币服务同时提交订单。

## 更新项目

```bash
cd /opt/quant-futures-bot && git pull && /opt/miniconda/envs/quant-bot/bin/pip install -r requirements.txt
```

## 环境变量

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

## 安装或更新 systemd 服务文件

一行复制全部服务文件：

```bash
cd /opt/quant-futures-bot && sudo cp -v deploy/*.service /etc/systemd/system/ && sudo cp -v deploy/*.timer /etc/systemd/system/ && sudo systemctl daemon-reload
```

如果只更新山寨币优化服务：

```bash
cd /opt/quant-futures-bot && git pull && sudo cp -v deploy/quant-altcoin-optimizer.service /etc/systemd/system/ && sudo systemctl daemon-reload
```

## 推荐启动组合

主策略 + 山寨币 Testnet 实盘模拟挂单：

```bash
sudo systemctl enable --now quant-websocket.service && sudo systemctl enable --now quant-optimizer.timer && sudo systemctl enable --now quant-altcoin-optimizer.timer && sudo systemctl enable --now quant-altcoin-websocket.service
```

只运行山寨币 paper 模拟，不向交易所下单：

```bash
sudo systemctl enable --now quant-altcoin-paper.timer
```

不建议开启旧版山寨币 Testnet 定时器。如果确实要用备用模式，先停止 WebSocket：

```bash
sudo systemctl stop quant-altcoin-websocket.service && sudo systemctl enable --now quant-altcoin-testnet.timer
```

## 一键查看状态

```bash
systemctl status quant-websocket.service quant-optimizer.timer quant-altcoin-optimizer.timer quant-altcoin-websocket.service
```

查看可选/备用服务：

```bash
systemctl status quant-altcoin-paper.timer quant-altcoin-testnet.timer
```

## 一键停止

停止推荐运行组合：

```bash
sudo systemctl stop quant-websocket.service quant-optimizer.timer quant-optimizer.service quant-altcoin-optimizer.timer quant-altcoin-optimizer.service quant-altcoin-websocket.service
```

停止所有相关服务，包括 paper 和备用 Testnet：

```bash
sudo systemctl stop quant-websocket.service quant-optimizer.timer quant-optimizer.service quant-altcoin-optimizer.timer quant-altcoin-optimizer.service quant-altcoin-websocket.service quant-altcoin-paper.timer quant-altcoin-paper.service quant-altcoin-testnet.timer quant-altcoin-testnet.service
```

## 主策略 WebSocket

作用：实时盯 BTC/ETH/SOL，连接 Testnet，读取账户、持仓、行情，并按主策略运行。

启动：

```bash
sudo systemctl enable --now quant-websocket.service
```

状态：

```bash
systemctl status quant-websocket.service
```

日志：

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

## 主策略优化

作用：每 4 小时优化 BTC/ETH/SOL 主策略。

启动定时器：

```bash
sudo systemctl enable --now quant-optimizer.timer
```

状态：

```bash
systemctl status quant-optimizer.timer quant-optimizer.service
```

日志：

```bash
journalctl -u quant-optimizer.service -n 100
```

手动运行一次：

```bash
sudo systemctl start quant-optimizer.service
```

停止：

```bash
sudo systemctl stop quant-optimizer.timer quant-optimizer.service
```

禁用开机自启：

```bash
sudo systemctl disable quant-optimizer.timer
```

## 山寨币策略优化

作用：每 1 小时抓取 Binance USDT 合约交易量前 100，滚动回测 `15m`、`30m` 山寨币激进策略，把所有 `score >= 1.0` 的组合写入：

```bash
/opt/quant-futures-bot/quant_futures_bot/data/altcoin_strategy_latest.json
```

这个服务只做回测和策略筛选，不会下单。

启动定时器：

```bash
sudo systemctl enable --now quant-altcoin-optimizer.timer
```

状态：

```bash
systemctl status quant-altcoin-optimizer.timer quant-altcoin-optimizer.service
```

实时进度日志：

```bash
journalctl -u quant-altcoin-optimizer.service -f
```

最近 100 行日志：

```bash
journalctl -u quant-altcoin-optimizer.service -n 100
```

文件日志：

```bash
tail -f /opt/quant-futures-bot/quant_futures_bot/logs/altcoin_strategy.log
```

手动后台运行一次，命令行马上返回：

```bash
sudo systemctl start --no-block quant-altcoin-optimizer.service
```

停止：

```bash
sudo systemctl stop quant-altcoin-optimizer.timer quant-altcoin-optimizer.service
```

禁用开机自启：

```bash
sudo systemctl disable quant-altcoin-optimizer.timer
```

如果看到锁文件提示：

```text
optimizer_lock_exists path=/opt/quant-futures-bot/quant_futures_bot/data/altcoin_optimizer.lock action=skip
```

说明上一轮优化还在跑，或者上次被强制停止后留下锁。确认没有任务在跑后清理：

```bash
sudo systemctl stop quant-altcoin-optimizer.service && rm -f /opt/quant-futures-bot/quant_futures_bot/data/altcoin_optimizer.lock && sudo systemctl start --no-block quant-altcoin-optimizer.service
```

正常进度会显示：

```text
fetching 1/100 SOL/USDT:USDT quote_volume=...
fetching_ohlcv 1/100 SOL/USDT:USDT timeframe=15m limit=500
fetching_ohlcv 1/100 SOL/USDT:USDT timeframe=30m limit=500
```

## 山寨币 Testnet WebSocket

作用：实时订阅所有评分达标的山寨币 `bookTicker`，每到对应 `15m`/`30m` K 线收盘运行策略，每 30 秒维护挂单超时、撤单和暂停状态。该服务会向 Binance Futures Demo/Testnet 提交限价挂单。

启动：

```bash
sudo systemctl enable --now quant-altcoin-websocket.service
```

状态：

```bash
systemctl status quant-altcoin-websocket.service
```

实时日志：

```bash
journalctl -u quant-altcoin-websocket.service -f
```

文件日志：

```bash
tail -f /opt/quant-futures-bot/quant_futures_bot/logs/altcoin_testnet.log
```

停止：

```bash
sudo systemctl stop quant-altcoin-websocket.service
```

禁用开机自启：

```bash
sudo systemctl disable quant-altcoin-websocket.service
```

## 山寨币 Paper 模拟

作用：每 15 分钟读取最新山寨币策略，在本地 paper 账户模拟，不向交易所下单。

启动：

```bash
sudo systemctl enable --now quant-altcoin-paper.timer
```

状态：

```bash
systemctl status quant-altcoin-paper.timer quant-altcoin-paper.service
```

日志：

```bash
journalctl -u quant-altcoin-paper.service -n 100
```

手动运行一次：

```bash
sudo systemctl start quant-altcoin-paper.service
```

停止：

```bash
sudo systemctl stop quant-altcoin-paper.timer quant-altcoin-paper.service
```

禁用开机自启：

```bash
sudo systemctl disable quant-altcoin-paper.timer
```

## 山寨币 Testnet 定时器备用

作用：旧版每 15 分钟检查一次山寨币 Testnet 挂单。现在主运行方式是 `quant-altcoin-websocket.service`，一般不要开启这个 timer。

启动备用模式：

```bash
sudo systemctl enable --now quant-altcoin-testnet.timer
```

状态：

```bash
systemctl status quant-altcoin-testnet.timer quant-altcoin-testnet.service
```

日志：

```bash
journalctl -u quant-altcoin-testnet.service -n 100
```

手动运行一次：

```bash
sudo systemctl start quant-altcoin-testnet.service
```

停止：

```bash
sudo systemctl stop quant-altcoin-testnet.timer quant-altcoin-testnet.service
```

禁用开机自启：

```bash
sudo systemctl disable quant-altcoin-testnet.timer
```

## 山寨币 Testnet 交易规则

- 运行范围：所有回测 `score >= 1.0` 的组合，不限前 5。
- `--top 0` 表示读取 `altcoin_strategy_latest.json` 里的全部达标组合。
- 只做限价挂单：`--order-type limit`。
- 默认 `--maker-offset 0.001`，买单低于信号价约 `0.1%`，卖单高于信号价约 `0.1%`。
- 使用 post-only，尽量避免直接吃单。
- 每轮先同步交易所余额、持仓、未成交挂单。
- 开仓挂单超过 `180` 秒未成交会撤单。
- 平仓挂单超过 `60` 秒未成交会撤单并重新评估。
- 同一币种连续 `3` 次挂单失败会暂停该币种。
- `15m` 策略最长持仓 `8` 根 K，约 `2` 小时。
- `30m` 策略最长持仓 `6` 根 K，约 `3` 小时。
- 超过最长持仓时，如果浮盈不足 `3%`，挂单平仓。
- 超过最长持仓且浮盈达到 `3%`，切换为 `3%` 追踪止盈。
- 进入追踪止盈后仍有二次最长持仓：`15m` 再延长 `4` 根 K，`30m` 再延长 `3` 根 K。
- 二次最长持仓到期仍未触发追踪止盈，会直接挂单平仓。

看到下面内容，表示已经向交易所测试盘提交限价挂单：

```text
testnet_order ... type=limit ... status=submitted post_only=YES
```

## 山寨币回测成本

山寨币滚动回测默认按：

- maker 手续费：`0.02%`
- 保守资金费：每 8 小时 `0.01%`

排名日志里的 `funding` 是该策略回测期间扣掉的资金费估算值。

## 瀑布预警

山寨币模块默认参数：

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

查看一次账户、持仓和浮盈浮亏：

```bash
cd /opt/quant-futures-bot && /opt/miniconda/envs/quant-bot/bin/python -m quant_futures_bot.account_watch
```

如果你的代码还没更新到自动读取 `.env`，可以临时这样运行：

```bash
cd /opt/quant-futures-bot && set -a && source .env && set +a && /opt/miniconda/envs/quant-bot/bin/python -m quant_futures_bot.account_watch
```

如需持续刷新：

```bash
cd /opt/quant-futures-bot && /opt/miniconda/envs/quant-bot/bin/python -m quant_futures_bot.account_watch --watch --interval-seconds 5
```

输出示例：

```text
Account Snapshot  2026-05-14 13:20:00
========================================================================
Equity                  4964.51 USDT
Wallet                  5000.00 USDT
Available               4374.11 USDT
Used Margin              590.40 USDT  (11.89%)
Unrealized PnL           -16.40 USDT
Positions                     2
Open Orders                   0

Positions
----------------------------------------------------------------------------------------------------------------
Symbol              Side              Qty         Entry          Mark      Notional      Margin         PnL     PnL%
BTC/USDT:USDT       LONG       0.01000000  79814.600000  78852.200000        788.52      394.26       -9.62   -1.22%
```

退出实时查看：

```text
Ctrl + C
```

查看 CPU：

```bash
top
```

查看 CPU 占用前 20：

```bash
ps aux --sort=-%cpu | head -20
```

查看最新山寨币策略：

```bash
cat /opt/quant-futures-bot/quant_futures_bot/data/altcoin_strategy_latest.json
```

查看山寨币 Testnet 最新状态：

```bash
cat /opt/quant-futures-bot/quant_futures_bot/data/altcoin_testnet_latest.json
```

查看山寨币挂单和暂停状态：

```bash
cat /opt/quant-futures-bot/quant_futures_bot/data/altcoin_testnet_runtime_state.json
```

只退出日志查看，不停止服务：

```text
Ctrl + C
```
