#!/usr/bin/env python3
"""
自适应策略回测

对比:
1. 买入持有 (Buy & Hold)
2. 固定策略 (Fixed Strategy)
3. 自适应单策略 (Adaptive Single)
4. 多策略组合 (Multi-Regime)

使用真实市场数据进行回测
"""
import sys
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime
import json

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.backtest import BacktestEngine
from brain.adaptive_strategy import AdaptiveStrategy, MultiRegimeStrategy
from brain.strategies.lib import generate_strategy


try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False


@dataclass
class BacktestResult:
    """回测结果"""
    method: str
    return_pct: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    sharpe_ratio: float
    final_value: float


def get_data(symbol: str, start: str, end: str) -> pd.DataFrame:
    """获取数据"""
    if YFINANCE_AVAILABLE:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start, end=end)
            if not df.empty:
                df = df.rename(columns={
                    'Open': 'open', 'High': 'high', 'Low': 'low',
                    'Close': 'close', 'Volume': 'volume'
                })
                df['pre_close'] = df['close'].shift(1)
                df.loc[df.index[0], 'pre_close'] = df['open'].iloc[0]
                return df[['open', 'high', 'low', 'close', 'volume', 'pre_close']]
        except:
            pass
    
    # 模拟数据
    return generate_mock_data(symbol, start, end)


def generate_mock_data(symbol: str, start: str, end: str) -> pd.DataFrame:
    """生成模拟数据 (包含不同市场状态)"""
    dates = pd.date_range(start=start, end=end, freq='B')
    n = len(dates)
    
    np.random.seed(hash(symbol) % 2**32)
    
    # 分段模拟不同市场状态
    segment_size = n // 3
    
    # 牛市段
    bull = 100 * (1 + np.random.normal(0.001, 0.015, segment_size)).cumprod()
    # 熊市段
    bear = bull[-1] * (1 + np.random.normal(-0.001, 0.02, segment_size)).cumprod()
    # 震荡段
    range_base = bear[-1]
    range_prices = range_base + np.cumsum(np.random.normal(0, 1.0, n - 2*segment_size))
    
    prices = np.concatenate([bull, bear, range_prices])
    
    df = pd.DataFrame({
        'open': prices * 0.995,
        'high': prices * 1.015,
        'low': prices * 0.985,
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, n),
        'pre_close': np.roll(prices, 1)
    }, index=dates)
    df.loc[df.index[0], 'pre_close'] = df['open'].iloc[0]
    
    return df


def run_backtest_comparison(
    data: pd.DataFrame,
    symbol: str
) -> Dict[str, BacktestResult]:
    """
    运行多种方法的回测对比
    """
    results = {}
    
    # 1. 买入持有
    print("\n📊 方法1: 买入持有 (Buy & Hold)")
    baseline_return = (data['close'].iloc[-1] / data['close'].iloc[0] - 1) * 100
    max_dd = (data['close'] / data['close'].cummax() - 1).min() * 100
    
    results['buy_hold'] = BacktestResult(
        method='买入持有',
        return_pct=baseline_return,
        max_drawdown=max_dd,
        win_rate=100.0 if baseline_return > 0 else 0.0,
        total_trades=1,
        sharpe_ratio=abs(baseline_return / max_dd) if max_dd != 0 else 0,
        final_value=100000 * (1 + baseline_return/100)
    )
    print(f"   收益: {baseline_return:+.2f}%, 回撤: {max_dd:.2f}%")
    
    # 2. 固定策略 (使用Ichimoku作为基准策略)
    print("\n📊 方法2: 固定策略 (Ichimoku)")
    try:
        fixed_signals = generate_strategy(
            data, 'ichimoku',
            tenkan_period=9, kijun_period=26, senkou_b_period=52
        )
        
        engine = BacktestEngine(initial_cash=100000, commission_rate=0.00025)
        result = engine.run(data, fixed_signals, symbol=symbol)
        
        results['fixed'] = BacktestResult(
            method='固定策略(Ichimoku)',
            return_pct=result['return_pct'],
            max_drawdown=result['max_drawdown'],
            win_rate=result['win_rate'],
            total_trades=result['total_trades'],
            sharpe_ratio=result['return_pct'] / abs(result['max_drawdown']) if result['max_drawdown'] != 0 else 0,
            final_value=result['final_value']
        )
        print(f"   收益: {result['return_pct']:+.2f}%, 回撤: {result['max_drawdown']:.2f}%, 交易: {result['total_trades']}")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
    
    # 3. 自适应单策略
    print("\n📊 方法3: 自适应单策略 (Adaptive Single)")
    try:
        adaptive = AdaptiveStrategy(verbose=False)
        adaptive_signals = adaptive.generate_signals(data)
        
        engine = BacktestEngine(initial_cash=100000, commission_rate=0.00025)
        result = engine.run(data, adaptive_signals, symbol=symbol)
        
        results['adaptive'] = BacktestResult(
            method='自适应单策略',
            return_pct=result['return_pct'],
            max_drawdown=result['max_drawdown'],
            win_rate=result['win_rate'],
            total_trades=result['total_trades'],
            sharpe_ratio=result['return_pct'] / abs(result['max_drawdown']) if result['max_drawdown'] != 0 else 0,
            final_value=result['final_value']
        )
        print(f"   收益: {result['return_pct']:+.2f}%, 回撤: {result['max_drawdown']:.2f}%, 交易: {result['total_trades']}")
        
        # 显示状态分布
        regime_df = adaptive.get_regime_transitions(data)
        print(f"   市场状态分布:")
        for regime, count in regime_df['regime'].value_counts().items():
            pct = count / len(regime_df) * 100
            print(f"     {regime}: {count}天 ({pct:.1f}%)")
        
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. 多策略组合
    print("\n📊 方法4: 多策略组合 (Multi-Regime)")
    try:
        multi = MultiRegimeStrategy()
        multi_signals = multi.generate_signals(data)
        
        engine = BacktestEngine(initial_cash=100000, commission_rate=0.00025)
        result = engine.run(data, multi_signals, symbol=symbol)
        
        results['multi'] = BacktestResult(
            method='多策略组合',
            return_pct=result['return_pct'],
            max_drawdown=result['max_drawdown'],
            win_rate=result['win_rate'],
            total_trades=result['total_trades'],
            sharpe_ratio=result['return_pct'] / abs(result['max_drawdown']) if result['max_drawdown'] != 0 else 0,
            final_value=result['final_value']
        )
        print(f"   收益: {result['return_pct']:+.2f}%, 回撤: {result['max_drawdown']:.2f}%, 交易: {result['total_trades']}")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
    
    return results


def print_comparison(results: Dict[str, BacktestResult], baseline: float):
    """打印对比结果"""
    print("\n" + "=" * 100)
    print("📊 回测结果对比")
    print("=" * 100)
    
    print(f"\n{'方法':<20} {'收益':<12} {'回撤':<10} {'夏普':<8} {'胜率':<8} {'交易':<8} {'vs基准':<8}")
    print("-" * 100)
    
    # 按收益排序
    sorted_results = sorted(results.items(), key=lambda x: x[1].return_pct, reverse=True)
    
    for key, r in sorted_results:
        vs_baseline = r.return_pct - baseline
        vs_emoji = "✅" if vs_baseline > 0 else "❌"
        print(f"{r.method:<18} {r.return_pct:>+9.2f}% {r.max_drawdown:>7.2f}% "
              f"{r.sharpe_ratio:>6.2f} {r.win_rate:>6.1f}% {r.total_trades:>6} "
              f"{vs_emoji} {vs_baseline:>+6.2f}%")
    
    # 找出最佳方法
    best = max(results.values(), key=lambda x: x.return_pct)
    print(f"\n🏆 最佳方法: {best.method} ({best.return_pct:+.2f}%)")
    
    # 风险调整收益
    best_sharpe = max(results.values(), key=lambda x: x.sharpe_ratio)
    print(f"⚖️  最佳夏普: {best_sharpe.method} (夏普={best_sharpe.sharpe_ratio:.2f})")
    
    # 是否战胜基准
    beat_baseline = [r for r in results.values() if r.return_pct > baseline]
    if beat_baseline:
        print(f"✅ 战胜基准的方法: {len(beat_baseline)}/{len(results)}")
    else:
        print(f"❌ 没有方法战胜基准")


def run_multi_period_test():
    """
    多周期测试
    
    测试不同市场环境下的表现
    """
    print("=" * 100)
    print("🎯 自适应策略 - 多周期测试")
    print("=" * 100)
    
    # 定义测试周期
    periods = [
        # 2023-2024: 熊市
        {'name': '熊市2023-2024', 'symbol': 'ASHR', 'start': '2023-01-01', 'end': '2024-12-31'},
        # 2025: 牛市
        {'name': '牛市2025', 'symbol': 'ASHR', 'start': '2025-01-01', 'end': '2025-12-31'},
        # 2022: 震荡/下跌
        {'name': '震荡2022', 'symbol': 'SPY', 'start': '2022-01-01', 'end': '2022-12-31'},
    ]
    
    all_results = {}
    
    for period in periods:
        print(f"\n{'='*100}")
        print(f"📅 测试周期: {period['name']}")
        print(f"   标的: {period['symbol']}, 区间: {period['start']} ~ {period['end']}")
        print("="*100)
        
        data = get_data(period['symbol'], period['start'], period['end'])
        baseline = (data['close'].iloc[-1] / data['close'].iloc[0] - 1) * 100
        
        print(f"\n📈 数据概览:")
        print(f"   交易日: {len(data)}天")
        print(f"   基准收益: {baseline:+.2f}%")
        
        results = run_backtest_comparison(data, period['symbol'])
        print_comparison(results, baseline)
        
        all_results[period['name']] = {
            'baseline': baseline,
            'results': results
        }
    
    # 跨周期汇总
    print("\n" + "=" * 100)
    print("📊 跨周期汇总对比")
    print("=" * 100)
    
    print(f"\n{'周期':<15} {'基准':<12} {'固定':<12} {'自适应':<12} {'多策略':<12} {'最佳':<15}")
    print("-" * 100)
    
    for period_name, data in all_results.items():
        baseline = data['baseline']
        fixed = data['results'].get('fixed', BacktestResult('', 0, 0, 0, 0, 0, 0)).return_pct
        adaptive = data['results'].get('adaptive', BacktestResult('', 0, 0, 0, 0, 0, 0)).return_pct
        multi = data['results'].get('multi', BacktestResult('', 0, 0, 0, 0, 0, 0)).return_pct
        
        # 找出最佳
        best_method = max(data['results'].values(), key=lambda x: x.return_pct)
        
        print(f"{period_name:<13} {baseline:>+9.2f}% {fixed:>+9.2f}% {adaptive:>+9.2f}% "
              f"{multi:>+9.2f}% {best_method.method:<12}")
    
    # 统计
    print(f"\n📈 统计:")
    wins = {'fixed': 0, 'adaptive': 0, 'multi': 0}
    for period_name, data in all_results.items():
        baseline = data['baseline']
        for method in ['fixed', 'adaptive', 'multi']:
            if method in data['results']:
                if data['results'][method].return_pct > baseline:
                    wins[method] += 1
    
    print(f"   固定策略战胜基准: {wins['fixed']}/{len(all_results)}")
    print(f"   自适应战胜基准: {wins['adaptive']}/{len(all_results)}")
    print(f"   多策略战胜基准: {wins['multi']}/{len(all_results)}")


def main():
    """主函数"""
    print("=" * 100)
    print("🎯 Brain 自适应策略回测系统")
    print("=" * 100)
    
    if not YFINANCE_AVAILABLE:
        print("\n⚠️  yfinance未安装，使用模拟数据")
        print("   安装: uv add yfinance")
    
    # 运行多周期测试
    run_multi_period_test()
    
    print("\n" + "=" * 100)
    print("✅ 自适应策略回测完成!")
    print("=" * 100)


if __name__ == "__main__":
    main()
