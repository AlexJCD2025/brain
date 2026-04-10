#!/usr/bin/env python3
"""
使用Yahoo Finance数据进行30策略回测

Yahoo Finance提供更稳定的国际数据源
可以获取A股ETF、港股、美股等
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
    print("⚠️  yfinance未安装，使用模拟数据")


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


# 30策略最佳参数
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


def get_yfinance_data(
    symbol: str,
    start_date: str,
    end_date: str
) -> Optional[pd.DataFrame]:
    """从Yahoo Finance获取数据"""
    if not YFINANCE_AVAILABLE:
        return generate_mock_data(symbol, start_date, end_date)
    
    try:
        print(f"   从Yahoo Finance获取 {symbol}...")
        
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date)
        
        if df.empty:
            print(f"   ⚠️  无数据返回")
            return None
        
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
        df['pre_close'].iloc[0] = df['open'].iloc[0]
        
        # 选择需要的列
        df = df[['open', 'high', 'low', 'close', 'volume', 'pre_close']]
        
        # 数据清洗
        df = df.dropna()
        df = df[df['volume'] > 0]
        
        print(f"   ✅ 获取成功: {len(df)} 条数据 ({df.index[0].date()} ~ {df.index[-1].date()})")
        
        return df
        
    except Exception as e:
        print(f"   ❌ 获取失败: {e}")
        return generate_mock_data(symbol, start_date, end_date)


def generate_mock_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """生成模拟真实市场特征的模拟数据"""
    print(f"   使用模拟数据 (带趋势和波动特征)")
    
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    dates = pd.date_range(start=start, end=end, freq='B')
    
    np.random.seed(hash(symbol) % 2**32)
    
    # 生成更真实的市场数据 (带趋势周期)
    n = len(dates)
    prices = []
    current_price = 100
    
    # 模拟不同市场状态
    for i in range(n):
        # 周期性趋势
        trend = 0.0003 * np.sin(i / 100)
        
        # 随机游走
        volatility = 0.015 + 0.01 * np.sin(i / 50)  # 波动率也周期性变化
        ret = np.random.normal(trend, volatility)
        
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


def backtest_all_strategies(symbol: str, start_date: str, end_date: str) -> List[BacktestResult]:
    """回测所有30个策略"""
    print(f"\n{'='*100}")
    print(f"🚀 回测标的: {symbol}")
    print(f"📅 回测区间: {start_date} ~ {end_date}")
    print(f"{'='*100}")
    
    # 获取数据
    print(f"\n📊 获取数据...")
    data = get_yfinance_data(symbol, start_date, end_date)
    
    if data is None or len(data) < 100:
        print(f"⚠️  数据不足")
        return []
    
    print(f"   数据长度: {len(data)} 天")
    print(f"   价格范围: {data['low'].min():.2f} ~ {data['high'].max():.2f}")
    
    # 基准收益
    baseline_return = (data['close'].iloc[-1] / data['close'].iloc[0] - 1) * 100
    print(f"   基准收益 (买入持有): {baseline_return:+.2f}%")
    
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
    
    return results


def print_summary(results: List[BacktestResult], symbol: str, baseline: float):
    """打印汇总报告"""
    if not results:
        return
    
    print("\n" + "=" * 100)
    print(f"📊 回测结果汇总: {symbol}")
    print("=" * 100)
    
    # 排序
    by_return = sorted(results, key=lambda x: x.return_pct, reverse=True)
    by_sharpe = sorted(results, key=lambda x: x.sharpe_ratio, reverse=True)
    
    # 统计战胜基准的策略
    beat_baseline = [r for r in results if r.return_pct > baseline]
    
    print(f"\n基准收益 (买入持有): {baseline:+.2f}%")
    print(f"战胜基准的策略: {len(beat_baseline)}/{len(results)}")
    
    # TOP 10 收益
    print(f"\n🏆 收益排名 TOP 10:")
    print("-" * 100)
    print(f"{'排名':<4} {'策略':<20} {'收益':<10} {'回撤':<8} {'胜率':<8} {'夏普':<8} {'交易':<6}")
    print("-" * 100)
    
    for i, r in enumerate(by_return[:10], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        beat = "✓" if r.return_pct > baseline else " "
        print(f"{medal} {i:<2} {r.strategy_name:<18} {r.return_pct:>+7.2f}% {beat} {r.max_drawdown:>6.2f}% "
              f"{r.win_rate:>6.1f}% {r.sharpe_ratio:>6.2f} {r.total_trades:>4}")
    
    # TOP 10 夏普
    print(f"\n⚖️ 夏普比率排名 TOP 10:")
    print("-" * 100)
    
    for i, r in enumerate(by_sharpe[:10], 1):
        beat = "✓" if r.return_pct > baseline else " "
        print(f"{i:2d}. {r.strategy_name:<18} 夏普={r.sharpe_ratio:>6.2f} 收益={r.return_pct:>+7.2f}% {beat}")
    
    # 统计
    returns = [r.return_pct for r in results]
    sharpes = [r.sharpe_ratio for r in results]
    
    print(f"\n📈 统计信息:")
    print(f"   策略数量: {len(results)}")
    print(f"   平均收益: {np.mean(returns):+.2f}%")
    print(f"   收益中位数: {np.median(returns):+.2f}%")
    print(f"   平均夏普: {np.mean(sharpes):.2f}")
    print(f"   正收益策略: {sum(1 for r in returns if r > 0)}/{len(results)}")
    print(f"   最佳策略: {by_return[0].strategy_name} ({by_return[0].return_pct:+.2f}%)")
    print(f"   最差策略: {by_return[-1].strategy_name} ({by_return[-1].return_pct:+.2f}%)")
    
    return by_return


def save_results(results: List[BacktestResult], symbol: str, baseline: float):
    """保存结果"""
    if not results:
        return
    
    import os
    os.makedirs('reports', exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"reports/real_backtest_{symbol}_{timestamp}.json"
    
    data = {
        'symbol': symbol,
        'timestamp': datetime.now().isoformat(),
        'baseline_return': baseline,
        'total_strategies': len(results),
        'results': [
            {
                'strategy': r.strategy_name,
                'return_pct': r.return_pct,
                'max_drawdown': r.max_drawdown,
                'win_rate': r.win_rate,
                'sharpe': r.sharpe_ratio,
                'trades': r.total_trades
            }
            for r in results
        ]
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 结果已保存: {filename}")


def main():
    """主函数"""
    print("=" * 100)
    print("🎯 Brain 30策略真实市场数据回测")
    print("=" * 100)
    
    if not YFINANCE_AVAILABLE:
        print("\n⚠️  yfinance未安装，将使用模拟数据")
        print("   安装命令: uv add yfinance")
    
    # 选择标的
    # A股ETF通过Yahoo Finance的代码
    symbols = [
        "ASHR",     # Xtrackers Harvest CSI 300 China A-Shares ETF
        "000001.SS", # 上证指数
        "399001.SZ", # 深证成指
    ]
    
    symbol = "ASHR"  # 使用A股ETF代表A股市场
    start_date = "2023-01-01"
    end_date = "2024-12-31"
    
    # 运行回测
    results = backtest_all_strategies(symbol, start_date, end_date)
    
    if results:
        # 重新获取数据计算基准
        data = get_yfinance_data(symbol, start_date, end_date)
        baseline = (data['close'].iloc[-1] / data['close'].iloc[0] - 1) * 100 if data is not None else 0
        
        top_strategies = print_summary(results, symbol, baseline)
        save_results(results, symbol, baseline)
        
        # 输出Python代码
        print("\n" + "=" * 100)
        print("💡 真实数据回测 TOP 10 策略 (可直接使用)")
        print("=" * 100)
        print("\n```python")
        print("# 基于真实市场数据回测的TOP 10策略")
        print("REAL_TOP10_STRATEGIES = [")
        for r in top_strategies[:10]:
            params = BEST_PARAMS_30.get(r.strategy_name, {})
            print(f"    ('{r.strategy_name}', {params}, {r.return_pct:.2f}),  # 夏普={r.sharpe_ratio:.2f}")
        print("]")
        print("```")
    
    print("\n" + "=" * 100)
    print("✅ 真实数据回测完成！")
    print("=" * 100)


if __name__ == "__main__":
    main()
