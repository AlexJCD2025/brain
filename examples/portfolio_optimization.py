#!/usr/bin/env python3
"""
B. 策略组合优化 - 马科维茨现代投资组合理论

优化目标:
1. 最大化夏普比率
2. 最小化组合波动率
3. 给定目标收益下的最小风险
"""
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
import itertools

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.strategies.lib import generate_strategy
from brain.backtest import BacktestEngine


@dataclass
class PortfolioResult:
    """组合优化结果"""
    weights: Dict[str, float]
    return_pct: float
    volatility: float  # 收益波动率
    sharpe_ratio: float
    max_drawdown: float
    calmar_ratio: float  # 收益/最大回撤


def generate_data(days=500, seed=42):
    """生成测试数据"""
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


def get_strategy_signals(data: pd.DataFrame) -> Dict[str, pd.Series]:
    """获取所有策略的信号"""
    strategies = {
        'bollinger': {'period': 15, 'std_dev': 2.5},
        'atr_breakout': {'period': 14, 'multiplier': 2.0},
        'donchian': {'period': 20},
        'dual_ma': {'fast': 5, 'slow': 20, 'ma_type': 'sma'},
        'momentum': {'period': 30},
    }
    
    signals = {}
    for name, params in strategies.items():
        try:
            sig = generate_strategy(data, name, **params)
            signals[name] = sig
        except Exception as e:
            print(f"   生成 {name} 信号失败: {e}")
    
    return signals


def run_backtest_get_equity(data: pd.DataFrame, signals: pd.Series) -> pd.Series:
    """运行回测并返回权益曲线"""
    try:
        engine = BacktestEngine(
            initial_cash=100000,
            commission_rate=0.00025,
            engine_type="ashare"
        )
        
        result = engine.run(data, signals, symbol="TEST")
        
        # 获取权益曲线
        equity_curve = engine.get_equity_curve()
        if len(equity_curve) == 0:
            return pd.Series([100000] * len(data), index=data.index)
        
        # 重采样到与data相同的索引
        equity_curve = equity_curve.reindex(data.index, method='ffill').fillna(100000)
        return equity_curve
        
    except Exception as e:
        print(f"   回测失败: {e}")
        return pd.Series([100000] * len(data), index=data.index)


def calculate_strategy_returns(data: pd.DataFrame, signals_dict: Dict[str, pd.Series]) -> pd.DataFrame:
    """计算每个策略的日收益率"""
    returns_df = pd.DataFrame(index=data.index)
    
    for name, signals in signals_dict.items():
        print(f"   计算 {name} 收益率...")
        equity = run_backtest_get_equity(data, signals)
        returns = equity.pct_change().fillna(0)
        returns_df[name] = returns
    
    return returns_df


def optimize_portfolio(returns_df: pd.DataFrame, risk_free_rate: float = 0.02) -> List[PortfolioResult]:
    """
    使用马科维茨理论优化组合
    
    策略:
    1. 等权重组合
    2. 风险平价组合
    3. 最大夏普比率组合
    4. 最小方差组合
    """
    strategies = returns_df.columns.tolist()
    n_strategies = len(strategies)
    
    results = []
    
    # 1. 等权重组合
    print("\n   计算等权重组合...")
    equal_weights = {s: 1.0 / n_strategies for s in strategies}
    results.append(evaluate_portfolio(returns_df, equal_weights, risk_free_rate, "等权重"))
    
    # 2. 风险平价组合 (简化版: 按波动率倒数加权)
    print("   计算风险平价组合...")
    volatilities = returns_df.std()
    inv_vol = 1.0 / (volatilities + 1e-6)
    risk_parity_weights = {s: inv_vol[s] / inv_vol.sum() for s in strategies}
    results.append(evaluate_portfolio(returns_df, risk_parity_weights, risk_free_rate, "风险平价"))
    
    # 3. 随机搜索最大夏普比率
    print("   搜索最大夏普比率组合...")
    best_sharpe = None
    best_sharpe_value = -np.inf
    
    np.random.seed(42)
    for _ in range(1000):  # 随机搜索1000次
        # 生成随机权重
        weights = np.random.dirichlet(np.ones(n_strategies))
        weights_dict = {s: weights[i] for i, s in enumerate(strategies)}
        
        portfolio_return = sum(weights_dict[s] * returns_df[s].mean() * 252 for s in strategies)
        portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(returns_df.cov() * 252, weights)))
        sharpe = (portfolio_return - risk_free_rate) / (portfolio_vol + 1e-6)
        
        if sharpe > best_sharpe_value:
            best_sharpe_value = sharpe
            best_sharpe = weights_dict
    
    if best_sharpe:
        results.append(evaluate_portfolio(returns_df, best_sharpe, risk_free_rate, "最大夏普"))
    
    # 4. 最小方差组合
    print("   计算最小方差组合...")
    # 简化: 使用波动率最小的策略
    min_vol_strategy = volatilities.idxmin()
    min_var_weights = {s: 1.0 if s == min_vol_strategy else 0.0 for s in strategies}
    results.append(evaluate_portfolio(returns_df, min_var_weights, risk_free_rate, "最小方差"))
    
    # 5. 动量加权组合 (近期表现好的给更高权重)
    print("   计算动量加权组合...")
    recent_returns = returns_df.iloc[-60:].mean()  # 最近60天
    momentum_weights = {s: max(0, recent_returns[s]) for s in strategies}
    total_weight = sum(momentum_weights.values())
    if total_weight > 0:
        momentum_weights = {s: w / total_weight for s, w in momentum_weights.items()}
    else:
        momentum_weights = equal_weights
    results.append(evaluate_portfolio(returns_df, momentum_weights, risk_free_rate, "动量加权"))
    
    return results


def evaluate_portfolio(returns_df: pd.DataFrame, weights: Dict[str, float], 
                      risk_free_rate: float, name: str) -> PortfolioResult:
    """评估组合表现"""
    strategies = list(weights.keys())
    
    # 组合日收益率
    portfolio_returns = sum(weights[s] * returns_df[s] for s in strategies)
    
    # 年化收益
    annual_return = portfolio_returns.mean() * 252 * 100
    
    # 年化波动率
    annual_vol = portfolio_returns.std() * np.sqrt(252) * 100
    
    # 夏普比率
    sharpe = (annual_return - risk_free_rate * 100) / (annual_vol + 1e-6)
    
    # 最大回撤
    cumulative = (1 + portfolio_returns).cumprod()
    peak = cumulative.expanding().max()
    drawdown = (cumulative - peak) / peak
    max_dd = drawdown.min() * 100
    
    # Calmar比率
    calmar = annual_return / abs(max_dd) if max_dd != 0 else 0
    
    return PortfolioResult(
        weights=weights,
        return_pct=annual_return,
        volatility=annual_vol,
        sharpe_ratio=sharpe,
        max_drawdown=max_dd,
        calmar_ratio=calmar
    )


def print_portfolio_results(results: List[PortfolioResult]):
    """打印组合优化结果"""
    print("\n" + "=" * 100)
    print("📊 组合优化结果")
    print("=" * 100)
    
    print(f"\n{'组合类型':<12} {'年化收益':<10} {'波动率':<10} {'夏普比率':<10} {'最大回撤':<10} {'Calmar':<8}")
    print("-" * 100)
    
    for r in results:
        name = list(r.weights.keys())[0] if len(set(r.weights.values())) == 1 else "混合"
        if len(set(r.weights.values())) == 1:
            name = "等权重"
        elif max(r.weights.values()) > 0.8:
            name = f"主导:{max(r.weights, key=r.weights.get)}"
        
        print(f"{name:<12} {r.return_pct:>+8.2f}% {r.volatility:>8.2f}% {r.sharpe_ratio:>8.2f} {r.max_drawdown:>8.2f}% {r.calmar_ratio:>6.2f}")
    
    print("-" * 100)
    
    # 找出最佳组合
    best_sharpe = max(results, key=lambda x: x.sharpe_ratio)
    best_return = max(results, key=lambda x: x.return_pct)
    best_calmar = max(results, key=lambda x: x.calmar_ratio)
    
    print("\n🏆 最佳组合:")
    print(f"   • 最大夏普比率: {best_sharpe.sharpe_ratio:.2f}")
    print(f"     权重: {best_sharpe.weights}")
    print(f"   • 最高收益: {best_return.return_pct:+.2f}%")
    print(f"     权重: {best_return.weights}")
    print(f"   • 最佳Calmar: {best_calmar.calmar_ratio:.2f}")
    print(f"     权重: {best_calmar.weights}")


def main():
    print("=" * 100)
    print("🎯 B. 策略组合优化 - 马科维茨现代投资组合理论")
    print("=" * 100)
    
    # 生成数据
    print("\n📊 生成测试数据...")
    data = generate_data(days=500)
    print(f"   数据条数: {len(data)}")
    
    # 获取策略信号
    print("\n📈 生成策略信号...")
    signals_dict = get_strategy_signals(data)
    print(f"   成功生成 {len(signals_dict)} 个策略信号")
    
    # 计算策略收益率
    print("\n💰 计算策略收益率...")
    returns_df = calculate_strategy_returns(data, signals_dict)
    
    # 显示策略统计
    print("\n📊 策略收益率统计:")
    print("-" * 100)
    print(f"{'策略':<15} {'日均收益':<12} {'年化收益':<12} {'波动率':<10} {'夏普':<8}")
    print("-" * 100)
    
    for col in returns_df.columns:
        daily_ret = returns_df[col].mean() * 100
        annual_ret = daily_ret * 252
        vol = returns_df[col].std() * np.sqrt(252) * 100
        sharpe = annual_ret / (vol + 1e-6)
        print(f"{col:<15} {daily_ret:>+9.4f}% {annual_ret:>+9.2f}% {vol:>8.2f}% {sharpe:>6.2f}")
    
    print("-" * 100)
    
    # 优化组合
    print("\n🔍 开始组合优化...")
    results = optimize_portfolio(returns_df)
    
    # 打印结果
    print_portfolio_results(results)
    
    # 相关性分析
    print("\n" + "=" * 100)
    print("🔗 策略相关性分析")
    print("=" * 100)
    
    corr_matrix = returns_df.corr()
    print("\n相关性矩阵:")
    print(corr_matrix.round(2))
    
    # 找出低相关性组合
    print("\n💡 低相关性策略对 (适合组合):")
    for i, col1 in enumerate(corr_matrix.columns):
        for j, col2 in enumerate(corr_matrix.columns):
            if i < j:
                corr = corr_matrix.loc[col1, col2]
                if abs(corr) < 0.3:
                    print(f"   • {col1} - {col2}: {corr:.3f}")
    
    # 最终推荐
    print("\n" + "=" * 100)
    print("💎 最终推荐组合")
    print("=" * 100)
    
    best = max(results, key=lambda x: x.sharpe_ratio)
    
    print(f"\n推荐权重配置 (最大夏普比率):")
    for strategy, weight in sorted(best.weights.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(weight * 50)
        print(f"   {strategy:<15}: {weight*100:>5.1f}% {bar}")
    
    print(f"\n预期表现:")
    print(f"   • 年化收益: {best.return_pct:+.2f}%")
    print(f"   • 年化波动: {best.volatility:.2f}%")
    print(f"   • 夏普比率: {best.sharpe_ratio:.2f}")
    print(f"   • 最大回撤: {best.max_drawdown:.2f}%")
    
    print("\n" + "=" * 100)
    print("✅ 组合优化完成！")
    print("=" * 100)


if __name__ == "__main__":
    main()
