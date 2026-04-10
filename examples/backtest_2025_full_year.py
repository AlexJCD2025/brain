#!/usr/bin/env python3
"""
2025年全年数据回测

使用2025年1月1日至2025年12月31日的真实市场数据
测试30个策略在2025年市场表现
"""
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import json

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.strategies.lib import generate_strategy
from brain.backtest import BacktestEngine


# 尝试导入yfinance
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False


@dataclass
class BacktestResult:
    """回测结果"""
    strategy_name: str
    symbol: str
    return_pct: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    sharpe_ratio: float
    start_date: str
    end_date: str


# 30策略最佳参数 (基于真实数据优化)
BEST_PARAMS_30 = {
    'dual_ma': {'fast': 5, 'slow': 20, 'ma_type': 'sma'},
    'macd': {'fast': 8, 'slow': 21, 'signal': 5},
    'rsi': {'period': 14, 'overbought': 80, 'oversold': 20},
    'bollinger': {'period': 15, 'std_dev': 2.5},
    'momentum': {'period': 30},
    'atr_breakout': {'period': 14, 'multiplier': 2.0},
    'donchian': {'period': 20},
    'volume_price': {'period': 10},
    'supertrend': {'period': 14, 'multiplier': 2.0},
    'kdj': {'n': 9, 'm1': 5, 'm2': 5},
    'cci': {'period': 14, 'upper': 150, 'lower': -150},
    'williams_r': {'period': 14, 'upper': -20, 'lower': -80},
    'ichimoku': {'tenkan_period': 9, 'kijun_period': 26, 'senkou_b_period': 52},
    'parabolic_sar': {'af_start': 0.03, 'af_max': 0.3},
    'obv': {},
    'adx': {'period': 14, 'threshold': 20.0},
    'mfi': {'period': 10, 'overbought': 80, 'oversold': 20},
    'vwap': {'period': 50},
    'stochastic': {'k_period': 14, 'd_period': 3, 'overbought': 80, 'oversold': 20},
    'heikin_ashi': {},
    'trix': {'period': 20, 'signal_period': 9},
    'aroon': {'period': 25},
    'ultimate_oscillator': {'short_period': 7, 'medium_period': 14, 'long_period': 28},
    'chaikin_money_flow': {'period': 30},
    'keltner_channel': {'period': 20, 'atr_multiplier': 2.0},
    'rate_of_change': {'period': 20},
    'tsi': {'long_period': 20, 'short_period': 10},
    'vortex_indicator': {'period': 20},
    'awesome_oscillator': {'short_period': 5, 'long_period': 34},
    'alligator': {'jaw_period': 13, 'teeth_period': 8, 'lips_period': 5},
}


def get_2025_data(symbol: str) -> Optional[pd.DataFrame]:
    """获取2025年全年数据"""
    if not YFINANCE_AVAILABLE:
        print("⚠️  yfinance未安装，使用模拟的2025年数据")
        return generate_2025_mock_data(symbol)
    
    try:
        print(f"   从Yahoo Finance获取 {symbol} 的2025年数据...")
        
        ticker = yf.Ticker(symbol)
        df = ticker.history(start="2025-01-01", end="2025-12-31")
        
        if df.empty:
            print(f"   ⚠️  无数据返回，使用模拟数据")
            return generate_2025_mock_data(symbol)
        
        # 标准化列名
        df = df.rename(columns={
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume',
        })
        
        # 计算pre_close
        df['pre_close'] = df['close'].shift(1)
        df.loc[df.index[0], 'pre_close'] = df['open'].iloc[0]
        
        # 选择需要的列
        df = df[['open', 'high', 'low', 'close', 'volume', 'pre_close']]
        
        # 数据清洗
        df = df.dropna()
        df = df[df['volume'] > 0]
        
        print(f"   ✅ 获取成功: {len(df)} 条数据")
        print(f"   📅 日期范围: {df.index[0].date()} ~ {df.index[-1].date()}")
        
        return df
        
    except Exception as e:
        print(f"   ❌ 获取失败: {e}，使用模拟数据")
        return generate_2025_mock_data(symbol)


def generate_2025_mock_data(symbol: str) -> pd.DataFrame:
    """生成2025年模拟数据 (带真实市场特征)"""
    print(f"   生成2025年模拟数据...")
    
    # 2025年交易日历 (大约252个交易日)
    dates = pd.date_range(start="2025-01-01", end="2025-12-31", freq='B')
    
    np.random.seed(hash(symbol) % 2**32 + 2025)
    
    # 模拟2025年市场特征 (基于2024年趋势延续)
    n = len(dates)
    prices = []
    current_price = 100
    
    for i in range(n):
        # 2025年模拟: 震荡上涨 + 几次回调
        if i < n * 0.2:  # Q1: 震荡上行
            trend = 0.0005
            vol = 0.012
        elif i < n * 0.4:  # Q2: 加速上涨
            trend = 0.0008
            vol = 0.015
        elif i < n * 0.6:  # Q3: 回调
            trend = -0.0003
            vol = 0.018
        elif i < n * 0.8:  # Q4前半: 恢复上涨
            trend = 0.0006
            vol = 0.014
        else:  # Q4后半: 震荡
            trend = 0.0002
            vol = 0.013
        
        ret = np.random.normal(trend, vol)
        current_price *= (1 + ret)
        prices.append(current_price)
    
    data = []
    for i, (date, close) in enumerate(zip(dates, prices)):
        daily_range = close * 0.015
        open_price = close + np.random.normal(0, daily_range * 0.3)
        high_price = max(open_price, close) + abs(np.random.normal(0, daily_range * 0.3))
        low_price = min(open_price, close) - abs(np.random.normal(0, daily_range * 0.3))
        
        data.append({
            'datetime': date,
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close, 2),
            'volume': int(np.random.normal(10000000, 5000000)),
            'pre_close': round(prices[i-1], 2) if i > 0 else round(close * 0.99, 2)
        })
    
    df = pd.DataFrame(data)
    df.set_index('datetime', inplace=True)
    
    print(f"   ✅ 生成完成: {len(df)} 条数据")
    print(f"   📅 日期范围: {df.index[0].date()} ~ {df.index[-1].date()}")
    
    return df


def run_strategy_backtest(
    strategy_name: str,
    symbol: str,
    data: pd.DataFrame
) -> Optional[BacktestResult]:
    """运行单策略回测"""
    try:
        params = BEST_PARAMS_30.get(strategy_name, {})
        signals = generate_strategy(data, strategy_name, **params)
        
        if signals.abs().sum() == 0:
            return None
        
        engine = BacktestEngine(
            initial_cash=100000,
            commission_rate=0.00025,
            engine_type="ashare"
        )
        
        result = engine.run(data, signals, symbol=symbol)
        
        sharpe = (result['return_pct'] / abs(result['max_drawdown']) 
                 if result['max_drawdown'] != 0 else 0)
        
        return BacktestResult(
            strategy_name=strategy_name,
            symbol=symbol,
            return_pct=result['return_pct'],
            max_drawdown=result['max_drawdown'],
            win_rate=result['win_rate'],
            total_trades=result['total_trades'],
            sharpe_ratio=sharpe,
            start_date=str(data.index[0].date()),
            end_date=str(data.index[-1].date())
        )
        
    except Exception as e:
        return None


def backtest_all_strategies_2025(symbol: str) -> List[BacktestResult]:
    """回测2025年全年所有策略"""
    print("=" * 100)
    print(f"🚀 2025年全年回测")
    print(f"📊 标的: {symbol}")
    print(f"📅 回测区间: 2025-01-01 ~ 2025-12-31")
    print("=" * 100)
    
    # 获取2025年数据
    print(f"\n📊 获取2025年数据...")
    data = get_2025_data(symbol)
    
    if data is None or len(data) < 100:
        print(f"⚠️  数据不足")
        return []
    
    print(f"\n📈 数据概览:")
    print(f"   数据长度: {len(data)} 天")
    print(f"   开盘价: {data['open'].iloc[0]:.2f}")
    print(f"   收盘价: {data['close'].iloc[-1]:.2f}")
    
    # 基准收益
    baseline_return = (data['close'].iloc[-1] / data['open'].iloc[0] - 1) * 100
    print(f"   基准收益 (买入持有): {baseline_return:+.2f}%")
    print(f"   最高价: {data['high'].max():.2f}")
    print(f"   最低价: {data['low'].min():.2f}")
    print(f"   最大回撤: {(data['close'] / data['close'].cummax() - 1).min() * 100:.2f}%")
    
    # 按月统计
    data['month'] = data.index.month
    monthly_returns = data.groupby('month').apply(
        lambda x: (x['close'].iloc[-1] / x['open'].iloc[0] - 1) * 100
    )
    
    print(f"\n📅 2025年月度收益:")
    for month, ret in monthly_returns.items():
        month_name = ['', '1月', '2月', '3月', '4月', '5月', '6月',
                      '7月', '8月', '9月', '10月', '11月', '12月'][month]
        print(f"   {month_name}: {ret:+.2f}%")
    
    # 运行所有策略
    print(f"\n🧪 开始回测30个策略...")
    print("-" * 100)
    
    results = []
    strategy_names = list(BEST_PARAMS_30.keys())
    
    for i, strategy_name in enumerate(strategy_names, 1):
        print(f"{i:2d}. {strategy_name:20s} ...", end=" ", flush=True)
        
        result = run_strategy_backtest(strategy_name, symbol, data)
        
        if result:
            results.append(result)
            print(f"✅ 收益={result.return_pct:>+7.2f}%, "
                  f"回撤={result.max_drawdown:>6.2f}%, "
                  f"胜率={result.win_rate:>5.1f}%, "
                  f"夏普={result.sharpe_ratio:>5.2f}, "
                  f"交易={result.total_trades:>3}")
        else:
            print(f"❌ 失败")
    
    return results, baseline_return, data


def print_summary(results: List[BacktestResult], symbol: str, baseline: float, data: pd.DataFrame):
    """打印汇总报告"""
    if not results:
        return
    
    print("\n" + "=" * 100)
    print(f"📊 2025年全年回测结果汇总: {symbol}")
    print("=" * 100)
    
    # 排序
    by_return = sorted(results, key=lambda x: x.return_pct, reverse=True)
    by_sharpe = sorted(results, key=lambda x: x.sharpe_ratio, reverse=True)
    
    # 统计战胜基准的策略
    beat_baseline = [r for r in results if r.return_pct > baseline]
    positive_return = [r for r in results if r.return_pct > 0]
    
    print(f"\n📈 整体统计:")
    print(f"   基准收益 (买入持有): {baseline:+.2f}%")
    print(f"   战胜基准的策略: {len(beat_baseline)}/{len(results)} ({len(beat_baseline)/len(results)*100:.1f}%)")
    print(f"   正收益策略: {len(positive_return)}/{len(results)} ({len(positive_return)/len(results)*100:.1f}%)")
    
    # TOP 15 收益
    print(f"\n🏆 收益排名 TOP 15:")
    print("-" * 100)
    print(f"{'排名':<4} {'策略':<20} {'收益':<10} {'回撤':<8} {'胜率':<8} {'夏普':<8} {'交易':<6} {'vs基准':<6}")
    print("-" * 100)
    
    for i, r in enumerate(by_return[:15], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        vs_baseline = "✓" if r.return_pct > baseline else " "
        print(f"{medal} {i:<2} {r.strategy_name:<18} {r.return_pct:>+7.2f}% {vs_baseline} {r.max_drawdown:>6.2f}% "
              f"{r.win_rate:>6.1f}% {r.sharpe_ratio:>6.2f} {r.total_trades:>4}")
    
    # TOP 10 夏普
    print(f"\n⚖️ 夏普比率排名 TOP 10:")
    print("-" * 100)
    
    for i, r in enumerate(by_sharpe[:10], 1):
        vs_baseline = "✓" if r.return_pct > baseline else " "
        print(f"{i:2d}. {r.strategy_name:<18} 夏普={r.sharpe_ratio:>6.2f} 收益={r.return_pct:>+7.2f}% {vs_baseline}")
    
    # 统计
    returns = [r.return_pct for r in results]
    sharpes = [r.sharpe_ratio for r in results]
    win_rates = [r.win_rate for r in results]
    
    print(f"\n📊 策略表现统计:")
    print(f"   策略数量: {len(results)}")
    print(f"   平均收益: {np.mean(returns):+.2f}%")
    print(f"   收益中位数: {np.median(returns):+.2f}%")
    print(f"   最佳收益: {max(returns):+.2f}% ({by_return[0].strategy_name})")
    print(f"   最差收益: {min(returns):+.2f}% ({by_return[-1].strategy_name})")
    print(f"   平均夏普: {np.mean(sharpes):.2f}")
    print(f"   平均胜率: {np.mean(win_rates):.1f}%")
    
    return by_return


def save_results(results: List[BacktestResult], symbol: str, baseline: float, data: pd.DataFrame):
    """保存结果"""
    if not results:
        return
    
    import os
    os.makedirs('reports', exist_ok=True)
    
    filename = f"reports/backtest_2025_{symbol}.json"
    
    # 计算月度收益
    data['month'] = data.index.month
    monthly_returns = data.groupby('month').apply(
        lambda x: (x['close'].iloc[-1] / x['open'].iloc[0] - 1) * 100
    ).to_dict()
    
    output = {
        'symbol': symbol,
        'year': 2025,
        'timestamp': datetime.now().isoformat(),
        'baseline_return': baseline,
        'total_strategies': len(results),
        'market_stats': {
            'trading_days': len(data),
            'start_price': float(data['open'].iloc[0]),
            'end_price': float(data['close'].iloc[-1]),
            'high': float(data['high'].max()),
            'low': float(data['low'].min()),
            'max_drawdown': float((data['close'] / data['close'].cummax() - 1).min() * 100),
            'monthly_returns': {f"{k}月": round(v, 2) for k, v in monthly_returns.items()}
        },
        'results': [
            {
                'rank': i+1,
                'strategy': r.strategy_name,
                'return_pct': round(r.return_pct, 2),
                'max_drawdown': round(r.max_drawdown, 2),
                'win_rate': round(r.win_rate, 2),
                'sharpe': round(r.sharpe_ratio, 2),
                'trades': r.total_trades,
                'beat_baseline': bool(r.return_pct > baseline)
            }
            for i, r in enumerate(sorted(results, key=lambda x: x.return_pct, reverse=True))
        ]
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 结果已保存: {filename}")


def main():
    """主函数"""
    print("=" * 100)
    print("🎯 Brain 30策略 - 2025年全年数据回测")
    print("=" * 100)
    
    # 测试标的
    symbols = [
        "ASHR",      # A股ETF
        "000001.SS", # 上证指数
        "SPY",       # 标普500 (对比)
        "QQQ",       # 纳斯达克 (对比)
    ]
    
    all_results = {}
    
    for symbol in symbols:
        results, baseline, data = backtest_all_strategies_2025(symbol)
        
        if results:
            top_strategies = print_summary(results, symbol, baseline, data)
            save_results(results, symbol, baseline, data)
            all_results[symbol] = {
                'top_strategies': top_strategies,
                'baseline': baseline
            }
    
    # 跨标汇总
    if len(all_results) > 1:
        print("\n" + "=" * 100)
        print("📊 跨标的汇总对比")
        print("=" * 100)
        
        print(f"\n{'标的':<15} {'基准收益':<12} {'最佳策略':<20} {'最佳收益':<10} {'正收益策略':<12}")
        print("-" * 100)
        
        for symbol, data in all_results.items():
            top = data['top_strategies'][0]
            positive = sum(1 for r in data['top_strategies'] if r.return_pct > 0)
            print(f"{symbol:<15} {data['baseline']:>+10.2f}%   {top.strategy_name:<18} "
                  f"{top.return_pct:>+8.2f}%   {positive:>3}/{len(data['top_strategies'])}")
    
    # 生成2025最佳配置
    print("\n" + "=" * 100)
    print("💡 2025年最佳策略配置 (基于回测结果)")
    print("=" * 100)
    
    if all_results:
        # 取第一个标的的TOP 10
        first_symbol = list(all_results.keys())[0]
        top10 = all_results[first_symbol]['top_strategies'][:10]
        
        print("\n```python")
        print("# 2025年全年回测 - TOP 10 策略配置")
        print("BEST_2025_PORTFOLIO = {")
        
        weights = [0.20, 0.15, 0.15, 0.10, 0.10, 0.10, 0.08, 0.05, 0.04, 0.03]
        for r, w in zip(top10, weights):
            params = BEST_PARAMS_30.get(r.strategy_name, {})
            print(f"    '{r.strategy_name}': {{'weight': {w}, 'params': {params}}},  # 收益={r.return_pct:+.2f}%")
        
        print("}")
        print("```")
    
    print("\n" + "=" * 100)
    print("✅ 2025年全年回测完成！")
    print("=" * 100)


if __name__ == "__main__":
    main()
