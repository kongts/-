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

## 安装

```bash
pip install -r requirements.txt
```

## 离线运行一轮

```bash
python -m quant_futures_bot.main --offline --cycles 1
```

## 使用交易所行情运行

```bash
python -m quant_futures_bot.main --cycles 1
```

如果 ccxt 或网络不可用，系统会自动退回本地模拟 K 线。

## 回测

```bash
python -m quant_futures_bot.backtest
```

## 数据文件

- SQLite: `quant_futures_bot/data/quant_bot.db`
- 状态: `quant_futures_bot/data/state.json`
- 错误日志: `quant_futures_bot/logs/error.log`

当前版本只做本地模拟成交，不真实下单。Testnet、WebSocket、实盘执行、部分成交和撤单已在模块边界上预留。

