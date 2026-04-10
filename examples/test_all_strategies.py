#!/usr/bin/env python3
"""
测试所有20个策略

验证每个策略都能正确运行并生成信号
"""
import sys
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.strategies.lib import generate_strategy, get_strategy_names
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
        
        # 统计信号
        buy_signals = (signals == 1).sum()
        sell_signals = (signals == -1).sum()
        total_signals = buy_signals + sell_signals
        
        # 回测
        engine = BacktestEngine(
            initial_cash=100000,
            commission_rate=0.00025,
            engine_type="ashare"
        )
        
        result = engine.run(data, signals, symbol="TEST")
        
        return {
            'success': True,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'total_signals': total_signals,
            'return_pct': result['return_pct'],
            'max_drawdown': result['max_drawdown'],
            'win_rate': result['win_rate'],
            'total_trades': result['total_trades'],
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def main():
    print("=" * 100)
    print("🧪 测试所有策略 (共20个)")
    print("=" * 100)
    
    # 生成数据
    print("\n📊 生成测试数据...")
    data = generate_test_data(days=300)
    print(f"   数据条数: {len(data)}")
    
    # 获取所有策略
    all_strategies = get_strategy_names()
    print(f"   策略数量: {len(all_strategies)}")
    
    # 定义策略参数
    strategy_params = {
        'dual_ma': {'fast': 5, 'slow': 20, 'ma_type': 'sma'},
        'macd': {'fast': 12, 'slow': 26, 'signal': 9},
        'rsi': {'period': 14, 'overbought': 70, 'oversold': 30},
        'bollinger': {'period': 15, 'std_dev': 2.5},
        'momentum': {'period': 20},
        'atr_breakout': {'period': 14, 'multiplier': 2.0},
        'donchian': {'period': 20},
        'volume_price': {'period': 20},
        'supertrend': {},
        'kdj': {'n': 9, 'm1': 3, 'm2': 3},
        'cci': {'period': 20, 'upper': 100, 'lower': -100},
        'williams_r': {'period': 14, 'upper': -20, 'lower': -80},
        'ichimoku': {'tenkan_period': 9, 'kijun_period': 26, 'senkou_b_period': 52},
        'parabolic_sar': {'af_start': 0.02, 'af_max': 0.20},
        'obv': {},
        'adx': {'period': 14, 'threshold': 25.0},
        'mfi': {'period': 14, 'overbought': 80, 'oversold': 20},
        'vwap': {'period': 20},
        'stochastic': {'k_period': 14, 'd_period': 3, 'overbought': 80, 'oversold': 20},
        'heikin_ashi': {},
    }
    
    # 策略中文名
    strategy_names_cn = {
        'dual_ma': '双均线',
        'macd': 'MACD',
        'rsi': 'RSI',
        'bollinger': '布林带',
        'momentum': '动量',
        'atr_breakout': 'ATR突破',
        'donchian': '唐奇安通道',
        'volume_price': '量价趋势',
        'supertrend': '超级趋势',
        'kdj': 'KDJ',
        'cci': 'CCI',
        'williams_r': 'Williams %R',
        'ichimoku': '一目均衡表',
        'parabolic_sar': '抛物线SAR',
        'obv': 'OBV能量潮',
        'adx': 'ADX趋向指数',
        'mfi': 'MFI资金流量',
        'vwap': 'VWAP',
        'stochastic': '随机震荡',
        'heikin_ashi': 'Heikin-Ashi',
    }
    
    # 测试每个策略
    print("\n🚀 开始测试所有策略...")
    print("-" * 100)
    
    results = []
    passed = 0
    failed = 0
    
    for i, strategy_name in enumerate(all_strategies, 1):
        params = strategy_params.get(strategy_name, {})
        cn_name = strategy_names_cn.get(strategy_name, strategy_name)
        
        print(f"\n{i:2d}. 测试 {strategy_name:<15} ({cn_name})")
        
        result = test_strategy(data, strategy_name, params)
        
        if result['success']:
            passed += 1
            print(f"    ✅ 通过 | 信号:{result['total_signals']:3d} | 收益:{result['return_pct']:>+7.2f}% | 胜率:{result['win_rate']:>5.1f}%")
            results.append({
                'name': strategy_name,
                'cn_name': cn_name,
                **result
            })
        else:
            failed += 1
            print(f"    ❌ 失败: {result['error']}")
    
    print("\n" + "=" * 100)
    print("📊 测试结果汇总")
    print("=" * 100)
    print(f"\n总策略数: {len(all_strategies)}")
    print(f"通过: {passed} ✅")
    print(f"失败: {failed} ❌")
    print(f"成功率: {passed/len(all_strategies)*100:.1f}%")
    
    if results:
        # 按收益排序
        results.sort(key=lambda x: x['return_pct'], reverse=True)
        
        print("\n🏆 收益排名 TOP 10:")
        print("-" * 100)
        print(f"{'排名':<4} {'策略':<15} {'中文名':<12} {'收益':<10} {'回撤':<8} {'胜率':<8} {'信号数':<6}")
        print("-" * 100)
        
        for i, r in enumerate(results[:10], 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
            print(f"{medal} {i:<2} {r['name']:<13} {r['cn_name']:<10} {r['return_pct']:>+7.2f}% {r['max_drawdown']:>6.2f}% {r['win_rate']:>6.1f}% {r['total_signals']:>4}")
        
        print("-" * 100)
        
        # 统计
        avg_return = np.mean([r['return_pct'] for r in results])
        avg_win_rate = np.mean([r['win_rate'] for r in results])
        avg_signals = np.mean([r['total_signals'] for r in results])
        
        print(f"\n📈 统计信息:")
        print(f"   平均收益: {avg_return:+.2f}%")
        print(f"   平均胜率: {avg_win_rate:.1f}%")
        print(f"   平均信号数: {avg_signals:.0f}")
    
    print("\n" + "=" * 100)
    
    if failed == 0:
        print("🎉 所有策略测试通过！")
    else:
        print(f"⚠️  有 {failed} 个策略测试失败")
    
    print("=" * 100)


if __name__ == "__main__":
    main()
