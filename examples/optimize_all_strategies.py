#!/usr/bin/env python3
"""
全策略批量参数优化系统

对9大策略进行网格搜索，找出每个策略的最佳参数组合

优化策略:
1. dual_ma (双均线) - 优化fast/slow周期组合
2. macd - 优化fast/slow/signal周期
3. rsi - 优化period和超买超卖阈值
4. bollinger - 优化period和std_dev (已单独优化过)
5. momentum - 优化period
6. atr_breakout - 优化period和multiplier
7. donchian - 优化period
8. volume_price - 优化period
9. supertrend - 优化period和multiplier
"""
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import json

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.strategies.lib import generate_strategy
from brain.backtest import BacktestEngine


@dataclass
class OptimizationResult:
    """优化结果数据类"""
    strategy_name: str
    best_params: Dict[str, Any]
    return_pct: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    profit_loss_ratio: float
    score: float
    all_results: List[Dict] = None
    
    def to_dict(self) -> Dict:
        return {
            'strategy_name': self.strategy_name,
            'best_params': self.best_params,
            'return_pct': self.return_pct,
            'max_drawdown': self.max_drawdown,
            'win_rate': self.win_rate,
            'total_trades': self.total_trades,
            'profit_loss_ratio': self.profit_loss_ratio,
            'score': self.score
        }


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


def calculate_score(return_pct: float, max_drawdown: float, 
                   win_rate: float, trades: int) -> float:
    """计算综合得分"""
    if max_drawdown == 0:
        max_drawdown = -0.01
    
    sharpe_like = return_pct / abs(max_drawdown) if max_drawdown != 0 else 0
    trade_penalty = min(trades / 50, 1.0) * 5
    
    score = (
        return_pct * 0.4 +
        sharpe_like * 0.3 +
        win_rate * 0.2 +
        (100 - trade_penalty) * 0.1
    )
    
    return score


def run_backtest(data: pd.DataFrame, strategy_name: str, params: Dict) -> Dict:
    """运行单次回测"""
    try:
        signals = generate_strategy(data, strategy_name, **params)
        
        if signals.abs().sum() == 0:
            return None
        
        engine = BacktestEngine(
            initial_cash=100000,
            commission_rate=0.00025,
            engine_type="ashare"
        )
        
        result = engine.run(data, signals, symbol="TEST")
        result['score'] = calculate_score(
            result['return_pct'],
            result['max_drawdown'],
            result['win_rate'],
            result['total_trades']
        )
        return result
        
    except Exception as e:
        print(f"   回测失败: {e}")
        return None


def optimize_dual_ma(data: pd.DataFrame) -> OptimizationResult:
    """优化双均线策略"""
    print("\n📈 优化 dual_ma (双均线)...")
    
    param_grid = [
        {'fast': 5, 'slow': 20, 'ma_type': 'sma'},
        {'fast': 10, 'slow': 30, 'ma_type': 'sma'},
        {'fast': 20, 'slow': 60, 'ma_type': 'sma'},
        {'fast': 5, 'slow': 20, 'ma_type': 'ema'},
        {'fast': 10, 'slow': 30, 'ma_type': 'ema'},
        {'fast': 12, 'slow': 26, 'ma_type': 'ema'},  # MACD风格
    ]
    
    return optimize_strategy(data, 'dual_ma', param_grid)


def optimize_macd(data: pd.DataFrame) -> OptimizationResult:
    """优化MACD策略"""
    print("\n📈 优化 macd...")
    
    param_grid = [
        {'fast': 8, 'slow': 21, 'signal': 5},
        {'fast': 12, 'slow': 26, 'signal': 9},  # 标准参数
        {'fast': 5, 'slow': 35, 'signal': 5},
        {'fast': 10, 'slow': 50, 'signal': 10},
    ]
    
    return optimize_strategy(data, 'macd', param_grid)


def optimize_rsi(data: pd.DataFrame) -> OptimizationResult:
    """优化RSI策略"""
    print("\n📈 优化 rsi...")
    
    param_grid = [
        {'period': 7, 'overbought': 75, 'oversold': 25},
        {'period': 14, 'overbought': 70, 'oversold': 30},  # 标准
        {'period': 21, 'overbought': 75, 'oversold': 25},
        {'period': 14, 'overbought': 80, 'oversold': 20},  # 更严格
    ]
    
    return optimize_strategy(data, 'rsi', param_grid)


def optimize_bollinger(data: pd.DataFrame) -> OptimizationResult:
    """优化布林带策略"""
    print("\n📈 优化 bollinger...")
    
    param_grid = [
        {'period': 15, 'std_dev': 2.5},  # 已优化
        {'period': 20, 'std_dev': 2.0},  # 标准
        {'period': 10, 'std_dev': 2.5},
        {'period': 25, 'std_dev': 2.0},
    ]
    
    return optimize_strategy(data, 'bollinger', param_grid)


def optimize_momentum(data: pd.DataFrame) -> OptimizationResult:
    """优化动量策略"""
    print("\n📈 优化 momentum...")
    
    param_grid = [
        {'period': 10},
        {'period': 20},  # 标准
        {'period': 30},
        {'period': 60},
    ]
    
    return optimize_strategy(data, 'momentum', param_grid)


def optimize_atr_breakout(data: pd.DataFrame) -> OptimizationResult:
    """优化ATR突破策略"""
    print("\n📈 优化 atr_breakout...")
    
    param_grid = [
        {'period': 10, 'multiplier': 1.5},
        {'period': 14, 'multiplier': 2.0},  # 标准
        {'period': 20, 'multiplier': 2.5},
        {'period': 20, 'multiplier': 3.0},  # 海龟风格
    ]
    
    return optimize_strategy(data, 'atr_breakout', param_grid)


def optimize_donchian(data: pd.DataFrame) -> OptimizationResult:
    """优化唐奇安通道策略"""
    print("\n📈 优化 donchian...")
    
    param_grid = [
        {'period': 20},   # 短期
        {'period': 55},   # 中期 (海龟)
        {'period': 100},  # 长期
    ]
    
    return optimize_strategy(data, 'donchian', param_grid)


def optimize_volume_price(data: pd.DataFrame) -> OptimizationResult:
    """优化量价趋势策略"""
    print("\n📈 优化 volume_price...")
    
    param_grid = [
        {'period': 10},
        {'period': 20},  # 标准
        {'period': 30},
    ]
    
    return optimize_strategy(data, 'volume_price', param_grid)


def optimize_supertrend(data: pd.DataFrame) -> OptimizationResult:
    """优化超级趋势策略"""
    print("\n📈 优化 supertrend...")
    
    param_grid = [
        {'period': 10, 'multiplier': 3.0},
        {'period': 14, 'multiplier': 2.0},
        {'period': 20, 'multiplier': 1.5},
    ]
    
    return optimize_strategy(data, 'supertrend', param_grid)


def optimize_strategy(data: pd.DataFrame, strategy_name: str, 
                     param_grid: List[Dict]) -> OptimizationResult:
    """通用策略优化函数"""
    results = []
    
    for params in param_grid:
        result = run_backtest(data, strategy_name, params)
        if result:
            results.append({
                'params': params,
                'return_pct': result['return_pct'],
                'max_drawdown': result['max_drawdown'],
                'win_rate': result['win_rate'],
                'total_trades': result['total_trades'],
                'profit_loss_ratio': result.get('profit_loss_ratio', 0),
                'score': result['score']
            })
    
    if not results:
        return OptimizationResult(
            strategy_name=strategy_name,
            best_params={},
            return_pct=0,
            max_drawdown=0,
            win_rate=0,
            total_trades=0,
            profit_loss_ratio=0,
            score=0,
            all_results=[]
        )
    
    # 找最佳结果
    best = max(results, key=lambda x: x['score'])
    
    return OptimizationResult(
        strategy_name=strategy_name,
        best_params=best['params'],
        return_pct=best['return_pct'],
        max_drawdown=best['max_drawdown'],
        win_rate=best['win_rate'],
        total_trades=best['total_trades'],
        profit_loss_ratio=best['profit_loss_ratio'],
        score=best['score'],
        all_results=results
    )


def print_optimization_report(results: List[OptimizationResult]):
    """打印优化报告"""
    print("\n" + "=" * 100)
    print("📊 全策略参数优化报告")
    print("=" * 100)
    
    # 按得分排序
    sorted_results = sorted(results, key=lambda x: x.score, reverse=True)
    
    print("\n🏆 策略综合排名 (按得分):")
    print("-" * 100)
    print(f"{'排名':<4} {'策略':<15} {'最佳参数':<30} {'收益':<10} {'回撤':<8} {'胜率':<8} {'交易':<6} {'得分':<8}")
    print("-" * 100)
    
    for i, r in enumerate(sorted_results, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        params_str = str(r.best_params)[:28]
        print(f"{medal} {i:<2} {r.strategy_name:<13} {params_str:<30} "
              f"{r.return_pct:>+7.2f}% {r.max_drawdown:>6.2f}% {r.win_rate:>6.1f}% {r.total_trades:>4} {r.score:>7.2f}")
    
    print("-" * 100)
    
    # 按收益率排序
    print("\n💰 策略收益率排名:")
    print("-" * 100)
    by_return = sorted(results, key=lambda x: x.return_pct, reverse=True)
    
    for i, r in enumerate(by_return, 1):
        params_str = str(r.best_params)[:40]
        print(f"{i}. {r.strategy_name:<15} {params_str:<40} → {r.return_pct:>+7.2f}%")
    
    print("-" * 100)
    
    # 按回撤排序
    print("\n🛡️  策略回撤排名 (越小越好):")
    print("-" * 100)
    by_dd = sorted(results, key=lambda x: abs(x.max_drawdown))
    
    for i, r in enumerate(by_dd, 1):
        print(f"{i}. {r.strategy_name:<15} 回撤: {r.max_drawdown:>6.2f}%")
    
    print("-" * 100)


def generate_best_params_json(results: List[OptimizationResult]):
    """生成最佳参数字典"""
    best_params = {}
    for r in results:
        best_params[r.strategy_name] = {
            'params': r.best_params,
            'performance': {
                'return_pct': r.return_pct,
                'max_drawdown': r.max_drawdown,
                'win_rate': r.win_rate,
                'total_trades': r.total_trades,
                'score': r.score
            }
        }
    return best_params


def print_strategy_details(results: List[OptimizationResult]):
    """打印每个策略的详细优化结果"""
    print("\n" + "=" * 100)
    print("🔍 各策略详细优化结果")
    print("=" * 100)
    
    for r in results:
        print(f"\n📌 {r.strategy_name.upper()}")
        print("-" * 80)
        print(f"   最佳参数: {r.best_params}")
        print(f"   回测表现:")
        print(f"     • 收益率: {r.return_pct:+.2f}%")
        print(f"     • 最大回撤: {r.max_drawdown:.2f}%")
        print(f"     • 胜率: {r.win_rate:.1f}%")
        print(f"     • 交易次数: {r.total_trades}")
        print(f"     • 盈亏比: {r.profit_loss_ratio:.2f}")
        print(f"     • 综合得分: {r.score:.2f}")
        
        if r.all_results and len(r.all_results) > 1:
            print(f"   参数对比:")
            sorted_all = sorted(r.all_results, key=lambda x: x['score'], reverse=True)
            for i, res in enumerate(sorted_all[:3], 1):
                print(f"     {i}. {res['params']} → 收益 {res['return_pct']:+.2f}% | 得分 {res['score']:.2f}")


def save_results(results: List[OptimizationResult], output_dir: str = "reports"):
    """保存优化结果"""
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{output_dir}/strategy_optimization_{timestamp}.json"
    
    data = {
        'timestamp': timestamp,
        'strategies': [r.to_dict() for r in results]
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return filename


def main():
    print("=" * 100)
    print("🚀 全策略批量参数优化系统")
    print("=" * 100)
    
    # 生成数据
    print("\n📊 生成测试数据...")
    data = generate_mock_data(days=500)
    print(f"   数据条数: {len(data)}")
    print(f"   日期范围: {data.index[0].date()} ~ {data.index[-1].date()}")
    
    # 优化所有策略
    print("\n🔍 开始批量优化...")
    print("-" * 100)
    
    results = []
    
    results.append(optimize_dual_ma(data))
    results.append(optimize_macd(data))
    results.append(optimize_rsi(data))
    results.append(optimize_bollinger(data))
    results.append(optimize_momentum(data))
    results.append(optimize_atr_breakout(data))
    results.append(optimize_donchian(data))
    results.append(optimize_volume_price(data))
    results.append(optimize_supertrend(data))
    
    # 打印报告
    print_optimization_report(results)
    print_strategy_details(results)
    
    # 保存结果
    filename = save_results(results)
    print(f"\n💾 优化结果已保存: {filename}")
    
    # 生成最佳参数代码
    print("\n" + "=" * 100)
    print("💡 最佳参数汇总 (可直接使用)")
    print("=" * 100)
    
    print("\n```python")
    print("# 全策略最佳参数配置")
    print("BEST_PARAMS = {")
    
    for r in sorted(results, key=lambda x: x.score, reverse=True):
        params_str = json.dumps(r.best_params, ensure_ascii=False)
        print(f"    '{r.strategy_name}': {params_str},  # 得分: {r.score:.2f}, 收益: {r.return_pct:+.2f}%")
    
    print("}")
    print("```")
    
    # 使用示例
    print("\n" + "=" * 100)
    print("📝 快速使用示例")
    print("=" * 100)
    
    best = max(results, key=lambda x: x.score)
    print(f"\n# 使用最佳策略: {best.strategy_name}")
    print(f"signals = generate_strategy(")
    print(f"    data=data,")
    print(f"    strategy_name='{best.strategy_name}',")
    for k, v in best.best_params.items():
        print(f"    {k}={v},")
    print(f")")
    
    print("\n" + "=" * 100)
    print("✅ 批量优化完成！")
    print("=" * 100)


if __name__ == "__main__":
    main()
