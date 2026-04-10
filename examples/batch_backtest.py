#!/usr/bin/env python3
"""
批量回测系统 - 测试多种策略并生成对比报告

功能:
1. 生成多种策略的参数组合
2. 批量回测所有策略
3. 排序并输出最佳策略
4. 生成详细对比报告
"""
import sys
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime
import json

import pandas as pd
import numpy as np

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.backtest import BacktestEngine
from brain.strategies.lib import StrategyOptimizer, generate_strategy


def generate_mock_data(days=500, start_price=100, trend=0.0003, volatility=0.02, seed=42):
    """生成模拟股票数据"""
    np.random.seed(seed)
    
    dates = pd.date_range(start='2022-01-01', periods=days, freq='B')
    
    # 随机游走生成价格
    returns = np.random.normal(trend, volatility, days)
    prices = start_price * (1 + returns).cumprod()
    
    # 生成 OHLCV
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


def run_single_backtest(data: pd.DataFrame, strategy_id: str, 
                        strategy_name: str, params: Dict) -> Dict:
    """
    运行单个策略回测
    
    Returns:
        回测结果字典
    """
    try:
        # 生成信号
        signals = generate_strategy(data, strategy_name, **params)
        
        # 检查是否有交易信号
        if signals.abs().sum() == 0:
            return None
        
        # 运行回测
        engine = BacktestEngine(
            initial_cash=100000,
            commission_rate=0.00025,
            engine_type="ashare"
        )
        
        result = engine.run(data, signals, symbol="TEST")
        
        # 添加策略信息
        result['strategy_id'] = strategy_id
        result['strategy_name'] = strategy_name
        result['params'] = params
        
        return result
        
    except Exception as e:
        print(f"   ❌ 回测失败 {strategy_id}: {e}")
        return None


def calculate_score(result: Dict) -> float:
    """
    计算策略综合得分
    
    综合考虑:
    - 收益率 (权重40%)
    - 夏普比率近似 (收益率/最大回撤, 权重30%)
    - 胜率 (权重20%)
    - 盈亏比 (权重10%)
    """
    return_pct = result.get('return_pct', 0)
    max_dd = abs(result.get('max_drawdown', 1))
    win_rate = result.get('win_rate', 0)
    pl_ratio = result.get('profit_loss_ratio', 0)
    
    # 避免除以零
    if max_dd < 0.01:
        max_dd = 0.01
    
    # 夏普近似
    sharpe_like = return_pct / max_dd if max_dd > 0 else 0
    
    # 综合得分
    score = (
        return_pct * 0.4 +
        sharpe_like * 0.3 +
        win_rate * 0.2 +
        pl_ratio * 0.1
    )
    
    return score


def run_batch_backtest(data: pd.DataFrame, strategies: List[Tuple]) -> List[Dict]:
    """
    批量运行回测
    
    Args:
        data: 股票数据
        strategies: 策略列表 [(id, name, params), ...]
        
    Returns:
        回测结果列表
    """
    results = []
    total = len(strategies)
    
    print(f"\n🚀 开始批量回测，共 {total} 个策略...")
    print("=" * 70)
    
    for i, (strategy_id, strategy_name, params) in enumerate(strategies, 1):
        print(f"\n[{i}/{total}] 测试 {strategy_id}...", end=" ")
        
        result = run_single_backtest(data, strategy_id, strategy_name, params)
        
        if result:
            score = calculate_score(result)
            result['score'] = score
            results.append(result)
            print(f"✅ 收益率: {result['return_pct']:+.2f}%, 得分: {score:.2f}")
        else:
            print("⚠️  无交易信号")
    
    return results


def generate_report(results: List[Dict], top_n: int = 10) -> str:
    """
    生成回测对比报告
    
    Args:
        results: 回测结果列表
        top_n: 显示前N名
        
    Returns:
        报告文本
    """
    if not results:
        return "没有有效的回测结果"
    
    # 按得分排序
    sorted_results = sorted(results, key=lambda x: x['score'], reverse=True)
    
    report_lines = []
    report_lines.append("\n" + "=" * 90)
    report_lines.append("📊 批量回测结果报告")
    report_lines.append("=" * 90)
    
    # 总体统计
    report_lines.append(f"\n📈 总体统计:")
    report_lines.append(f"   测试策略数: {len(results)}")
    report_lines.append(f"   盈利策略: {sum(1 for r in results if r['return_pct'] > 0)}")
    report_lines.append(f"   亏损策略: {sum(1 for r in results if r['return_pct'] <= 0)}")
    report_lines.append(f"   平均收益率: {np.mean([r['return_pct'] for r in results]):.2f}%")
    
    # 最佳策略
    best = sorted_results[0]
    report_lines.append(f"\n🏆 最佳策略:")
    report_lines.append(f"   名称: {best['strategy_id']}")
    report_lines.append(f"   收益率: {best['return_pct']:+.2f}%")
    report_lines.append(f"   最大回撤: {best['max_drawdown']:.2f}%")
    report_lines.append(f"   胜率: {best['win_rate']:.1f}%")
    report_lines.append(f"   交易次数: {best['total_trades']}")
    report_lines.append(f"   综合得分: {best['score']:.2f}")
    
    # Top N 表格
    report_lines.append(f"\n📋 Top {top_n} 策略排名:")
    report_lines.append("-" * 90)
    report_lines.append(f"{'排名':<4} {'策略ID':<25} {'收益率':<10} {'回撤':<8} {'胜率':<8} {'交易':<6} {'得分':<8}")
    report_lines.append("-" * 90)
    
    for i, r in enumerate(sorted_results[:top_n], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        report_lines.append(
            f"{medal} {i:<2} {r['strategy_id']:<25} "
            f"{r['return_pct']:>+7.2f}% {r['max_drawdown']:>6.2f}% "
            f"{r['win_rate']:>6.1f}% {r['total_trades']:>4} {r['score']:>7.2f}"
        )
    
    report_lines.append("-" * 90)
    
    # 按策略类型统计
    report_lines.append("\n📊 按策略类型统计:")
    strategy_types = {}
    for r in results:
        name = r['strategy_name']
        if name not in strategy_types:
            strategy_types[name] = []
        strategy_types[name].append(r['return_pct'])
    
    for name, returns in sorted(strategy_types.items(), key=lambda x: np.mean(x[1]), reverse=True):
        avg_return = np.mean(returns)
        best_return = max(returns)
        report_lines.append(f"   {name:<20} 平均: {avg_return:>+6.2f}%  最佳: {best_return:>+6.2f}%")
    
    report_lines.append("\n" + "=" * 90)
    
    return "\n".join(report_lines)


def save_results(results: List[Dict], output_dir: str = "reports"):
    """保存详细结果到JSON"""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = output_path / f"batch_backtest_{timestamp}.json"
    
    # 简化数据以便JSON序列化
    simple_results = []
    for r in results:
        simple_results.append({
            'strategy_id': r['strategy_id'],
            'strategy_name': r['strategy_name'],
            'params': r['params'],
            'return_pct': r['return_pct'],
            'max_drawdown': r['max_drawdown'],
            'total_trades': r['total_trades'],
            'win_rate': r['win_rate'],
            'profit_loss_ratio': r['profit_loss_ratio'],
            'score': r['score']
        })
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(simple_results, f, ensure_ascii=False, indent=2)
    
    return filename


def main():
    print("=" * 90)
    print("🧠 Brain 量化框架 - 批量策略回测系统")
    print("=" * 90)
    
    # 1. 生成模拟数据
    print("\n📊 生成测试数据...")
    data = generate_mock_data(days=500, start_price=100, trend=0.0003, volatility=0.02)
    print(f"   数据条数: {len(data)}")
    print(f"   日期范围: {data.index[0].date()} ~ {data.index[-1].date()}")
    print(f"   最终价格: {data['close'].iloc[-1]:.2f}")
    
    # 2. 生成所有策略
    print("\n📋 生成策略组合...")
    strategies = StrategyOptimizer.generate_all_strategies()
    print(f"   共生成 {len(strategies)} 个策略参数组合")
    
    # 显示策略列表
    strategy_names = set([s[1] for s in strategies])
    print(f"   策略类型: {', '.join(sorted(strategy_names))}")
    
    # 3. 批量回测
    results = run_batch_backtest(data, strategies)
    
    # 4. 生成报告
    if results:
        print("\n" + generate_report(results, top_n=15))
        
        # 5. 保存结果
        filename = save_results(results)
        print(f"\n💾 详细结果已保存: {filename}")
        
        # 6. 输出最佳策略详情
        best = sorted(results, key=lambda x: x['score'], reverse=True)[0]
        print(f"\n🔍 最佳策略详情:")
        print(f"   ID: {best['strategy_id']}")
        print(f"   参数: {best['params']}")
        print(f"   初始资金: ¥{best['initial_value']:,.2f}")
        print(f"   最终资金: ¥{best['final_value']:,.2f}")
        print(f"   盈亏: ¥{best['final_value'] - best['initial_value']:,.2f}")
        
        trades = best.get('trades', [])
        if trades:
            print(f"\n   交易明细 (最近5笔):")
            for t in list(trades)[-5:]:
                pnl_str = f"{t.pnl:+.2f}"
                print(f"      {str(t.entry_time)[:10]} {t.direction:>2} {pnl_str:>10}")
    else:
        print("\n❌ 没有有效的回测结果")
    
    print("\n" + "=" * 90)
    print("✅ 批量回测完成！")
    print("=" * 90)


if __name__ == "__main__":
    main()
