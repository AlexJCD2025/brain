# 🎯 Brain 策略库文档

本文档介绍 brain 量化框架的策略库，包含多种技术指标策略和批量回测系统。

## 📚 策略列表

### 1. 双均线 (Dual MA)
```python
from brain.strategies.lib import generate_strategy

signals = generate_strategy(
    data=data,
    strategy_name="dual_ma",
    fast=10,      # 短期均线
    slow=30       # 长期均线
)
```
**逻辑**: 金叉买入，死叉卖出  
**参数**:
- `fast`: 短期周期 (默认10)
- `slow`: 长期周期 (默认30)

**推荐参数组合**:
- 短线: (5, 20)
- 中线: (10, 30)
- 长线: (20, 60)

---

### 2. MACD
```python
signals = generate_strategy(
    data=data,
    strategy_name="macd",
    fast=12,      # 快线
    slow=26,      # 慢线
    signal=9      # 信号线
)
```
**逻辑**: MACD线上穿信号线买入，下穿卖出  
**推荐参数**: (12, 26, 9) 标准参数

---

### 3. RSI 均值回归
```python
signals = generate_strategy(
    data=data,
    strategy_name="rsi",
    period=14,        # RSI周期
    overbought=70,    # 超买阈值
    oversold=30       # 超卖阈值
)
```
**逻辑**: RSI低于超卖线买入，高于超买线卖出  
**推荐参数**:
- 短线: (7, 75, 25)
- 标准: (14, 70, 30)

---

### 4. 布林带
```python
signals = generate_strategy(
    data=data,
    strategy_name="bollinger",
    period=20,      # 均线周期
    std_dev=2.0     # 标准差倍数
)
```
**逻辑**: 触及下轨买入，触及上轨卖出  
**推荐参数**: (20, 2.0) 标准参数

---

### 5. 动量策略
```python
signals = generate_strategy(
    data=data,
    strategy_name="momentum",
    period=20       # 动量周期
)
```
**逻辑**: 动量转正买入，转负卖出  
**推荐参数**: (20) 或 (60) 月线/季度线

---

### 6. ATR突破
```python
signals = generate_strategy(
    data=data,
    strategy_name="atr_breakout",
    period=14,         # ATR周期
    multiplier=2.0     # ATR乘数
)
```
**逻辑**: 突破ATR通道上轨买入，跌破下轨卖出  
**推荐参数**: (14, 2.0) - 海龟交易风格

---

### 7. 唐奇安通道 (海龟)
```python
signals = generate_strategy(
    data=data,
    strategy_name="donchian",
    period=20       # 通道周期
)
```
**逻辑**: 突破N日高点买入，跌破N日低点卖出  
**推荐参数**: (20) 短期, (55) 中期, (100) 长期

---

### 8. 量价趋势
```python
signals = generate_strategy(
    data=data,
    strategy_name="volume_price",
    period=20       # 均线周期
)
```
**逻辑**: 价格突破均线+成交量放大买入  
**推荐参数**: (20) 标准周期

---

## 🚀 批量回测

### 快速开始

```bash
cd /home/alex_jiang/brain
source .venv/bin/activate
python examples/batch_backtest.py
```

### 生成自定义策略组合

```python
from brain.strategies.lib import StrategyOptimizer

# 生成所有策略组合
strategies = StrategyOptimizer.generate_all_strategies()
# 返回: [(strategy_id, strategy_name, params), ...]

# 生成特定策略的参数网格
params_list = StrategyOptimizer.generate_param_grid("dual_ma")
```

### 自定义批量回测

```python
from brain.strategies.lib import generate_strategy
from brain.backtest import BacktestEngine

# 测试多个策略
strategy_configs = [
    ("dual_ma", {"fast": 5, "slow": 20}),
    ("atr_breakout", {"period": 14, "multiplier": 2.0}),
    ("donchian", {"period": 55}),
]

results = []
for name, params in strategy_configs:
    signals = generate_strategy(data, name, **params)
    engine = BacktestEngine(engine_type="ashare")
    result = engine.run(data, signals, symbol="000001")
    results.append(result)
```

---

## 📊 回测结果可视化

```bash
python examples/visualize_results.py
```

输出包括:
- ASCII条形图显示策略收益率排名
- 按策略类型汇总统计
- 绩效矩阵 (平均/中位数/最高/最低)
- Top 5策略详情
- 自动生成最佳策略的Python代码

---

## 🎯 最佳实践

### 1. 参数优化建议

| 策略 | 推荐参数 | 适用场景 |
|------|----------|----------|
| 双均线 | (10, 30) | 趋势市场 |
| MACD | (12, 26, 9) | 通用 |
| RSI | (14, 70, 30) | 震荡市场 |
| ATR突破 | (14, 2.0) | 趋势启动 |
| 唐奇安 | (55) | 中长线趋势 |

### 2. 策略组合建议

**稳健型组合**:
- 趋势: 双均线 (20, 60) 权重40%
- 均值回归: RSI (14, 70, 30) 权重30%
- 突破: ATR突破 (14, 2.0) 权重30%

**激进型组合**:
- 趋势: 唐奇安 (20) 权重50%
- 动量: 动量策略 (20) 权重50%

### 3. A股特殊考虑

使用 `AShareEngine` 自动处理:
- ✅ T+1: 当日买入不能卖出
- ✅ 涨跌停: 涨停不能买，跌停不能卖
- ✅ 手数: 100股整数倍
- ✅ 手续费: 佣金+印花税+过户费

---

## 📈 实测结果示例

```
🏆 Top 5 策略 (基于2022-2023模拟数据)

1. ATR突破 (14, 2.0)      收益率: +17.94%  得分: 20.88
2. 唐奇安通道 (20)         收益率: +15.93%  得分: 19.19
3. 唐奇安通道 (100)        收益率: +7.03%   得分: 15.71
4. 双均线 (5, 60)          收益率: +6.21%   得分: 14.70
5. 双均线 (5, 20)          收益率: +2.85%   得分: 12.69
```

---

## 🔧 扩展新策略

### 步骤1: 在 lib.py 中添加策略函数

```python
@staticmethod
def my_strategy(data: pd.DataFrame, param1: int = 10) -> pd.Series:
    """我的自定义策略"""
    close = data['close']
    
    # 计算信号
    signals = pd.Series(0, index=data.index)
    buy_condition = ...
    sell_condition = ...
    
    signals[buy_condition] = 1
    signals[sell_condition] = -1
    
    return signals
```

### 步骤2: 添加到策略映射

```python
strategy_map = {
    'my_strategy': StrategyGenerator.my_strategy,
    # ... 其他策略
}
```

### 步骤3: 添加参数网格

```python
param_grids = {
    'my_strategy': [
        {'param1': 10},
        {'param1': 20},
    ],
}
```

---

## 📚 相关文件

- `brain/strategies/lib.py` - 策略库实现
- `examples/batch_backtest.py` - 批量回测脚本
- `examples/visualize_results.py` - 结果可视化
- `examples/test_new_engine.py` - 新引擎测试

---

## 🔗 更多资源

- [Backtrader文档](https://www.backtrader.com/docu/)
- [技术指标大全](https://www.investopedia.com/terms/t/technicalindicator.asp)
- [海龟交易法则](https://www.investopedia.com/articles/trading/08/turtle-trading.asp)

---

**Happy Trading! 🚀**
