#!/usr/bin/env python3
"""
策略组合优化器

基于马科维茨投资组合理论，对30个策略进行组合优化
"""
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
import json

import pandas as pd
import numpy as np
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.strategies.lib import generate_strategy
from brain.backtest import BacktestEngine


@dataclass
class PortfolioConfig:
    """组合配置"""
    name: str
    weights: Dict[str, float]
    strategies: List[str]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'weights': self.weights,
            'strategies': self.strategies,
            'expected_return': self.expected_return,
            'volatility': self.volatility,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'win_rate': self.win_rate
        }


# 30策略最佳参数 (从优化结果导入)
BEST_PARAMS_30 = {
    'bollinger': {"period": 15, "std_dev": 2.5},
    'atr_breakout': {"period": 14, "multiplier": 2.0},
    'donchian': {"period": 20},
    'awesome_oscillator': {"short_period": 5, "long_period": 34},
    'adx': {"period": 14, "threshold": 20.0},
    'keltner_channel': {"period": 20, "atr_multiplier": 2.0},
    'ichimoku': {"tenkan_period": 9, "kijun_period": 26, "senkou_b_period": 52},
    'williams_r': {"period": 14, "upper": -20, "lower": -80},
    'stochastic': {"k_period": 14, "d_period": 3, "overbought": 80, "oversold": 20},
    'vortex_indicator': {"period": 20},
    'dual_ma': {"fast": 5, "slow": 20, "ma_type": "sma"},
    'momentum': {"period": 30},
    'volume_price': {"period": 10},
    'rsi': {"period": 14, "overbought": 80, "oversold": 20},
    'aroon': {"period": 25},
    'alligator': {"jaw_period": 13, "teeth_period": 8, "lips_period": 5},
    'chaikin_money_flow': {"period": 30},
    'ultimate_oscillator': {"short_period": 7, "medium_period": 14, "long_period": 28},
    'tsi': {"long_period": 20, "short_period": 10},
    'cci': {"period": 14, "upper": 150, "lower": -150},
    'macd': {"fast": 8, "slow": 21, "signal": 5},
    'trix': {"period": 20, "signal_period": 9},
    'mfi': {"period": 10, "overbought": 80, "oversold": 20},
    'rate_of_change': {"period": 20},
    'vwap': {"period": 50},
    'obv': {},
    'parabolic_sar': {"af_start": 0.03, "af_max": 0.3},
    'kdj': {"n": 9, "m1": 5, "m2": 5},
    'heikin_ashi': {},
    'supertrend': {},
}


def generate_test_data(days=500, seed=42):
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


def get_strategy_returns(data: pd.DataFrame, strategy_name: str, params: Dict) -> pd.Series:
    """获取策略的每日收益序列"""
    try:
        signals = generate_strategy(data, strategy_name, **params)
        
        if signals.abs().sum() == 0:
            return pd.Series(0, index=data.index)
        
        engine = BacktestEngine(
            initial_cash=100000,
            commission_rate=0.00025,
            engine_type="ashare"
        )
        
        result = engine.run(data, signals, symbol="TEST")
        
        # 计算每日权益变化
        equity_curve = result['equity_curve']
        returns = equity_curve.pct_change().fillna(0)
        
        return returns
    except:
        return pd.Series(0, index=data.index)


def calculate_portfolio_metrics(weights: np.ndarray, 
                               returns_df: pd.DataFrame,
                               cov_matrix: pd.DataFrame) -> Tuple[float, float, float]:
    """计算组合指标"""
    # 预期收益 (加权平均)
    portfolio_return = np.sum(returns_df.mean() * weights) * 252
    
    # 波动率
    portfolio_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))) * np.sqrt(252)
    
    # 夏普比率 (假设无风险利率为0)
    sharpe = portfolio_return / portfolio_std if portfolio_std != 0 else 0
    
    return portfolio_return, portfolio_std, sharpe


def optimize_sharpe(returns_df: pd.DataFrame, 
                   cov_matrix: pd.DataFrame,
                   bounds: Tuple = (0.0, 0.3)) -> np.ndarray:
    """优化夏普比率"""
    n = len(returns_df.columns)
    
    def neg_sharpe(weights):
        _, _, sharpe = calculate_portfolio_metrics(weights, returns_df, cov_matrix)
        return -sharpe
    
    constraints = {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
    bounds_list = [bounds] * n
    x0 = np.array([1/n] * n)
    
    result = minimize(
        neg_sharpe, x0,
        method='SLSQP',
        bounds=bounds_list,
        constraints=constraints
    )
    
    return result.x


def optimize_return(returns_df: pd.DataFrame, 
                   cov_matrix: pd.DataFrame,
                   target_volatility: float = 0.15) -> np.ndarray:
    """在给定波动率约束下最大化收益"""
    n = len(returns_df.columns)
    
    def neg_return(weights):
        ret, _, _ = calculate_portfolio_metrics(weights, returns_df, cov_matrix)
        return -ret
    
    def volatility_constraint(weights):
        _, vol, _ = calculate_portfolio_metrics(weights, returns_df, cov_matrix)
        return target_volatility - vol
    
    constraints = [
        {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
        {'type': 'ineq', 'fun': volatility_constraint}
    ]
    bounds_list = [(0.0, 0.4)] * n
    x0 = np.array([1/n] * n)
    
    result = minimize(
        neg_return, x0,
        method='SLSQP',
        bounds=bounds_list,
        constraints=constraints
    )
    
    return result.x


def optimize_min_volatility(returns_df: pd.DataFrame, 
                           cov_matrix: pd.DataFrame,
                           target_return: float = 0.10) -> np.ndarray:
    """在给定收益约束下最小化波动率"""
    n = len(returns_df.columns)
    
    def portfolio_volatility(weights):
        _, vol, _ = calculate_portfolio_metrics(weights, returns_df, cov_matrix)
        return vol
    
    def return_constraint(weights):
        ret, _, _ = calculate_portfolio_metrics(weights, returns_df, cov_matrix)
        return ret - target_return
    
    constraints = [
        {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
        {'type': 'ineq', 'fun': return_constraint}
    ]
    bounds_list = [(0.0, 0.4)] * n
    x0 = np.array([1/n] * n)
    
    result = minimize(
        portfolio_volatility, x0,
        method='SLSQP',
        bounds=bounds_list,
        constraints=constraints
    )
    
    return result.x


def equal_weight_portfolio(n: int) -> np.ndarray:
    """等权重组合"""
    return np.array([1/n] * n)


def risk_parity_portfolio(cov_matrix: pd.DataFrame) -> np.ndarray:
    """风险平价组合"""
    inv_vol = 1 / np.sqrt(np.diag(cov_matrix))
    weights = inv_vol / np.sum(inv_vol)
    return weights


def backtest_portfolio(data: pd.DataFrame, 
                      weights: np.ndarray,
                      strategies: List[str],
                      params_dict: Dict) -> Dict:
    """回测组合策略"""
    combined_signals = pd.Series(0.0, index=data.index)
    
    for strategy, weight in zip(strategies, weights):
        if weight > 0.01:  # 只考虑权重大于1%的策略
            params = params_dict.get(strategy, {})
            try:
                signals = generate_strategy(data, strategy, **params)
                combined_signals += signals * weight
            except:
                pass
    
    # 信号归一化
    combined_signals = np.sign(combined_signals)
    
    engine = BacktestEngine(
        initial_cash=100000,
        commission_rate=0.00025,
        engine_type="ashare"
    )
    
    return engine.run(data, combined_signals, symbol="PORTFOLIO")


def create_efficient_frontier(returns_df: pd.DataFrame, 
                              cov_matrix: pd.DataFrame,
                              n_points: int = 20) -> List[Tuple[float, float]]:
    """生成有效前沿"""
    returns_range = np.linspace(
        returns_df.mean().min() * 252,
        returns_df.mean().max() * 252,
        n_points
    )
    
    efficient_portfolios = []
    
    for target in returns_range:
        try:
            weights = optimize_min_volatility(returns_df, cov_matrix, target)
            ret, vol, _ = calculate_portfolio_metrics(weights, returns_df, cov_matrix)
            efficient_portfolios.append((vol, ret))
        except:
            pass
    
    return efficient_portfolios


def main():
    print("=" * 100)
    print("🚀 策略组合优化器 (马科维茨投资组合理论)")
    print("=" * 100)
    
    # 选择前15个表现最好的策略
    top_strategies = [
        'bollinger', 'atr_breakout', 'donchian', 'awesome_oscillator',
        'adx', 'keltner_channel', 'ichimoku', 'williams_r', 'stochastic',
        'vortex_indicator', 'dual_ma', 'momentum', 'volume_price',
        'rsi', 'aroon'
    ]
    
    print(f"\n📊 选择策略: {len(top_strategies)} 个")
    for i, s in enumerate(top_strategies, 1):
        print(f"   {i:2d}. {s}")
    
    # 生成数据
    print("\n📈 生成测试数据...")
    data = generate_test_data(days=500)
    
    # 获取各策略收益序列
    print("\n🔍 计算策略收益序列...")
    returns_dict = {}
    
    for strategy in top_strategies:
        params = BEST_PARAMS_30.get(strategy, {})
        returns = get_strategy_returns(data, strategy, params)
        returns_dict[strategy] = returns
        print(f"   {strategy}: 年化收益 = {returns.mean()*252*100:+.2f}%")
    
    returns_df = pd.DataFrame(returns_dict).dropna()
    
    # 计算协方差矩阵
    cov_matrix = returns_df.cov() * 252
    
    print("\n" + "-" * 100)
    print("📊 构建组合...")
    print("-" * 100)
    
    # 1. 最大夏普比率组合
    print("\n1️⃣ 优化夏普比率...")
    weights_sharpe = optimize_sharpe(returns_df, cov_matrix, bounds=(0.0, 0.25))
    
    # 2. 给定波动率下最大收益
    print("2️⃣ 给定波动率(15%)下最大化收益...")
    weights_return = optimize_return(returns_df, cov_matrix, target_volatility=0.15)
    
    # 3. 给定收益下最小波动率
    print("3️⃣ 给定收益(10%)下最小化波动率...")
    weights_min_vol = optimize_min_volatility(returns_df, cov_matrix, target_return=0.10)
    
    # 4. 等权重
    print("4️⃣ 等权重组合...")
    weights_equal = equal_weight_portfolio(len(top_strategies))
    
    # 5. 风险平价
    print("5️⃣ 风险平价组合...")
    weights_risk_parity = risk_parity_portfolio(cov_matrix)
    
    # 回测所有组合
    print("\n" + "=" * 100)
    print("🧪 回测组合表现")
    print("=" * 100)
    
    portfolios = {
        '最大夏普': weights_sharpe,
        '高收益(15%波动)': weights_return,
        '低风险(10%收益)': weights_min_vol,
        '等权重': weights_equal,
        '风险平价': weights_risk_parity,
    }
    
    results = []
    
    for name, weights in portfolios.items():
        result = backtest_portfolio(data, weights, top_strategies, BEST_PARAMS_30)
        results.append((name, result, weights))
        
        print(f"\n📌 {name}")
        print("-" * 60)
        print(f"   收益率: {result['return_pct']:>+8.2f}%")
        print(f"   最大回撤: {result['max_drawdown']:>7.2f}%")
        print(f"   胜率: {result['win_rate']:>9.1f}%")
        print(f"   交易次数: {result['total_trades']:>5}")
        
        # 显示权重前3
        weights_dict = {s: w for s, w in zip(top_strategies, weights) if w > 0.01}
        sorted_weights = sorted(weights_dict.items(), key=lambda x: x[1], reverse=True)[:3]
        print(f"   主要策略: {', '.join([f'{s}({w*100:.1f}%)' for s, w in sorted_weights])}")
    
    # 生成报告
    print("\n" + "=" * 100)
    print("📋 组合配置详情")
    print("=" * 100)
    
    for name, result, weights in results:
        print(f"\n🎯 {name}")
        print("-" * 80)
        print("策略权重分配:")
        for s, w in zip(top_strategies, weights):
            if w > 0.005:  # 显示权重大于0.5%的
                bar = "█" * int(w * 50)
                print(f"  {s:20s} {bar:50s} {w*100:5.2f}%")
    
    # Python代码生成
    print("\n" + "=" * 100)
    print("💡 推荐组合配置 (Python代码)")
    print("=" * 100)
    
    print("\n```python")
    print("# 推荐策略组合配置")
    print("# 基于马科维茨投资组合优化")
    print()
    print("RECOMMENDED_PORTFOLIOS = {")
    
    for name, result, weights in results:
        weights_dict = {s: round(w, 4) for s, w in zip(top_strategies, weights) if w > 0.01}
        print(f"    '{name}': {{")
        for s, w in sorted(weights_dict.items(), key=lambda x: x[1], reverse=True):
            print(f"        '{s}': {w},")
        print(f"    }},")
    
    print("}")
    print()
    print("# 使用方法:")
    print("# portfolio = RECOMMENDED_PORTFOLIOS['最大夏普']")
    print("# signals = combined_strategy(data, portfolio)")
    print("```")
    
    # 保存结果
    output = {
        'timestamp': str(pd.Timestamp.now()),
        'strategies': top_strategies,
        'portfolios': {
            name: {
                'weights': {s: float(w) for s, w in zip(top_strategies, weights) if w > 0.01},
                'return_pct': float(result['return_pct']),
                'max_drawdown': float(result['max_drawdown']),
                'win_rate': float(result['win_rate']),
                'total_trades': int(result['total_trades'])
            }
            for name, result, weights in results
        }
    }
    
    import os
    os.makedirs('reports', exist_ok=True)
    with open('reports/portfolio_optimization.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 结果已保存: reports/portfolio_optimization.json")
    
    print("\n" + "=" * 100)
    print("✅ 组合优化完成！")
    print("=" * 100)
    
    return results


if __name__ == "__main__":
    main()
