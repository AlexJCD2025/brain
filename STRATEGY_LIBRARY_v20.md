# 🎯 Brain 策略库 v2.0 - 完整策略清单 (20个)

## 📊 概览

Brain 量化框架现已集成 **20个** 技术指标策略，涵盖趋势追踪、均值回归、量价分析等多种类型。

---

## 📋 完整策略列表

### 1. 趋势策略 (Trend Following)

| # | 策略 | 英文名 | 类型 | 核心逻辑 |
|---|------|--------|------|---------|
| 1 | **双均线** | dual_ma | 趋势 | 快线上穿慢线买入 |
| 2 | **MACD** | macd | 趋势 | DIF上穿DEA买入 |
| 3 | **动量** | momentum | 趋势 | 价格上涨买入 |
| 4 | **ATR突破** | atr_breakout | 趋势 | ATR通道突破 |
| 5 | **唐奇安通道** | donchian | 趋势 | 通道上下轨突破 |
| 6 | **超级趋势** | supertrend | 趋势 | 超级趋势指标 |
| 7 | **一目均衡表** | ichimoku | 趋势 | 价格穿越云层 |
| 8 | **抛物线SAR** | parabolic_sar | 趋势 | 价格穿越SAR点 |

### 2. 均值回归策略 (Mean Reversion)

| # | 策略 | 英文名 | 类型 | 核心逻辑 |
|---|------|--------|------|---------|
| 9 | **RSI** | rsi | 均值回归 | 超卖(<30)买入，超买(>70)卖出 |
| 10 | **布林带** | bollinger | 均值回归 | 触及下轨买入，上轨卖出 |
| 11 | **KDJ** | kdj | 均值回归 | K上穿D买入 |
| 12 | **CCI** | cci | 均值回归 | CCI<-100买入，>100卖出 |
| 13 | **Williams %R** | williams_r | 均值回归 | <-80买入，>-20卖出 |
| 14 | **MFI** | mfi | 均值回归 | 成交量加权RSI |
| 15 | **随机震荡** | stochastic | 均值回归 | %K<20买入，>80卖出 |

### 3. 量价策略 (Volume-Price)

| # | 策略 | 英文名 | 类型 | 核心逻辑 |
|---|------|--------|------|---------|
| 16 | **量价趋势** | volume_price | 量价 | 价格突破+放量买入 |
| 17 | **OBV** | obv | 量价 | OBV上穿均线买入 |
| 18 | **VWAP** | vwap | 量价 | 价格上穿VWAP买入 |

### 4. 趋势强度/其他

| # | 策略 | 英文名 | 类型 | 核心逻辑 |
|---|------|--------|------|---------|
| 19 | **ADX** | adx | 趋势强度 | ADX>25时+DI>-DI买入 |
| 20 | **Heikin-Ashi** | heikin_ashi | 蜡烛图 | 连续3阳线买入 |

---

## 🚀 快速使用

### 单策略使用

```python
from brain.strategies.lib import generate_strategy

# 使用任何策略
signals = generate_strategy(data, 'ichimoku')           # 一目均衡表
signals = generate_strategy(data, 'parabolic_sar')      # 抛物线SAR
signals = generate_strategy(data, 'obv')                # OBV
signals = generate_strategy(data, 'adx')                # ADX
signals = generate_strategy(data, 'mfi')                # MFI
signals = generate_strategy(data, 'vwap')               # VWAP
signals = generate_strategy(data, 'stochastic')         # 随机震荡
signals = generate_strategy(data, 'heikin_ashi')        # Heikin-Ashi
```

### 带参数使用

```python
# 一目均衡表 - 自定义周期
signals = generate_strategy(
    data, 
    'ichimoku',
    tenkan_period=9,      # 转换线周期
    kijun_period=26,      # 基准线周期
    senkou_b_period=52    # 先行下线周期
)

# 抛物线SAR - 自定义加速因子
signals = generate_strategy(
    data,
    'parabolic_sar',
    af_start=0.02,        # 初始加速因子
    af_max=0.20           # 最大加速因子
)

# ADX - 自定义阈值
signals = generate_strategy(
    data,
    'adx',
    period=14,            # 周期
    threshold=25.0        # 趋势强度阈值
)

# MFI - 自定义超买超卖
signals = generate_strategy(
    data,
    'mfi',
    period=14,            # 周期
    overbought=80,        # 超买阈值
    oversold=20           # 超卖阈值
)
```

---

## 📖 策略详解

### 1. Ichimoku Cloud (一目均衡表)

```python
signals = generate_strategy(data, 'ichimoku')
```

日本经典趋势指标，包含5条线：
- **Tenkan-sen** (转换线): 短周期中线
- **Kijun-sen** (基准线): 中周期中线
- **Senkou Span A** (先行上线): 未来支撑阻力
- **Senkou Span B** (先行下线): 未来支撑阻力
- **Chikou Span** (延迟线): 26日前收盘价

**交易逻辑**: 价格上穿云层买入，下穿云层卖出

---

### 2. Parabolic SAR (抛物线SAR)

```python
signals = generate_strategy(data, 'parabolic_sar')
```

Welles Wilder开发的趋势追踪指标。

**交易逻辑**: 价格上穿SAR点买入，下穿卖出

**特点**: 
- 加速因子随趋势增强而增加
- 适合强趋势市场
- 反转时信号明确

---

### 3. OBV (能量潮)

```python
signals = generate_strategy(data, 'obv')
```

Joseph Granville开发的量价指标。

**计算公式**:
- 价格上涨: OBV += 成交量
- 价格下跌: OBV -= 成交量

**交易逻辑**: OBV上穿均线买入，下穿卖出

---

### 4. ADX (平均趋向指数)

```python
signals = generate_strategy(data, 'adx')
```

Welles Wilder开发的趋势强度指标。

**交易逻辑**:
- ADX > 25: 趋势市场
  - +DI > -DI: 买入
  - +DI < -DI: 卖出
- ADX < 25: 震荡市场，不交易

---

### 5. MFI (资金流量指标)

```python
signals = generate_strategy(data, 'mfi')
```

类似RSI但考虑成交量。

**计算公式**: MFI = 100 - (100 / (1 + 资金流比率))

**交易逻辑**: MFI < 20 超卖买入，MFI > 80 超买卖出

---

### 6. VWAP (成交量加权平均价)

```python
signals = generate_strategy(data, 'vwap')
```

机构常用交易基准。

**计算公式**: VWAP = Σ(典型价格 × 成交量) / Σ成交量

**交易逻辑**: 价格上穿VWAP买入，下穿卖出

**特点**:
- 反映机构成本
- 日内交易重要参考
- 长期趋势判断

---

### 7. Stochastic Oscillator (随机震荡)

```python
signals = generate_strategy(data, 'stochastic')
```

与KDJ类似但更简单。

**计算公式**:
- %K = 100 × (收盘价 - 最低价) / (最高价 - 最低价)
- %D = %K的3日移动平均

**交易逻辑**: %K < 20 超卖买入，%K > 80 超买卖出

---

### 8. Heikin-Ashi (平均K线)

```python
signals = generate_strategy(data, 'heikin_ashi')
```

日本蜡烛图变体，过滤噪音。

**计算公式**:
- HA收盘价 = (开+高+低+收) / 4
- HA开盘价 = (前HA开 + 前HA收) / 2

**交易逻辑**: 连续3根阳线买入，连续3根阴线卖出

**特点**:
- 过滤价格噪音
- 趋势更明确
- 减少假信号

---

## 📊 策略对比

### 按类型分类

| 类型 | 策略数量 | 代表策略 |
|------|---------|---------|
| 趋势策略 | 8 | ATR突破、一目均衡表 |
| 均值回归 | 7 | 布林带、RSI、KDJ |
| 量价策略 | 3 | OBV、VWAP |
| 趋势强度 | 1 | ADX |
| 蜡烛图 | 1 | Heikin-Ashi |

### 按适用市场

| 市场环境 | 推荐策略 |
|---------|---------|
| 强趋势 | ATR突破、抛物线SAR |
| 震荡 | 布林带、RSI、MFI |
| 高波动 | ADX、ATR突破 |
| 低波动 | 双均线、VWAP |

---

## 🎯 推荐组合

### 平衡型组合 (推荐)

```python
balanced_portfolio = {
    'atr_breakout': 0.30,      # 30% 趋势捕捉
    'ichimoku': 0.20,          # 20% 趋势确认
    'bollinger': 0.20,         # 20% 均值回归
    'rsi': 0.15,               # 15% 动量
    'obv': 0.10,               # 10% 量价确认
    'adx': 0.05                # 5% 趋势过滤
}
```

### 趋势型组合

```python
trend_portfolio = {
    'atr_breakout': 0.30,
    'ichimoku': 0.25,
    'parabolic_sar': 0.25,
    'donchian': 0.20
}
```

### 均值回归型组合

```python
mean_reversion_portfolio = {
    'bollinger': 0.30,
    'rsi': 0.25,
    'mfi': 0.20,
    'stochastic': 0.15,
    'williams_r': 0.10
}
```

---

## 📁 项目文件

```
brain/
├── brain/strategies/
│   └── lib.py                    ← 20个策略全部实现
├── examples/
│   ├── test_all_strategies.py    ← 全部策略测试
│   ├── optimize_all_strategies.py ← 批量优化
│   └── ...
└── STRATEGY_LIBRARY_v20.md       ← 本文档
```

---

## 🎓 学习路径

### 新手推荐
1. **双均线** - 最基础的趋势策略
2. **RSI** - 最基础的均值回归
3. **布林带** - 波动率+均值回归
4. **MACD** - 经典动量指标

### 进阶推荐
1. **一目均衡表** - 完整趋势系统
2. **ADX** - 判断趋势强度
3. **OBV** - 量价分析基础
4. **VWAP** - 机构视角

### 专家推荐
1. **多策略组合** - 降低单一策略风险
2. **动态参数调整** - 适应不同市场环境
3. **机器学习增强** - 预测信号质量

---

## 📞 联系信息

- **GitHub**: https://github.com/AlexJCD2025/brain
- **版本**: v2.0
- **策略数量**: 20
- **完成时间**: 2026-04-10

---

## 🎉 总结

Brain 框架现在拥有 **20个** 完整的交易策略：

- ✅ 8个趋势策略
- ✅ 7个均值回归策略  
- ✅ 3个量价策略
- ✅ 2个其他类型

所有策略：
- ✅ 已测试通过
- ✅ 集成到generate_strategy()
- ✅ 可参数化配置
- ✅ 支持组合使用

**Happy Trading! 🚀**
