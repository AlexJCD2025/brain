#!/usr/bin/env python3
"""
D. 测试新策略 - KDJ, CCI, Williams %R

验证新策略的正确性和表现
"""
import sys
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.strategies.lib import generate_strategy
from brain.backtest import BacktestEngine


def generate_test_data(days=300, seed=42):
    """生成测试数据"""
    np.random.seed(seed)
    dates = pd.date_range(start='2022-01-01', periods=days, freq='B')
    returns = np.random.normal(0.0003, 0.02, days)
    prices = 100 * (1 + returns).cumprod()
    
    data = []
    for i, (date, close) in enumerate(zip(dates, prices)):
        daily_range = close * 0.01
        open_price = close + np.random.normal(0, daily_range * 0.3)
        high_price = max(open_price, close) + abs(np.random.normal(0, daily_range * 0.3))
        low_price = min(open_price, close) - abs(np.random.normal(0, daily_range * 0.3))
        
        data.append({
            'datetime': date,
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close, 2),
            'volume': int(np.random.normal(1000000, 300000)),
            'pre_close': round(prices[i-1], 2) if i > 0 else round(close * 0.99, 2)
        })
    
    df = pd.DataFrame(data)
    df.set_index('datetime', inplace=True)
    return df


def test_strategy(data, strategy_name, params):
    """测试单个策略"""
    try:
        signals = generate_strategy(data, strategy_name, **params)
        
        engine = BacktestEngine(
            initial_cash=100000,
            commission_rate=0.00025,
            engine_type="ashare"
        )
        
        result = engine.run(data, signals, symbol="TEST")
        
        return {
            'success': True,
            'return_pct': result['return_pct'],
            'max_drawdown': result['max_drawdown'],
            'win_rate': result['win_rate'],
            'total_trades': result['total_trades'],
            'signals_count': (signals != 0).sum()
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def main():
    print("=" * 100)
    print("🆕 D. 新策略测试 - KDJ, CCI, Williams %R")
    print("=" * 100)
    
    # 生成数据
    print("\n📊 生成测试数据...")
    data = generate_test_data(days=300)
    print(f"   数据条数: {len(data)}")
    
    # 定义新策略
    new_strategies = [
        ('kdj', {'n': 9, 'm1': 3, 'm2': 3}, 'KDJ随机指标'),
        ('cci', {'period': 20, 'upper': 100, 'lower': -100}, 'CCI商品通道'),
        ('williams_r', {'period': 14, 'upper': -20, 'lower': -80}, 'Williams %R'),
    ]
    
    print("\n🧪 测试新策略...")
    print("-" * 100)
    
    results = []
    
    for strategy_name, params, chinese_name in new_strategies:
        print(f"\n📈 测试 {strategy_name} ({chinese_name})...")
        print(f"   参数: {params}")
        
        result = test_strategy(data, strategy_name, params)
        
        if result['success']:
            print(f"   ✅ 回测成功")
            print(f"   信号数量: {result['signals_count']}")
            print(f"   收益率: {result['return_pct']:+.2f}%")
            print(f"   最大回撤: {result['max_drawdown']:.2f}%")
            print(f"   胜率: {result['win_rate']:.1f}%")
            print(f"   交易次数: {result['total_trades']}")
            
            results.append({
                'name': strategy_name,
                'chinese_name': chinese_name,
                'params': params,
                **result
            })
        else:
            print(f"   ❌ 测试失败: {result['error']}")
    
    # 对比旧策略
    print("\n" + "=" * 100)
    print("📊 新旧策略对比")
    print("=" * 100)
    
    old_strategies = [
        ('bollinger', {'period': 15, 'std_dev': 2.5}, '布林带'),
        ('atr_breakout', {'period': 14, 'multiplier': 2.0}, 'ATR突破'),
        ('rsi', {'period': 14, 'overbought': 70, 'oversold': 30}, 'RSI'),
    ]
    
    all_results = []
    
    for strategy_name, params, chinese_name in old_strategies:
        result = test_strategy(data, strategy_name, params)
        if result['success']:
            all_results.append({
                'name': strategy_name,
                'chinese_name': chinese_name,
                'type': '旧策略',
                **result
            })
    
    for r in results:
        all_results.append({
            'name': r['name'],
            'chinese_name': r['chinese_name'],
            'type': '新策略',
            **{k: v for k, v in r.items() if k not in ['name', 'chinese_name', 'params', 'success']}
        })
    
    # 打印对比表
    print(f"\n{'策略':<15} {'类型':<8} {'收益':<10} {'回撤':<8} {'胜率':<8} {'交易':<6}")
    print("-" * 100)
    
    # 按收益排序
    all_results.sort(key=lambda x: x['return_pct'], reverse=True)
    
    for r in all_results:
        print(f"{r['chinese_name']:<15} {r['type']:<8} {r['return_pct']:>+7.2f}% {r['max_drawdown']:>6.2f}% {r['win_rate']:>6.1f}% {r['total_trades']:>4}")
    
    print("-" * 100)
    
    # 新策略总结
    print("\n📝 新策略总结")
    print("-" * 100)
    
    print("""
    ✅ KDJ (随机指标)
       • 逻辑: K线上穿D线买入，下穿卖出
       • 参数: n=9, m1=3, m2=3 (标准参数)
       • 特点: 对价格变化敏感，适合短线
       
    ✅ CCI (商品通道指数)
       • 逻辑: CCI < -100 超卖买入，> +100 超买卖出
       • 参数: period=20, upper=100, lower=-100
       • 特点: 衡量价格偏离程度
       
    ✅ Williams %R (威廉指标)
       • 逻辑: %R < -80 超卖买入，> -20 超买卖出
       • 参数: period=14, upper=-20, lower=-80
       • 特点: 与RSI类似但计算方式不同
    """)
    
    # 策略库现在包含
    print("\n📚 当前策略库 (12大策略)")
    print("-" * 100)
    
    all_strategy_names = [
        ('dual_ma', '双均线'),
        ('macd', 'MACD'),
        ('rsi', 'RSI'),
        ('bollinger', '布林带'),
        ('momentum', '动量'),
        ('atr_breakout', 'ATR突破'),
        ('donchian', '唐奇安通道'),
        ('volume_price', '量价趋势'),
        ('kdj', 'KDJ (NEW)'),
        ('cci', 'CCI (NEW)'),
        ('williams_r', 'Williams %R (NEW)'),
        ('supertrend', '超级趋势'),
    ]
    
    for i, (name, chinese) in enumerate(all_strategy_names, 1):
        is_new = "NEW" in chinese
        marker = "🆕" if is_new else "  "
        print(f"   {marker} {i:2d}. {name:<15} ({chinese.replace(' (NEW)', '')})")
    
    print("\n" + "=" * 100)
    print("✅ 新策略添加完成！")
    print("=" * 100)


if __name__ == "__main__":
    main()
