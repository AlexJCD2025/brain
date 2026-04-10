#!/usr/bin/env python3
"""
30策略批量参数优化系统

对30个策略进行网格搜索，找出每个策略的最佳参数组合
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


# ============================================================
# 30策略参数网格定义
# ============================================================

def get_strategy_param_grids() -> Dict[str, List[Dict]]:
    """获取所有30个策略的参数网格"""
    
    return {
        # 1. 双均线
        'dual_ma': [
            {'fast': 5, 'slow': 20, 'ma_type': 'sma'},
            {'fast': 10, 'slow': 30, 'ma_type': 'sma'},
            {'fast': 5, 'slow': 20, 'ma_type': 'ema'},
            {'fast': 10, 'slow': 30, 'ma_type': 'ema'},
            {'fast': 12, 'slow': 26, 'ma_type': 'ema'},
        ],
        
        # 2. MACD
        'macd': [
            {'fast': 8, 'slow': 21, 'signal': 5},
            {'fast': 12, 'slow': 26, 'signal': 9},
            {'fast': 5, 'slow': 35, 'signal': 5},
        ],
        
        # 3. RSI
        'rsi': [
            {'period': 7, 'overbought': 75, 'oversold': 25},
            {'period': 14, 'overbought': 70, 'oversold': 30},
            {'period': 21, 'overbought': 75, 'oversold': 25},
            {'period': 14, 'overbought': 80, 'oversold': 20},
        ],
        
        # 4. 布林带
        'bollinger': [
            {'period': 15, 'std_dev': 2.5},
            {'period': 20, 'std_dev': 2.0},
            {'period': 10, 'std_dev': 2.5},
            {'period': 25, 'std_dev': 2.0},
        ],
        
        # 5. 动量
        'momentum': [
            {'period': 10},
            {'period': 20},
            {'period': 30},
            {'period': 60},
        ],
        
        # 6. ATR突破
        'atr_breakout': [
            {'period': 10, 'multiplier': 1.5},
            {'period': 14, 'multiplier': 2.0},
            {'period': 20, 'multiplier': 2.5},
            {'period': 20, 'multiplier': 3.0},
        ],
        
        # 7. 唐奇安通道
        'donchian': [
            {'period': 20},
            {'period': 55},
            {'period': 100},
        ],
        
        # 8. 量价趋势
        'volume_price': [
            {'period': 10},
            {'period': 20},
            {'period': 30},
        ],
        
        # 9. 超级趋势
        'supertrend': [
            {'period': 10, 'multiplier': 3.0},
            {'period': 14, 'multiplier': 2.0},
            {'period': 20, 'multiplier': 1.5},
        ],
        
        # 10. KDJ
        'kdj': [
            {'n': 9, 'm1': 3, 'm2': 3},
            {'n': 14, 'm1': 3, 'm2': 3},
            {'n': 9, 'm1': 5, 'm2': 5},
        ],
        
        # 11. CCI
        'cci': [
            {'period': 14, 'upper': 100, 'lower': -100},
            {'period': 20, 'upper': 100, 'lower': -100},
            {'period': 14, 'upper': 150, 'lower': -150},
        ],
        
        # 12. Williams %R
        'williams_r': [
            {'period': 10, 'upper': -20, 'lower': -80},
            {'period': 14, 'upper': -20, 'lower': -80},
            {'period': 21, 'upper': -20, 'lower': -80},
        ],
        
        # 13. 一目均衡表
        'ichimoku': [
            {'tenkan_period': 9, 'kijun_period': 26, 'senkou_b_period': 52},
            {'tenkan_period': 5, 'kijun_period': 20, 'senkou_b_period': 40},
        ],
        
        # 14. 抛物线SAR
        'parabolic_sar': [
            {'af_start': 0.02, 'af_max': 0.20},
            {'af_start': 0.01, 'af_max': 0.10},
            {'af_start': 0.03, 'af_max': 0.30},
        ],
        
        # 15. OBV
        'obv': [
            {},  # 无参数
        ],
        
        # 16. ADX
        'adx': [
            {'period': 14, 'threshold': 25.0},
            {'period': 20, 'threshold': 25.0},
            {'period': 14, 'threshold': 20.0},
        ],
        
        # 17. MFI
        'mfi': [
            {'period': 14, 'overbought': 80, 'oversold': 20},
            {'period': 10, 'overbought': 80, 'oversold': 20},
            {'period': 21, 'overbought': 80, 'oversold': 20},
        ],
        
        # 18. VWAP
        'vwap': [
            {'period': 20},
            {'period': 30},
            {'period': 50},
        ],
        
        # 19. 随机震荡
        'stochastic': [
            {'k_period': 14, 'd_period': 3, 'overbought': 80, 'oversold': 20},
            {'k_period': 10, 'd_period': 3, 'overbought': 80, 'oversold': 20},
            {'k_period': 21, 'd_period': 5, 'overbought': 80, 'oversold': 20},
        ],
        
        # 20. Heikin-Ashi
        'heikin_ashi': [
            {},  # 无参数
        ],
        
        # 21. TRIX
        'trix': [
            {'period': 12, 'signal_period': 9},
            {'period': 15, 'signal_period': 9},
            {'period': 20, 'signal_period': 9},
        ],
        
        # 22. Aroon
        'aroon': [
            {'period': 14},
            {'period': 20},
            {'period': 25},
        ],
        
        # 23. 终极震荡
        'ultimate_oscillator': [
            {'short_period': 7, 'medium_period': 14, 'long_period': 28},
            {'short_period': 5, 'medium_period': 10, 'long_period': 20},
        ],
        
        # 24. 蔡金资金流
        'chaikin_money_flow': [
            {'period': 20},
            {'period': 14},
            {'period': 30},
        ],
        
        # 25. 肯特纳通道
        'keltner_channel': [
            {'period': 20, 'atr_multiplier': 2.0},
            {'period': 20, 'atr_multiplier': 1.5},
            {'period': 20, 'atr_multiplier': 2.5},
        ],
        
        # 26. ROC
        'rate_of_change': [
            {'period': 10},
            {'period': 12},
            {'period': 20},
        ],
        
        # 27. TSI
        'tsi': [
            {'long_period': 25, 'short_period': 13},
            {'long_period': 20, 'short_period': 10},
        ],
        
        # 28. 漩涡指标
        'vortex_indicator': [
            {'period': 14},
            {'period': 20},
        ],
        
        # 29. Awesome Oscillator
        'awesome_oscillator': [
            {'short_period': 5, 'long_period': 34},
            {'short_period': 5, 'long_period': 21},
        ],
        
        # 30. 鳄鱼线
        'alligator': [
            {'jaw_period': 13, 'teeth_period': 8, 'lips_period': 5},
            {'jaw_period': 21, 'teeth_period': 13, 'lips_period': 8},
        ],
    }


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
    print("📊 30策略参数优化报告")
    print("=" * 100)
    
    # 按得分排序
    sorted_results = sorted(results, key=lambda x: x.score, reverse=True)
    
    print("\n🏆 策略综合排名 (按得分):")
    print("-" * 100)
    print(f"{'排名':<4} {'策略':<20} {'最佳参数':<35} {'收益':<10} {'回撤':<8} {'胜率':<8} {'交易':<6} {'得分':<8}")
    print("-" * 100)
    
    for i, r in enumerate(sorted_results, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        params_str = str(r.best_params)[:33]
        print(f"{medal} {i:<2} {r.strategy_name:<18} {params_str:<35} "
              f"{r.return_pct:>+7.2f}% {r.max_drawdown:>6.2f}% {r.win_rate:>6.1f}% {r.total_trades:>4} {r.score:>7.2f}")
    
    print("-" * 100)
    
    # 按收益率排序
    print("\n💰 策略收益率排名:")
    print("-" * 100)
    by_return = sorted(results, key=lambda x: x.return_pct, reverse=True)
    
    for i, r in enumerate(by_return[:15], 1):
        params_str = str(r.best_params)[:40]
        print(f"{i}. {r.strategy_name:<20} {params_str:<40} → {r.return_pct:>+7.2f}%")
    
    print("-" * 100)


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
    filename = f"{output_dir}/30_strategy_optimization_{timestamp}.json"
    
    data = {
        'timestamp': timestamp,
        'strategies': [r.to_dict() for r in results]
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return filename


def generate_best_params_code(results: List[OptimizationResult]):
    """生成最佳参数Python代码"""
    print("\n" + "=" * 100)
    print("💡 最佳参数汇总 (可直接使用)")
    print("=" * 100)
    
    print("\n```python")
    print("# 30策略最佳参数配置")
    print("BEST_PARAMS_30 = {")
    
    # 按得分排序
    sorted_results = sorted(results, key=lambda x: x.score, reverse=True)
    
    for r in sorted_results:
        params_str = json.dumps(r.best_params, ensure_ascii=False)
        print(f"    '{r.strategy_name}': {params_str},  # 得分: {r.score:.2f}, 收益: {r.return_pct:+.2f}%")
    
    print("}")
    print("```")


def main():
    print("=" * 100)
    print("🚀 30策略批量参数优化系统")
    print("=" * 100)
    
    # 生成数据
    print("\n📊 生成测试数据...")
    data = generate_mock_data(days=500)
    print(f"   数据条数: {len(data)}")
    print(f"   日期范围: {data.index[0].date()} ~ {data.index[-1].date()}")
    
    # 获取参数网格
    param_grids = get_strategy_param_grids()
    print(f"\n📋 策略数量: {len(param_grids)}")
    
    # 计算总参数组合数
    total_combinations = sum(len(grid) for grid in param_grids.values())
    print(f"   总参数组合: {total_combinations}")
    
    # 优化所有策略
    print("\n🔍 开始批量优化...")
    print("-" * 100)
    
    results = []
    
    for strategy_name, param_grid in param_grids.items():
        print(f"\n📈 优化 {strategy_name}... ({len(param_grid)} 组参数)")
        result = optimize_strategy(data, strategy_name, param_grid)
        results.append(result)
        print(f"   最佳得分: {result.score:.2f} | 收益: {result.return_pct:+.2f}%")
    
    # 打印报告
    print_optimization_report(results)
    print_strategy_details(results)
    
    # 保存结果
    filename = save_results(results)
    print(f"\n💾 优化结果已保存: {filename}")
    
    # 生成最佳参数代码
    generate_best_params_code(results)
    
    # 快速使用示例
    print("\n" + "=" * 100)
    print("📝 快速使用示例")
    print("=" * 100)
    
    best = max(results, key=lambda x: x.score)
    print(f"\n# 使用全场最佳策略: {best.strategy_name}")
    print(f"signals = generate_strategy(")
    print(f"    data=data,")
    print(f"    strategy_name='{best.strategy_name}',")
    for k, v in best.best_params.items():
        if isinstance(v, str):
            print(f"    {k}='{v}',")
        else:
            print(f"    {k}={v},")
    print(f")")
    
    print("\n" + "=" * 100)
    print("✅ 30策略批量优化完成！")
    print("=" * 100)


if __name__ == "__main__":
    main()
