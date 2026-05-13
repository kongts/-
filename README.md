# 加密货币合约量化 Paper Trading 系统

这是一个基于 Python 的 Binance USDT-M Futures 多币种 Paper Trading 系统第一阶段实现。

已实现：

- BTC/ETH/SOL 多币种
- 事件驱动链路：MarketEvent -> SignalEvent -> RiskEngine -> OrderEvent -> Execution -> FillEvent -> Portfolio -> Database
- MA 趋势策略与 RSI 震荡策略自动切换
- 多空、单向持仓、逐仓低杠杆模拟
- 风控最终否决权
- Paper Trading 成交、滑点、手续费
- 订单状态机
- SQLite 数据库存储
- state.json 状态恢复
- 暂停机制
- 基础回测指标

当前版本只做本地模拟成交，不真实下单。Testnet、WebSocket、实盘执行、部分成交和撤单已在模块边界上预留。

## 安装

在项目根目录运行：

```bash
pip install -r requirements.txt
```

项目根目录是：

```text
C:\Users\kongt\Documents\New project 2
```

## 离线运行一轮

不依赖交易所网络，使用本地模拟 K 线：

```bash
python -m quant_futures_bot.main --offline --cycles 1
```

如果你的终端运行 `python` 后没有任何输出，说明 Windows 可能命中了 Microsoft Store 的 Python 占位启动器。可以改用项目自带脚本：

```bat
run_offline_once.bat
```

或者使用真实 Python 路径：

```bat
"%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" -m quant_futures_bot.main --offline --cycles 1
```

终端会输出类似：

```text
cycle=1 equity=10000.00 used_margin=0.00 status=RUNNING execution_mode=paper orders_created=0 fills_created=0 exchange_order_ids=- data_source=BTC/USDT:USDT=synthetic,ETH/USDT:USDT=synthetic,SOL/USDT:USDT=synthetic
```

字段含义：

- `cycle`：当前运行轮次
- `equity`：账户权益
- `used_margin`：已用保证金
- `status`：系统状态，可能是 `RUNNING`、`PAUSED` 或 `STOPPED`
- `execution_mode`：执行模式，`paper` 是本地模拟成交，`testnet` 是 Binance Futures Testnet
- `orders_created`：本轮生成的订单数
- `fills_created`：本轮成交数
- `exchange_order_ids`：Testnet 返回的真实测试网订单 ID；`-` 表示本轮没有交易所订单
- `data_source`：每个交易品种的数据来源，`synthetic` 表示模拟 K 线，`exchange` 表示交易所真实行情

## 使用交易所行情运行

使用 ccxt 拉取 Binance Futures 行情：

```bash
python -m quant_futures_bot.main --cycles 1
```

如果这条命令没有任何输出，使用项目自带脚本：

```bat
run_live_once.bat
```

或者使用真实 Python 路径：

```bat
"%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" -m quant_futures_bot.main --cycles 1
```

如果 ccxt 或网络不可用，系统会自动退回本地模拟 K 线。

## 使用 Binance Futures Testnet 模拟盘

默认执行模式是本地 Paper Trading：

```text
EXECUTION_MODE=paper
```

如果要接入 Binance Futures Testnet，需要先在当前终端设置环境变量。不要把 API Key 或 Secret 写进代码、README 或 bat 文件。

```bat
set BINANCE_TESTNET_API_KEY=你的testnet_api_key
set BINANCE_TESTNET_API_SECRET=你的testnet_api_secret
```

然后运行：

```bat
run_testnet_once.bat
```

这个脚本会设置：

```text
EXECUTION_MODE=testnet
```

然后执行一轮当前策略。Testnet 模式会向 Binance Futures Testnet 发送真实测试网订单，但不会动真钱。

运行后看终端输出：

```text
execution_mode=testnet orders_created=1 fills_created=1 exchange_order_ids=123456789
```

如果 `orders_created=0`，说明本轮策略没有产生下单信号，或者信号被风控拒绝。
如果 `exchange_order_ids=-`，说明本轮没有交易所订单 ID。

## 实时盯盘

如果要持续盯盘，而不是只运行一轮，可以使用监控脚本。

本地 Paper Trading 盯盘：

```bat
run_paper_monitor.bat
```

Binance Futures Testnet 盯盘：

```bat
run_testnet_monitor.bat
```

Testnet 盯盘前必须先设置环境变量：

```bat
set BINANCE_TESTNET_API_KEY=你的testnet_api_key
set BINANCE_TESTNET_API_SECRET=你的testnet_api_secret
```

默认每 60 秒检查一次行情和信号。终端会持续输出：

```text
[2026-05-13 10:00:00] cycle=1 equity=9998.20 used_margin=600.30 status=RUNNING execution_mode=testnet signals=0 rejected=0 orders_created=0 fills_created=0 exchange_order_ids=- prices=BTC/USDT:USDT=103000.0000,... strategy=BTC/USDT:USDT=mean_reversion_20/4h,... data_source=BTC/USDT:USDT=exchange,...
```

字段含义：

- `signals`：本轮产生的策略信号数
- `rejected`：本轮被风控拒绝或无可用数量的信号数
- `orders_created`：本轮生成的订单数
- `fills_created`：本轮成交数
- `exchange_order_ids`：Testnet 返回的订单 ID
- `prices`：本轮拉到的最新收盘价
- `strategy`：每个币种当前使用的策略和 K 线周期

停止盯盘：在终端按 `Ctrl+C`。

盯盘脚本每一轮都会重新读取 `selected_strategy.json`，所以如果你同时运行 `auto_optimize_every_4h.bat`，最新优化策略会在下一轮盯盘时生效。

如果终端提示缺少环境变量，可以运行：

```bat
set_testnet_env_example.bat
```

它只会显示示例命令，不会保存你的真实 key。

## 怎么判断是模拟还是真实行情

看终端输出里的 `data_source`：

```text
data_source=BTC/USDT:USDT=synthetic,ETH/USDT:USDT=synthetic,SOL/USDT:USDT=synthetic
```

含义：

- `synthetic`：本地模拟 K 线
- `exchange`：通过 ccxt 获取的 Binance Futures 行情

也可以打开 SQLite 数据库的 `market_data` 表，查看 `data_source` 字段。

## 查看回测结果

最推荐先用回测看系统效果。现在 `run_backtest.bat` 默认会在线拉取 Binance Futures 历史行情：

```bash
python -m quant_futures_bot.backtest
```

如果这条命令没有任何输出，直接运行：

```bat
run_backtest.bat
```

或者：

```bat
"%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" -m quant_futures_bot.backtest
```

也可以直接运行：

```bat
run_backtest.bat
```

会输出类似：

```text
final_equity=10414.77
return_pct=4.15%
max_drawdown=2.89%
sharpe=6.59
win_rate=50.00%
long_win_rate=0.00%
short_win_rate=66.67%
trade_count=4
profit_factor=1.83
max_consecutive_losses=2
pause_count=0
data_source=BTC/USDT:USDT=exchange,ETH/USDT:USDT=exchange,SOL/USDT:USDT=exchange
```

`data_source=exchange` 表示这次回测使用交易所历史行情。

如果你只是想断网测试代码，可以显式运行离线模拟回测：

```bat
run_backtest_offline.bat
```

真实历史行情回测结果可能会因为交易所返回的最新 K 线变化而变化。

字段含义：

- `final_equity`：最终账户权益
- `return_pct`：收益率
- `max_drawdown`：最大回撤
- `sharpe`：夏普比率
- `win_rate`：总胜率
- `long_win_rate`：多单胜率
- `short_win_rate`：空单胜率
- `trade_count`：交易次数
- `profit_factor`：盈亏比
- `max_consecutive_losses`：最大连续亏损次数
- `pause_count`：触发暂停次数
- `data_source`：回测数据来源，`exchange` 是真实历史行情，`synthetic` 是本地模拟 K 线

## 按币种多策略优化并应用到当前运行

运行：

```bat
optimize_strategy.bat
```

系统会：

1. 在线拉取 Binance Futures 历史 K 线
2. 对 BTC、ETH、SOL 分别测试多个周期：`4h`、`6h`
3. 对每个币种、每个周期、每个策略做 Walk Forward 回测
4. 用滚动测试段评估稳定性，不只看单次收益
5. 按收益、夏普、回撤、交易次数、稳定盈利窗口比例综合评分
6. 为每个币种单独选择最优策略和周期
7. 把结果写入 `quant_futures_bot/data/selected_strategy.json`

当前候选策略：

- `regime_ma_rsi`：趋势用 MA，震荡用 RSI
- `ma_trend`：均线趋势策略
- `rsi_range`：RSI 震荡策略
- `breakout_20`：20 根 K 线突破策略
- `breakout_40`：40 根 K 线突破策略
- `mean_reversion_20`：20 周期均值回归
- `mean_reversion_30`：30 周期均值回归

优化完成后，再运行：

```bat
run_live_once.bat
```

终端输出会显示当前使用的策略：

```text
strategy=BTC/USDT:USDT=mean_reversion_20/4h,ETH/USDT:USDT=mean_reversion_20/6h,SOL/USDT:USDT=mean_reversion_20/4h
```

这表示 Paper Trading 当前会按币种使用优化器选出的策略和 K 线周期。策略优化不会真实下单，只会决定本地模拟盘使用哪套策略逻辑。

如果希望系统每 4 小时自动重新回测并更新最新策略，运行：

```bat
auto_optimize_every_4h.bat
```

这个脚本会先立刻优化一次，然后每隔 4 小时再次运行 `optimize_strategy`，更新 `quant_futures_bot/data/selected_strategy.json`。之后 `run_live_once.bat` 会读取最新策略。

注意：优化器选出的是“当前候选策略里评分最高的策略”，不等于它一定是盈利策略。重点看优化输出里的验证段指标：

- `test_return`：验证段收益
- `test_dd`：验证段最大回撤
- `test_sharpe`：验证段夏普
- `trades`：验证段交易次数

如果排名第一的策略 `test_return` 仍然是负数，说明当前候选策略整体还需要继续改进，不应该直接理解成“已经找到好策略”。

## 查看运行后的数据文件

运行主程序后，会生成这些文件：

- SQLite 数据库：`quant_futures_bot/data/quant_bot.db`
- 状态文件：`quant_futures_bot/data/state.json`
- 错误日志：`quant_futures_bot/logs/error.log`

SQLite 数据库里包含：

- `market_data`：行情数据
- `signals`：策略信号
- `orders`：订单状态
- `fills`：模拟成交
- `positions`：持仓
- `trades`：交易盈亏
- `equity_curve`：资金曲线
- `pause_logs`：暂停记录
- `error_logs`：错误记录

`state.json` 可以直接打开查看当前账户状态、持仓、系统状态、最大回撤、连续亏损次数等信息。
