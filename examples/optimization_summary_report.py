#!/usr/bin/env python3
"""
策略优化结果可视化报告
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def print_banner():
    print("=" * 90)
    print("""
     ██████╗ ███████╗███████╗████████╗    ██████╗ █████╗ ██████╗  █████╗ ███╗   ███╗
    ██╔═══██╗██╔════╝██╔════╝╚══██╔══╝   ██╔════╝██╔══██╗██╔══██╗██╔══██╗████╗ ████║
    ██║   ██║█████╗  ███████╗   ██║█████╗██║     ███████║██████╔╝███████║██╔████╔██║
    ██║   ██║██╔══╝  ╚════██║   ██║╚════╝██║     ██╔══██║██╔══██╗██╔══██║██║╚██╔╝██║
    ╚██████╔╝██║     ███████║   ██║      ╚██████╗██║  ██║██║  ██║██║  ██║██║ ╚═╝ ██║
     ╚═════╝ ╚═╝     ╚══════╝   ╚═╝       ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝
    """)
    print("=" * 90)


def print_strategy_ranking():
    """打印策略排名"""
    strategies = [
        ('bollinger', 33.08, 2.59, -0.38, 100.0, 2, {'period': 15, 'std_dev': 2.5}),
        ('atr_breakout', 30.42, 17.94, -2.74, 57.7, 26, {'period': 14, 'multiplier': 2.0}),
        ('donchian', 28.75, 15.93, -3.88, 57.1, 28, {'period': 20}),
        ('dual_ma', 22.43, 2.85, -4.35, 56.2, 16, {'fast': 5, 'slow': 20, 'ma_type': 'sma'}),
        ('momentum', 22.05, 1.00, -5.48, 59.1, 22, {'period': 30}),
        ('volume_price', 21.67, 4.90, -20.98, 50.7, 71, {'period': 10}),
        ('rsi', 20.70, -2.57, -3.56, 60.0, 5, {'period': 14, 'overbought': 80, 'oversold': 20}),
        ('macd', 18.47, -5.41, -7.88, 55.9, 34, {'fast': 8, 'slow': 21, 'signal': 5}),
    ]
    
    print("\n🏆 策略综合排名 (按得分)")
    print("-" * 90)
    print(f"{'排名':<4} {'策略':<15} {'得分':<8} {'收益':<10} {'回撤':<8} {'胜率':<8} {'交易':<6} {'最佳参数'}")
    print("-" * 90)
    
    for i, (name, score, ret, dd, wr, trades, params) in enumerate(strategies, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        params_str = str(params)[:25]
        print(f"{medal} {i:<2} {name:<13} {score:>6.2f} {ret:>+7.2f}% {dd:>6.2f}% {wr:>6.1f}% {trades:>4} {params_str}")
    
    print("-" * 90)


def print_return_chart():
    """打印收益条形图"""
    print("\n📊 收益率可视化")
    print("-" * 90)
    
    strategies = [
        ('atr_breakout', 17.94),
        ('donchian', 15.93),
        ('volume_price', 4.90),
        ('dual_ma', 2.85),
        ('bollinger', 2.59),
        ('momentum', 1.00),
        ('rsi', -2.57),
        ('macd', -5.41),
    ]
    
    max_val = max([s[1] for s in strategies])
    min_val = min([s[1] for s in strategies])
    
    for name, val in strategies:
        bar_len = int((val - min_val) / (max_val - min_val) * 50) if max_val != min_val else 25
        bar = "█" * bar_len
        emoji = "🟢" if val > 0 else "🔴"
        print(f"{name:<15} {emoji} {val:>+7.2f}% {bar}")
    
    print("-" * 90)


def print_drawdown_chart():
    """打印回撤条形图"""
    print("\n📉 回撤对比 (越小越好)")
    print("-" * 90)
    
    strategies = [
        ('bollinger', 0.38),
        ('atr_breakout', 2.74),
        ('rsi', 3.56),
        ('donchian', 3.88),
        ('dual_ma', 4.35),
        ('momentum', 5.48),
        ('macd', 7.88),
        ('volume_price', 20.98),
    ]
    
    max_val = max([s[1] for s in strategies])
    
    for name, val in strategies:
        bar_len = int(val / max_val * 50)
        bar = "█" * bar_len
        print(f"{name:<15} {val:>6.2f}% {bar}")
    
    print("-" * 90)


def print_strategy_categories():
    """按策略类型分类"""
    print("\n📚 按策略类型分类")
    print("-" * 90)
    
    categories = {
        '趋势策略': [
            ('atr_breakout', 17.94, 30.42),
            ('donchian', 15.93, 28.75),
            ('dual_ma', 2.85, 22.43),
            ('momentum', 1.00, 22.05),
        ],
        '均值回归': [
            ('bollinger', 2.59, 33.08),
            ('rsi', -2.57, 20.70),
        ],
        '量价策略': [
            ('volume_price', 4.90, 21.67),
        ],
        '震荡策略': [
            ('macd', -5.41, 18.47),
        ],
    }
    
    for category, strategies in categories.items():
        print(f"\n{category}:")
        avg_return = sum([s[1] for s in strategies]) / len(strategies)
        print(f"  平均收益: {avg_return:+.2f}%")
        for name, ret, score in sorted(strategies, key=lambda x: x[2], reverse=True):
            print(f"  • {name:<15} 收益: {ret:>+6.2f}%  得分: {score:>5.2f}")


def print_key_insights():
    """打印关键洞察"""
    print("\n💡 关键洞察")
    print("-" * 90)
    
    insights = [
        ("1. 最佳策略", "Bollinger (得分33.08): 回撤极小(-0.38%)，胜率100%"),
        ("2. 最高收益", "ATR Breakout (+17.94%): 但回撤稍大(-2.74%)"),
        ("3. 最稳健", "Donchian (+15.93%): 高收益+低回撤(-3.88%)的平衡"),
        ("4. 趋势vs回归", "趋势策略平均+9.43%，均值回归平均+0.01%"),
        ("5. 参数敏感", "Volume-Price周期10最优，周期20/30表现差"),
        ("6. MACD困境", "所有参数组合均为负收益，可能不适合当前市场环境"),
        ("7. RSI优化", "提高阈值(80/20)比标准(70/30)表现更好"),
    ]
    
    for title, desc in insights:
        print(f"   📌 {title}: {desc}")


def print_recommended_portfolio():
    """打印推荐组合"""
    print("\n🎯 推荐策略组合")
    print("-" * 90)
    
    print("""
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                                                                             │
    │  保守型组合 (低风险)                                                         │
    │  ───────────────────────────────────────────────────────────────────────   │
    │  • Bollinger (40%): period=15, std_dev=2.5                                  │
    │    理由: 回撤最小(-0.38%)，胜率100%                                          │
    │                                                                             │
    │  • Dual MA (30%): fast=5, slow=20, ma_type=sma                              │
    │    理由: 稳定收益(+2.85%)，适中回撤(-4.35%)                                  │
    │                                                                             │
    │  • Momentum (30%): period=30                                                 │
    │    理由: 趋势确认，与其他策略低相关性                                         │
    │                                                                             │
    └─────────────────────────────────────────────────────────────────────────────┘
    
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                                                                             │
    │  激进型组合 (高收益)                                                         │
    │  ───────────────────────────────────────────────────────────────────────   │
    │  • ATR Breakout (40%): period=14, multiplier=2.0                            │
    │    理由: 最高收益(+17.94%)                                                   │
    │                                                                             │
    │  • Donchian (40%): period=20                                                │
    │    理由: 次高收益(+15.93%)，回撤可控(-3.88%)                                  │
    │                                                                             │
    │  • Bollinger (20%): period=15, std_dev=2.5                                  │
    │    理由: 降低组合回撤，提高稳健性                                             │
    │                                                                             │
    └─────────────────────────────────────────────────────────────────────────────┘
    """)


def print_quick_start():
    """打印快速开始"""
    print("\n🚀 快速开始代码")
    print("-" * 90)
    
    print("""
```python
from brain.strategies.lib import generate_strategy
from brain.backtest import BacktestEngine
import pandas as pd

# 加载数据
data = pd.read_csv('stock.csv', index_col='date', parse_dates=True)

# 方案1: 使用单策略 (推荐Bollinger - 最稳健)
signals = generate_strategy(
    data=data,
    strategy_name='bollinger',
    period=15,
    std_dev=2.5
)

# 方案2: 使用多策略组合
signals1 = generate_strategy(data, 'bollinger', period=15, std_dev=2.5)
signals2 = generate_strategy(data, 'atr_breakout', period=14, multiplier=2.0)
combined = (signals1 * 0.6 + signals2 * 0.4).clip(-1, 1)

# 回测
engine = BacktestEngine(engine_type='ashare')
result = engine.run(data, signals, symbol='000001')

print(f"收益率: {result['return_pct']}%")
print(f"最大回撤: {result['max_drawdown']}%")
```
    """)


def print_best_params_reference():
    """打印最佳参数速查表"""
    print("\n📖 最佳参数速查表")
    print("-" * 90)
    
    print("""
┌─────────────────┬─────────────────────────────────────────┬──────────┐
│ 策略            │ 最佳参数                                 │ 预期收益  │
├─────────────────┼─────────────────────────────────────────┼──────────┤
│ bollinger       │ period=15, std_dev=2.5                  │ +2.59%   │
│ atr_breakout    │ period=14, multiplier=2.0               │ +17.94%  │
│ donchian        │ period=20                               │ +15.93%  │
│ dual_ma         │ fast=5, slow=20, ma_type='sma'          │ +2.85%   │
│ momentum        │ period=30                               │ +1.00%   │
│ volume_price    │ period=10                               │ +4.90%   │
│ rsi             │ period=14, overbought=80, oversold=20   │ -2.57%   │
│ macd            │ fast=8, slow=21, signal=5               │ -5.41%   │
└─────────────────┴─────────────────────────────────────────┴──────────┘
    """)


def main():
    print_banner()
    print_strategy_ranking()
    print_return_chart()
    print_drawdown_chart()
    print_strategy_categories()
    print_key_insights()
    print_recommended_portfolio()
    print_quick_start()
    print_best_params_reference()
    
    print("\n" + "=" * 90)
    print("📁 相关文件")
    print("-" * 90)
    print("   • examples/optimize_all_strategies.py - 批量优化脚本")
    print("   • reports/strategy_optimization_*.json - 详细结果")
    print("   • BOLLINGER_OPTIMIZATION_REPORT.md - Bollinger专项报告")
    print("   • GitHub: https://github.com/AlexJCD2025/brain")
    print("=" * 90)


if __name__ == "__main__":
    main()
