#!/usr/bin/env python3
"""
Jarvis vs Brain 策略回测对比

对比维度:
1. Jarvis风格: 无延迟、当日执行、简单手续费
2. Brain风格: 延迟1bar、A股规则(T+1/涨跌停/100股)、完整手续费
3. 性能对比: 执行速度
"""
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
import time

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.strategies.lib import generate_strategy, StrategyOptimizer
from brain.backtest import BacktestEngine


def generate_mock_data(days=500, start_price=100, trend=0.0003, volatility=0.02, seed=42):
    """生成模拟股票数据"""
    np.random.seed(seed)
    dates = pd.date_range(start='2022-01-01', periods=days, freq='B')
    
    returns = np.random.normal(trend, volatility, days)
    prices = start_price * (1 + returns).cumprod()
    
    data = []
    for i, (date, close) in enumerate(zip(dates, prices)):
        daily_range = close * volatility * 0.5
        open_price = close + np.random.normal(0, daily_range * 0.3)
        high_price = max(open_price, close) + abs(np.random.normal(0, daily_range * 0.3))
        low_price = min(open_price, close) - abs(np.random.normal(0, daily_range * 0.3))
        volume = int(np.random.normal(1000000, 300000))
        
        data.append({
            'datetime': date,
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close, 2),
            'volume': max(volume, 100000),
            'pre_close': round(prices[i-1], 2) if i > 0 else round(close * 0.99, 2)
        })
    
    df = pd.DataFrame(data)
    df.set_index('datetime', inplace=True)
    return df


def jarvis_style_backtest(data: pd.DataFrame, signals: pd.Series, 
                          initial_cash: float = 100000) -> Dict:
    """
    模拟 Jarvis 风格的回测
    - 无延迟执行（当日信号当日成交）
    - 简单手续费（固定费率）
    - 无A股规则（可做空、无涨跌停、无T+1）
    - 允许分数股
    """
    capital = initial_cash
    position = 0.0
    trades = []
    equity_curve = []
    
    commission_rate = 0.001  # 千分之一
    
    for i in range(len(data)):
        price = data['close'].iloc[i]
        signal = signals.iloc[i]
        
        # Jarvis风格: 当日执行（可能产生未来函数）
        if signal == 1 and position <= 0:  # 买入
            if position < 0:
                # 先平空
                pnl = -position * price * 0.999  # 简单手续费
                capital += pnl
                trades.append({'type': 'cover', 'price': price, 'pnl': pnl})
                position = 0
            
            # 开多
            shares = capital * 0.95 / price  # 用95%资金
            position = shares
            cost = shares * price * (1 + commission_rate)
            capital -= cost
            trades.append({'type': 'buy', 'price': price, 'shares': shares})
            
        elif signal == -1 and position >= 0:  # 卖出
            if position > 0:
                # 平多
                pnl = position * price * 0.999
                capital += pnl
                trades.append({'type': 'sell', 'price': price, 'pnl': pnl})
                position = 0
            
            # 开空（Jarvis允许做空）
            shares = capital * 0.95 / price
            position = -shares
            cost = shares * price * commission_rate
            capital -= cost
            trades.append({'type': 'short', 'price': price, 'shares': shares})
        
        # 计算权益
        equity = capital + position * price
        equity_curve.append(equity)
    
    # 强制平仓
    final_price = data['close'].iloc[-1]
    if position != 0:
        if position > 0:
            capital += position * final_price * 0.999
        else:
            capital += position * final_price * 0.999
        position = 0
    
    final_equity = capital
    
    # 计算指标
    total_return = (final_equity - initial_cash) / initial_cash * 100
    equity_series = pd.Series(equity_curve, index=data.index)
    peak = equity_series.expanding().max()
    drawdown = (equity_series - peak) / peak
    max_drawdown = drawdown.min() * 100
    
    winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
    win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
    
    return {
        'style': 'Jarvis',
        'initial': initial_cash,
        'final': final_equity,
        'return_pct': total_return,
        'max_drawdown': max_drawdown,
        'trades': len(trades),
        'win_rate': win_rate,
        'equity_curve': equity_curve
    }


def brain_style_backtest(data: pd.DataFrame, signals: pd.Series,
                         initial_cash: float = 100000) -> Dict:
    """
    Brain 风格的回测
    - 延迟1bar执行（避免未来函数）
    - A股规则（T+1、涨跌停、100股整数倍）
    - 完整手续费（佣金+印花税+过户费）
    """
    start_time = time.time()
    
    engine = BacktestEngine(
        initial_cash=initial_cash,
        commission_rate=0.00025,
        engine_type="ashare"
    )
    
    result = engine.run(data, signals, symbol="TEST")
    
    elapsed = time.time() - start_time
    
    return {
        'style': 'Brain',
        'initial': result['initial_value'],
        'final': result['final_value'],
        'return_pct': result['return_pct'],
        'max_drawdown': result['max_drawdown'],
        'trades': result['total_trades'],
        'win_rate': result['win_rate'],
        'commission': result.get('total_commission', 0),
        'time': elapsed
    }


def compare_strategy(data: pd.DataFrame, strategy_name: str, params: Dict) -> Tuple[Dict, Dict]:
    """对比单个策略的两种回测方式"""
    # 生成信号
    signals = generate_strategy(data, strategy_name, **params)
    
    # Jarvis风格
    jarvis_result = jarvis_style_backtest(data, signals)
    
    # Brain风格
    brain_result = brain_style_backtest(data, signals)
    
    return jarvis_result, brain_result


def run_comparison():
    """运行完整对比测试"""
    print("=" * 90)
    print("🆚 Jarvis vs Brain 策略回测对比")
    print("=" * 90)
    
    # 生成数据
    print("\n📊 生成测试数据...")
    data = generate_mock_data(days=500, start_price=100, trend=0.0003, volatility=0.02)
    print(f"   数据条数: {len(data)}")
    print(f"   日期范围: {data.index[0].date()} ~ {data.index[-1].date()}")
    
    # 选择要对比的策略
    test_strategies = [
        ('rsi', {'period': 14, 'overbought': 70, 'oversold': 30}),
        ('bollinger', {'period': 20, 'std_dev': 2.0}),
        ('macd', {'fast': 12, 'slow': 26, 'signal': 9}),
        ('dual_ma', {'fast': 20, 'slow': 50}),
        ('donchian', {'period': 20}),
        ('supertrend', {'period': 10, 'multiplier': 3.0}),
    ]
    
    results = []
    
    print("\n🚀 开始对比回测...")
    print("-" * 90)
    
    for strategy_name, params in test_strategies:
        print(f"\n📈 测试 {strategy_name}...")
        
        jarvis, brain = compare_strategy(data, strategy_name, params)
        
        results.append({
            'strategy': strategy_name,
            'params': params,
            'jarvis': jarvis,
            'brain': brain
        })
        
        print(f"   Jarvis: 收益 {jarvis['return_pct']:+.2f}% | 回撤 {jarvis['max_drawdown']:.2f}% | 交易 {jarvis['trades']} 笔")
        print(f"   Brain:  收益 {brain['return_pct']:+.2f}% | 回撤 {brain['max_drawdown']:.2f}% | 交易 {brain['trades']} 笔")
        print(f"   差异:   收益 {brain['return_pct'] - jarvis['return_pct']:+.2f}% | 回撤 {brain['max_drawdown'] - jarvis['max_drawdown']:+.2f}%")
    
    # 生成报告
    print("\n" + "=" * 90)
    print("📋 对比报告")
    print("=" * 90)
    
    print(f"\n{'策略':<15} {'Jarvis收益':<12} {'Brain收益':<12} {'差异':<10} {'Jarvis回撤':<12} {'Brain回撤':<12}")
    print("-" * 90)
    
    total_jarvis_return = 0
    total_brain_return = 0
    
    for r in results:
        jarvis_return = r['jarvis']['return_pct']
        brain_return = r['brain']['return_pct']
        diff = brain_return - jarvis_return
        jarvis_dd = r['jarvis']['max_drawdown']
        brain_dd = r['brain']['max_drawdown']
        
        total_jarvis_return += jarvis_return
        total_brain_return += brain_return
        
        print(f"{r['strategy']:<15} {jarvis_return:>+10.2f}% {brain_return:>+10.2f}% {diff:>+8.2f}% {jarvis_dd:>10.2f}% {brain_dd:>10.2f}%")
    
    print("-" * 90)
    avg_diff = (total_brain_return - total_jarvis_return) / len(results)
    print(f"{'平均':<15} {total_jarvis_return/len(results):>+10.2f}% {total_brain_return/len(results):>+10.2f}% {avg_diff:>+8.2f}%")
    
    # 分析结论
    print("\n" + "=" * 90)
    print("🎯 分析结论")
    print("=" * 90)
    
    print("\n1. 收益差异原因:")
    print("   • Jarvis: 当日执行，可能使用未来信息，回测虚高")
    print("   • Brain:  延迟1bar执行，更接近实盘结果")
    print(f"   • 平均差异: {avg_diff:+.2f}% (Brain {'更低' if avg_diff < 0 else '更高'})")
    
    print("\n2. 回撤对比:")
    jarvis_worse_dd = sum(1 for r in results if abs(r['jarvis']['max_drawdown']) > abs(r['brain']['max_drawdown']))
    print(f"   • Jarvis回撤更大: {jarvis_worse_dd}/{len(results)} 个策略")
    print("   • 原因: Jarvis允许做空，Brain禁止做空（A股规则）")
    
    print("\n3. 交易次数:")
    jarvis_more_trades = sum(1 for r in results if r['jarvis']['trades'] > r['brain']['trades'])
    print(f"   • Jarvis交易更多: {jarvis_more_trades}/{len(results)} 个策略")
    print("   • 原因: Jarvis允许连续信号，Brain只在穿越时交易")
    
    print("\n4. 手续费影响:")
    print("   • Jarvis: 固定千分之一")
    print("   • Brain:  万2.5佣金+万5印花税+万0.1过户费")
    print("   • Brain手续费更真实，特别是卖出时")
    
    print("\n" + "=" * 90)
    print("✅ 对比完成！")
    print("=" * 90)
    
    return results


if __name__ == "__main__":
    run_comparison()
