#!/usr/bin/env python3
"""
Bollinger Bands 策略参数优化
使用网格搜索找出最佳参数组合

优化维度:
- period: 均线周期 (10, 15, 20, 25, 30)
- std_dev: 标准差倍数 (1.5, 2.0, 2.5, 3.0)
- 卖出逻辑: 上轨卖出 vs 中轨卖出 vs 百分比止盈
"""
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.backtest import BacktestEngine


@dataclass
class BollingerResult:
    """Bollinger策略回测结果"""
    period: int
    std_dev: float
    exit_logic: str  # 'upper', 'middle', 'percent'
    return_pct: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    profit_loss_ratio: float
    score: float


def generate_mock_data(days=500, seed=42):
    """生成模拟数据"""
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


def generate_bollinger_signals(data: pd.DataFrame, period: int = 20, 
                                std_dev: float = 2.0, exit_logic: str = 'upper') -> pd.Series:
    """
    生成布林带策略信号
    
    Args:
        data: OHLCV DataFrame
        period: 均线周期
        std_dev: 标准差倍数
        exit_logic: 卖出逻辑 ('upper'=上轨, 'middle'=中轨, 'percent'=百分比止盈)
    """
    close = data['close']
    
    # 计算布林带
    ma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = ma + std_dev * std
    lower = ma - std_dev * std
    
    signals = pd.Series(0, index=data.index)
    
    # 买入信号: 触及下轨
    buy_signal = (close < lower) & (close.shift(1) >= lower.shift(1))
    signals[buy_signal] = 1
    
    # 卖出信号根据逻辑不同
    if exit_logic == 'upper':
        # 触及上轨卖出
        sell_signal = (close > upper) & (close.shift(1) <= upper.shift(1))
    elif exit_logic == 'middle':
        # 触及中轨卖出
        sell_signal = (close > ma) & (close.shift(1) <= ma.shift(1))
    elif exit_logic == 'percent':
        # 5%止盈卖出 (简化实现，用上轨近似)
        sell_signal = (close > upper * 0.95) & (close.shift(1) <= upper.shift(1) * 0.95)
    else:
        sell_signal = pd.Series(False, index=data.index)
    
    signals[sell_signal] = -1
    
    return signals


def calculate_score(return_pct: float, max_drawdown: float, 
                   win_rate: float, trades: int) -> float:
    """计算综合得分"""
    # 避免除零
    if max_drawdown == 0:
        max_drawdown = -0.01
    
    # 夏普近似
    sharpe_like = return_pct / abs(max_drawdown) if max_drawdown != 0 else 0
    
    # 交易次数惩罚 (避免过度交易)
    trade_penalty = min(trades / 50, 1.0) * 5  # 超过50次开始扣分
    
    score = (
        return_pct * 0.4 +
        sharpe_like * 0.3 +
        win_rate * 0.2 +
        (100 - trade_penalty) * 0.1
    )
    
    return score


def run_single_test(data: pd.DataFrame, period: int, std_dev: float, 
                   exit_logic: str) -> BollingerResult:
    """运行单组参数测试"""
    signals = generate_bollinger_signals(data, period, std_dev, exit_logic)
    
    engine = BacktestEngine(
        initial_cash=100000,
        commission_rate=0.00025,
        engine_type="ashare"
    )
    
    result = engine.run(data, signals, symbol="TEST")
    
    score = calculate_score(
        result['return_pct'],
        result['max_drawdown'],
        result['win_rate'],
        result['total_trades']
    )
    
    return BollingerResult(
        period=period,
        std_dev=std_dev,
        exit_logic=exit_logic,
        return_pct=result['return_pct'],
        max_drawdown=result['max_drawdown'],
        win_rate=result['win_rate'],
        total_trades=result['total_trades'],
        profit_loss_ratio=result.get('profit_loss_ratio', 0),
        score=score
    )


def grid_search(data: pd.DataFrame) -> List[BollingerResult]:
    """网格搜索最佳参数"""
    print("\n🔍 开始网格搜索...")
    print("-" * 90)
    
    # 参数网格
    periods = [10, 15, 20, 25, 30]
    std_devs = [1.5, 2.0, 2.5, 3.0]
    exit_logics = ['upper', 'middle', 'percent']
    
    results = []
    total = len(periods) * len(std_devs) * len(exit_logics)
    current = 0
    
    for period in periods:
        for std_dev in std_devs:
            for exit_logic in exit_logics:
                current += 1
                print(f"\r[{current}/{total}] 测试 period={period}, std_dev={std_dev}, exit={exit_logic}...", end="")
                
                result = run_single_test(data, period, std_dev, exit_logic)
                results.append(result)
    
    print("\n✅ 网格搜索完成！")
    return results


def print_results(results: List[BollingerResult], top_n: int = 10):
    """打印回测结果"""
    # 按得分排序
    sorted_results = sorted(results, key=lambda x: x.score, reverse=True)
    
    print("\n" + "=" * 90)
    print("📊 Bollinger 策略参数优化结果")
    print("=" * 90)
    
    print(f"\n🏆 Top {top_n} 参数组合:")
    print("-" * 90)
    print(f"{'排名':<4} {'周期':<6} {'倍数':<6} {'卖出':<8} {'收益':<10} {'回撤':<8} {'胜率':<8} {'交易':<6} {'得分':<8}")
    print("-" * 90)
    
    for i, r in enumerate(sorted_results[:top_n], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        print(f"{medal} {i:<2} {r.period:<4} {r.std_dev:<4.1f} {r.exit_logic:<8} "
              f"{r.return_pct:>+7.2f}% {r.max_drawdown:>6.2f}% {r.win_rate:>6.1f}% {r.total_trades:>4} {r.score:>7.2f}")
    
    print("-" * 90)
    
    # 按卖出逻辑分组统计
    print("\n📈 按卖出逻辑分组统计:")
    print("-" * 90)
    
    by_exit = {}
    for r in results:
        if r.exit_logic not in by_exit:
            by_exit[r.exit_logic] = []
        by_exit[r.exit_logic].append(r)
    
    for exit_logic, group in sorted(by_exit.items(), key=lambda x: np.mean([r.return_pct for r in x[1]]), reverse=True):
        returns = [r.return_pct for r in group]
        avg_return = np.mean(returns)
        best_return = max(returns)
        avg_score = np.mean([r.score for r in group])
        
        print(f"\n卖出逻辑: {exit_logic}")
        print(f"  平均收益: {avg_return:+.2f}%")
        print(f"  最佳收益: {best_return:+.2f}%")
        print(f"  平均得分: {avg_score:.2f}")
        
        # 该组最佳
        best = max(group, key=lambda x: x.score)
        print(f"  推荐参数: period={best.period}, std_dev={best.std_dev}")
    
    print("\n" + "-" * 90)


def print_heatmap(results: List[BollingerResult]):
    """打印收益热力图"""
    print("\n🌡️  收益热力图 (按 period x std_dev)")
    print("-" * 90)
    
    # 按卖出逻辑分组
    for exit_logic in ['upper', 'middle', 'percent']:
        print(f"\n卖出逻辑: {exit_logic}")
        print(f"{'周期':<6} | {'1.5':<8} {'2.0':<8} {'2.5':<8} {'3.0':<8}")
        print("-" * 50)
        
        for period in [10, 15, 20, 25, 30]:
            row = f"{period:<6} |"
            for std_dev in [1.5, 2.0, 2.5, 3.0]:
                # 找对应结果
                result = next((r for r in results 
                              if r.period == period and r.std_dev == std_dev 
                              and r.exit_logic == exit_logic), None)
                if result:
                    emoji = "🟢" if result.return_pct > 0 else "🔴"
                    row += f" {emoji} {result.return_pct:>+5.1f}%"
                else:
                    row += f" {'N/A':<8}"
            print(row)


def generate_best_strategy_code(best_result: BollingerResult):
    """生成最佳策略代码"""
    code = f'''
# ============================================================
# Bollinger Bands 最佳参数策略
# 优化结果: period={best_result.period}, std_dev={best_result.std_dev}, exit_logic='{best_result.exit_logic}'
# 回测表现: 收益 {best_result.return_pct:+.2f}%, 回撤 {best_result.max_drawdown:.2f}%, 胜率 {best_result.win_rate:.1f}%
# ============================================================

from brain.strategies.lib import generate_strategy
from brain.backtest import BacktestEngine
import pandas as pd

# 加载数据
data = pd.read_csv('your_data.csv', index_col='date', parse_dates=True)

# 生成信号 (最佳参数)
signals = generate_strategy(
    data=data,
    strategy_name="bollinger",
    period={best_result.period},
    std_dev={best_result.std_dev}
)

# 运行回测
engine = BacktestEngine(
    initial_cash=100000,
    commission_rate=0.00025,
    engine_type="ashare"
)

result = engine.run(data, signals, symbol="000001")

print(f"收益率: {{result['return_pct']}}%")
print(f"最大回撤: {{result['max_drawdown']}}%")
print(f"胜率: {{result['win_rate']}}%")
'''
    return code


def main():
    print("=" * 90)
    print("🎯 Bollinger Bands 策略参数优化")
    print("=" * 90)
    
    # 生成数据
    print("\n📊 生成测试数据...")
    data = generate_mock_data(days=500)
    print(f"   数据条数: {len(data)}")
    print(f"   日期范围: {data.index[0].date()} ~ {data.index[-1].date()}")
    
    # 基准测试 (原始参数)
    print("\n📏 基准测试 (原始参数: period=20, std_dev=2.0, exit=upper)...")
    baseline = run_single_test(data, period=20, std_dev=2.0, exit_logic='upper')
    print(f"   收益: {baseline.return_pct:+.2f}% | 回撤: {baseline.max_drawdown:.2f}% | 胜率: {baseline.win_rate:.1f}%")
    
    # 网格搜索
    results = grid_search(data)
    
    # 打印结果
    print_results(results, top_n=15)
    print_heatmap(results)
    
    # 最佳结果
    best = max(results, key=lambda x: x.score)
    
    print("\n" + "=" * 90)
    print("🏆 最佳参数组合")
    print("=" * 90)
    print(f"\n参数:")
    print(f"   period (周期): {best.period}")
    print(f"   std_dev (倍数): {best.std_dev}")
    print(f"   exit_logic (卖出): {best.exit_logic}")
    print(f"\n回测表现:")
    print(f"   收益率: {best.return_pct:+.2f}%")
    print(f"   最大回撤: {best.max_drawdown:.2f}%")
    print(f"   胜率: {best.win_rate:.1f}%")
    print(f"   交易次数: {best.total_trades}")
    print(f"   综合得分: {best.score:.2f}")
    
    # 对比提升
    improvement = best.return_pct - baseline.return_pct
    print(f"\n📈 相比基准提升: {improvement:+.2f}%")
    
    # 生成代码
    print("\n" + "=" * 90)
    print("💡 最佳策略使用代码")
    print("=" * 90)
    print(generate_best_strategy_code(best))
    
    print("\n" + "=" * 90)
    print("✅ 优化完成！")
    print("=" * 90)


if __name__ == "__main__":
    main()
