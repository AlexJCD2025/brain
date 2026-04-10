#!/usr/bin/env python3
"""
可视化回测结果
生成策略对比图表
"""
import sys
from pathlib import Path
import json

import pandas as pd
import numpy as np

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_latest_results(reports_dir: str = "reports") -> list:
    """加载最新的回测结果"""
    import glob
    
    files = glob.glob(f"{reports_dir}/batch_backtest_*.json")
    if not files:
        print("未找到回测结果文件")
        return []
    
    latest = max(files, key=lambda x: Path(x).stat().st_mtime)
    print(f"加载结果: {latest}")
    
    with open(latest, 'r', encoding='utf-8') as f:
        return json.load(f)


def print_ascii_chart(data: list, title: str, width: 50):
    """打印ASCII条形图"""
    print(f"\n{title}")
    print("=" * 70)
    
    values = [d['return_pct'] for d in data]
    names = [d['strategy_id'][:20] for d in data]
    
    max_val = max(values) if values else 1
    min_val = min(values) if values else 0
    
    for name, val in zip(names, values):
        # 计算条形长度
        if max_val != min_val:
            bar_len = int((val - min_val) / (max_val - min_val) * width)
        else:
            bar_len = width // 2
        
        bar = "█" * max(0, bar_len)
        color = "🟢" if val > 0 else "🔴"
        print(f"{name:<20} {color} {val:>+7.2f}% {bar}")
    
    print("=" * 70)


def print_strategy_type_summary(results: list):
    """按策略类型打印汇总"""
    print("\n📊 策略类型表现对比")
    print("=" * 70)
    
    # 按类型分组
    by_type = {}
    for r in results:
        t = r['strategy_name']
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(r)
    
    # 计算统计
    summary = []
    for t, items in by_type.items():
        returns = [i['return_pct'] for i in items]
        summary.append({
            'type': t,
            'count': len(items),
            'avg': np.mean(returns),
            'max': max(returns),
            'min': min(returns),
            'win_rate': sum(1 for r in returns if r > 0) / len(returns) * 100
        })
    
    # 按平均收益排序
    summary.sort(key=lambda x: x['avg'], reverse=True)
    
    print(f"{'策略类型':<18} {'数量':<6} {'平均':<8} {'最佳':<8} {'最差':<8} {'胜率':<6}")
    print("-" * 70)
    
    for s in summary:
        medal = "🥇" if s['avg'] > 5 else "🥈" if s['avg'] > 0 else "🥉"
        print(f"{medal} {s['type']:<16} {s['count']:<6} "
              f"{s['avg']:>+6.2f}% {s['max']:>+6.2f}% {s['min']:>+6.2f}% {s['win_rate']:>5.1f}%")


def print_top_strategies(results: list, n: int = 5):
    """打印最佳策略"""
    print(f"\n🏆 Top {n} 策略")
    print("=" * 70)
    
    sorted_results = sorted(results, key=lambda x: x['score'], reverse=True)
    
    for i, r in enumerate(sorted_results[:n], 1):
        print(f"\n{i}. {r['strategy_id']}")
        print(f"   参数: {r['params']}")
        print(f"   📈 收益率: {r['return_pct']:+.2f}%")
        print(f"   📉 最大回撤: {r['max_drawdown']:.2f}%")
        print(f"   🎯 胜率: {r['win_rate']:.1f}%")
        print(f"   💰 盈亏比: {r['profit_loss_ratio']:.2f}")
        print(f"   🔢 交易次数: {r['total_trades']}")
        print(f"   ⭐ 综合得分: {r['score']:.2f}")


def print_performance_matrix(results: list):
    """打印绩效矩阵"""
    print("\n📈 绩效矩阵")
    print("=" * 70)
    
    # 提取数据
    returns = [r['return_pct'] for r in results]
    drawdowns = [abs(r['max_drawdown']) for r in results]
    win_rates = [r['win_rate'] for r in results]
    scores = [r['score'] for r in results]
    
    print(f"\n{'指标':<15} {'平均':<10} {'中位数':<10} {'最高':<10} {'最低':<10}")
    print("-" * 70)
    print(f"{'收益率(%)':<15} {np.mean(returns):>+8.2f} {np.median(returns):>+8.2f} "
          f"{max(returns):>+8.2f} {min(returns):>+8.2f}")
    print(f"{'回撤(%)':<15} {np.mean(drawdowns):>8.2f} {np.median(drawdowns):>8.2f} "
          f"{max(drawdowns):>8.2f} {min(drawdowns):>8.2f}")
    print(f"{'胜率(%)':<15} {np.mean(win_rates):>8.2f} {np.median(win_rates):>8.2f} "
          f"{max(win_rates):>8.2f} {min(win_rates):>8.2f}")
    print(f"{'综合得分':<15} {np.mean(scores):>8.2f} {np.median(scores):>8.2f} "
          f"{max(scores):>8.2f} {min(scores):>8.2f}")


def generate_strategy_code(result: dict) -> str:
    """生成最佳策略的Python代码"""
    name = result['strategy_name']
    params = result['params']
    
    code = f'''
# 最佳策略代码: {result['strategy_id']}
# 收益率: {result['return_pct']:+.2f}%, 得分: {result['score']:.2f}

from brain.strategies.lib import generate_strategy

# 生成信号
signals = generate_strategy(
    data=data,
    strategy_name="{name}",
    {chr(10).join([f"    {k}={v}," for k, v in params.items()])}
)

# 运行回测
engine = BacktestEngine(initial_cash=100000, engine_type="ashare")
result = engine.run(data, signals, symbol="000001")
'''
    return code


def main():
    print("=" * 70)
    print("🧠 Brain 量化框架 - 回测结果可视化")
    print("=" * 70)
    
    # 加载结果
    results = load_latest_results()
    if not results:
        return
    
    print(f"\n✅ 加载了 {len(results)} 个策略的回测结果")
    
    # 按收益率排序
    sorted_by_return = sorted(results, key=lambda x: x['return_pct'], reverse=True)
    
    # 打印收益率条形图
    print_ascii_chart(sorted_by_return[:15], "📊 收益率排名 (Top 15)", width=40)
    
    # 策略类型汇总
    print_strategy_type_summary(results)
    
    # 绩效矩阵
    print_performance_matrix(results)
    
    # 最佳策略详情
    print_top_strategies(results, n=5)
    
    # 生成最佳策略代码
    best = sorted(results, key=lambda x: x['score'], reverse=True)[0]
    print(f"\n💡 最佳策略使用代码:")
    print("-" * 70)
    print(generate_strategy_code(best))
    
    print("\n" + "=" * 70)
    print("✅ 可视化完成！")
    print("=" * 70)


if __name__ == "__main__":
    main()
