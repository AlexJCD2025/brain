#!/usr/bin/env python3
"""
自适应策略 V2 vs V1 对比回测

对比改进效果:
1. V1: 基础自适应
2. V2: 改进版 (多维度检测 + 渐进式仓位)
3. V2-Multi: 多时间框架确认
"""
import sys
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.backtest import BacktestEngine
from brain.adaptive_strategy import AdaptiveStrategy, MultiRegimeStrategy
from brain.adaptive_strategy_v2 import AdaptiveStrategyV2, MultiTimeframeStrategy


try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False


@dataclass
class BacktestResult:
    method: str
    return_pct: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    sharpe_ratio: float
    avg_position: float
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
    
    return generate_mock_data(symbol, start, end)


def generate_mock_data(symbol: str, start: str, end: str) -> pd.DataFrame:
    """生成包含不同状态的模拟数据"""
    dates = pd.date_range(start=start, end=end, freq='B')
    n = len(dates)
    
    np.random.seed(hash(symbol) % 2**32)
    
    # 分段模拟不同市场状态
    third = n // 3
    
    bull = 100 * (1 + np.random.normal(0.0015, 0.012, third)).cumprod()
    bear = bull[-1] * (1 + np.random.normal(-0.001, 0.018, third)).cumprod()
    range_prices = bear[-1] + np.cumsum(np.random.normal(0, 0.8, n - 2*third))
    
    prices = np.concatenate([bull, bear, range_prices])
    
    df = pd.DataFrame({
        'open': prices * 0.995,
        'high': prices * 1.015,
        'low': prices * 0.985,
        'close': prices,
        'volume': np.random.normal(10000000, 2000000, n)
    }, index=dates)
    df['pre_close'] = np.roll(prices, 1)
    df.loc[df.index[0], 'pre_close'] = df['open'].iloc[0]
    
    return df


def run_comparison_backtest(data: pd.DataFrame, symbol: str) -> Dict[str, BacktestResult]:
    """运行对比回测"""
    results = {}
    
    # 1. 买入持有 (基准)
    print("\n📊 买入持有 (基准)")
    baseline_return = (data['close'].iloc[-1] / data['close'].iloc[0] - 1) * 100
    max_dd = (data['close'] / data['close'].cummax() - 1).min() * 100
    
    results['buy_hold'] = BacktestResult(
        method='买入持有',
        return_pct=baseline_return,
        max_drawdown=max_dd,
        win_rate=100.0 if baseline_return > 0 else 0.0,
        total_trades=1,
        sharpe_ratio=abs(baseline_return / max_dd) if max_dd != 0 else 0,
        avg_position=1.0,
        final_value=100000 * (1 + baseline_return/100)
    )
    print(f"   收益: {baseline_return:+.2f}%, 回撤: {max_dd:.2f}%")
    
    # 2. V1 自适应策略
    print("\n📊 V1 自适应策略 (基础版)")
    try:
        adaptive_v1 = AdaptiveStrategy(verbose=False)
        signals_v1 = adaptive_v1.generate_signals(data)
        
        engine = BacktestEngine(initial_cash=100000, commission_rate=0.00025)
        result = engine.run(data, signals_v1, symbol=symbol)
        
        results['adaptive_v1'] = BacktestResult(
            method='V1 自适应(基础)',
            return_pct=result['return_pct'],
            max_drawdown=result['max_drawdown'],
            win_rate=result['win_rate'],
            total_trades=result['total_trades'],
            sharpe_ratio=result['return_pct'] / abs(result['max_drawdown']) if result['max_drawdown'] != 0 else 0,
            avg_position=signals_v1.abs().mean(),
            final_value=result['final_value']
        )
        print(f"   收益: {result['return_pct']:+.2f}%, 回撤: {result['max_drawdown']:.2f}%, "
              f"平均持仓: {signals_v1.abs().mean():.1%}")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
    
    # 3. V2 自适应策略 (改进版)
    print("\n📊 V2 自适应策略 (改进版)")
    try:
        adaptive_v2 = AdaptiveStrategyV2(verbose=False)
        signals_v2 = adaptive_v2.generate_signals(data)
        
        engine = BacktestEngine(initial_cash=100000, commission_rate=0.00025)
        result = engine.run(data, signals_v2, symbol=symbol)
        
        results['adaptive_v2'] = BacktestResult(
            method='V2 自适应(改进)',
            return_pct=result['return_pct'],
            max_drawdown=result['max_drawdown'],
            win_rate=result['win_rate'],
            total_trades=result['total_trades'],
            sharpe_ratio=result['return_pct'] / abs(result['max_drawdown']) if result['max_drawdown'] != 0 else 0,
            avg_position=signals_v2.abs().mean(),
            final_value=result['final_value']
        )
        print(f"   收益: {result['return_pct']:+.2f}%, 回撤: {result['max_drawdown']:.2f}%, "
              f"平均持仓: {signals_v2.abs().mean():.1%}")
        
        # V2分析报告
        report = adaptive_v2.generate_report(data)
        print(f"   V2状态分布:")
        for regime, stats in list(report['regime_distribution'].items())[:5]:
            print(f"     {regime}: {stats['percentage']}")
        
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. V2 多时间框架
    print("\n📊 V2 多时间框架策略")
    try:
        multi_tf = MultiTimeframeStrategy()
        signals_multi = multi_tf.generate_signals(data)
        
        engine = BacktestEngine(initial_cash=100000, commission_rate=0.00025)
        result = engine.run(data, signals_multi, symbol=symbol)
        
        results['multi_tf'] = BacktestResult(
            method='V2 多时间框架',
            return_pct=result['return_pct'],
            max_drawdown=result['max_drawdown'],
            win_rate=result['win_rate'],
            total_trades=result['total_trades'],
            sharpe_ratio=result['return_pct'] / abs(result['max_drawdown']) if result['max_drawdown'] != 0 else 0,
            avg_position=signals_multi.abs().mean(),
            final_value=result['final_value']
        )
        print(f"   收益: {result['return_pct']:+.2f}%, 回撤: {result['max_drawdown']:.2f}%, "
              f"平均持仓: {signals_multi.abs().mean():.1%}")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
    
    return results


def print_comparison(results: Dict[str, BacktestResult], baseline: float):
    """打印对比结果"""
    print("\n" + "=" * 100)
    print("📊 对比结果")
    print("=" * 100)
    
    print(f"\n{'方法':<20} {'收益':<10} {'回撤':<8} {'夏普':<8} {'持仓':<8} {'交易':<8} {'vs基准':<8}")
    print("-" * 100)
    
    sorted_results = sorted(results.items(), key=lambda x: x[1].return_pct, reverse=True)
    
    for key, r in sorted_results:
        vs_baseline = r.return_pct - baseline
        emoji = "✅" if vs_baseline > 0 else "❌"
        print(f"{r.method:<18} {r.return_pct:>+7.2f}% {r.max_drawdown:>6.2f}% "
              f"{r.sharpe_ratio:>6.2f} {r.avg_position:>6.1%} {r.total_trades:>6} "
              f"{emoji} {vs_baseline:>+6.2f}%")
    
    # 找出最佳
    best_return = max(results.values(), key=lambda x: x.return_pct)
    best_sharpe = max(results.values(), key=lambda x: x.sharpe_ratio)
    
    print(f"\n🏆 最佳收益: {best_return.method} ({best_return.return_pct:+.2f}%)")
    print(f"⚖️  最佳夏普: {best_sharpe.method} (夏普={best_sharpe.sharpe_ratio:.2f})")
    
    # 对比V1 vs V2
    if 'adaptive_v1' in results and 'adaptive_v2' in results:
        v1 = results['adaptive_v1']
        v2 = results['adaptive_v2']
        print(f"\n📈 V1 vs V2 对比:")
        print(f"   收益改进: {v2.return_pct - v1.return_pct:+.2f}%")
        print(f"   回撤控制: V1={v1.max_drawdown:.2f}%, V2={v2.max_drawdown:.2f}%")
        print(f"   夏普改进: {v2.sharpe_ratio - v1.sharpe_ratio:+.2f}")
        print(f"   平均持仓: V1={v1.avg_position:.1%}, V2={v2.avg_position:.1%}")


def run_multi_period_comparison():
    """多周期对比测试"""
    print("=" * 100)
    print("🎯 自适应策略 V2 改进版 - 多周期对比")
    print("=" * 100)
    
    periods = [
        {'name': '熊市2023-2024', 'symbol': 'ASHR', 'start': '2023-01-01', 'end': '2024-12-31'},
        {'name': '牛市2025', 'symbol': 'ASHR', 'start': '2025-01-01', 'end': '2025-12-31'},
        {'name': '震荡2022', 'symbol': 'SPY', 'start': '2022-01-01', 'end': '2022-12-31'},
    ]
    
    all_results = {}
    
    for period in periods:
        print(f"\n{'='*100}")
        print(f"📅 {period['name']}")
        print(f"   {period['symbol']} | {period['start']} ~ {period['end']}")
        print("="*100)
        
        data = get_data(period['symbol'], period['start'], period['end'])
        baseline = (data['close'].iloc[-1] / data['close'].iloc[0] - 1) * 100
        
        print(f"\n📈 数据概览:")
        print(f"   交易日: {len(data)}天")
        print(f"   基准收益: {baseline:+.2f}%")
        
        results = run_comparison_backtest(data, period['symbol'])
        print_comparison(results, baseline)
        
        all_results[period['name']] = {
            'baseline': baseline,
            'results': results
        }
    
    # 跨周期汇总
    print("\n" + "=" * 100)
    print("📊 跨周期汇总对比")
    print("=" * 100)
    
    print(f"\n{'周期':<15} {'基准':<10} {'V1':<10} {'V2':<10} {'V2-Multi':<10} {'最佳':<15}")
    print("-" * 100)
    
    v1_wins = 0
    v2_wins = 0
    
    for period_name, data in all_results.items():
        baseline = data['baseline']
        
        v1_ret = data['results'].get('adaptive_v1', BacktestResult('', 0, 0, 0, 0, 0, 0, 0)).return_pct
        v2_ret = data['results'].get('adaptive_v2', BacktestResult('', 0, 0, 0, 0, 0, 0, 0)).return_pct
        multi_ret = data['results'].get('multi_tf', BacktestResult('', 0, 0, 0, 0, 0, 0, 0)).return_pct
        
        best = max(data['results'].values(), key=lambda x: x.return_pct)
        
        print(f"{period_name:<13} {baseline:>+7.2f}% {v1_ret:>+7.2f}% {v2_ret:>+7.2f}% "
              f"{multi_ret:>+7.2f}% {best.method:<12}")
        
        # 统计
        if v2_ret > v1_ret:
            v2_wins += 1
        elif v1_ret > v2_ret:
            v1_wins += 1
    
    print(f"\n📈 V1 vs V2 胜率:")
    print(f"   V1 获胜: {v1_wins}/{len(all_results)}")
    print(f"   V2 获胜: {v2_wins}/{len(all_results)}")
    
    if v2_wins > v1_wins:
        print(f"   ✅ V2 改进有效!")
    elif v1_wins > v2_wins:
        print(f"   ⚠️  V2 需要进一步优化")
    else:
        print(f"   ⚖️  各有千秋")


def main():
    print("=" * 100)
    print("🎯 Brain 自适应策略 V2 改进版对比测试")
    print("=" * 100)
    print("\n改进点:")
    print("   1. ✅ 增强牛市识别 (多维度确认)")
    print("   2. ✅ 多时间框架确认 (短/中/长期)")
    print("   3. ✅ 渐进式仓位管理 (20%-100%)")
    
    run_multi_period_comparison()
    
    print("\n" + "=" * 100)
    print("✅ V2 对比测试完成!")
    print("=" * 100)


if __name__ == "__main__":
    main()
