#!/usr/bin/env python3
"""
自适应策略选择器

根据市场环境自动选择最合适的策略

市场状态识别:
1. 趋势市场 (Trending) - 使用趋势策略
2. 震荡市场 (Ranging) - 使用均值回归策略
3. 高波动 (High Volatility) - 使用波动率策略
4. 低波动 (Low Volatility) - 使用突破策略

动态调整:
- 定期评估各策略近期表现
- 自动切换到表现最好的策略
- 组合权重动态调整
"""
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.strategies.lib import generate_strategy
from brain.backtest import BacktestEngine


class MarketRegime(Enum):
    """市场状态"""
    TRENDING_UP = "上涨趋势"
    TRENDING_DOWN = "下跌趋势"
    RANGING = "震荡区间"
    HIGH_VOLATILITY = "高波动"
    LOW_VOLATILITY = "低波动"
    UNKNOWN = "未知"


@dataclass
class StrategyPerformance:
    """策略表现"""
    strategy_name: str
    recent_return: float
    win_rate: float
    sharpe: float
    max_dd: float
    score: float


class MarketRegimeDetector:
    """市场状态检测器"""
    
    @staticmethod
    def detect(data: pd.DataFrame, lookback: int = 60) -> MarketRegime:
        """检测当前市场状态"""
        if len(data) < lookback:
            return MarketRegime.UNKNOWN
        
        recent = data.tail(lookback)
        close = recent['close']
        
        # 计算指标
        returns = close.pct_change().dropna()
        volatility = returns.std() * np.sqrt(252) * 100  # 年化波动率
        
        # 趋势强度 (ADX近似)
        sma_short = close.rolling(10).mean().iloc[-1]
        sma_long = close.rolling(30).mean().iloc[-1]
        trend_strength = abs(sma_short - sma_long) / close.iloc[-1] * 100
        
        # 价格位置 (布林带近似)
        bb_upper = close.rolling(20).mean().iloc[-1] + 2 * close.rolling(20).std().iloc[-1]
        bb_lower = close.rolling(20).mean().iloc[-1] - 2 * close.rolling(20).std().iloc[-1]
        price_position = (close.iloc[-1] - bb_lower) / (bb_upper - bb_lower)
        
        # 判断市场状态
        if volatility > 40:
            return MarketRegime.HIGH_VOLATILITY
        elif volatility < 15:
            return MarketRegime.LOW_VOLATILITY
        elif trend_strength > 5:
            if sma_short > sma_long:
                return MarketRegime.TRENDING_UP
            else:
                return MarketRegime.TRENDING_DOWN
        else:
            return MarketRegime.RANGING


class AdaptiveStrategySelector:
    """自适应策略选择器"""
    
    def __init__(self, data: pd.DataFrame):
        self.data = data
        self.regime_detector = MarketRegimeDetector()
        
        # 策略分类
        self.strategy_categories = {
            MarketRegime.TRENDING_UP: [
                'atr_breakout', 'donchian', 'awesome_oscillator',
                'ichimoku', 'vortex_indicator', 'dual_ma'
            ],
            MarketRegime.TRENDING_DOWN: [
                'atr_breakout', 'donchian', 'ichimoku',
                'vortex_indicator', 'adx'
            ],
            MarketRegime.RANGING: [
                'bollinger', 'rsi', 'keltner_channel',
                'williams_r', 'stochastic', 'aroon'
            ],
            MarketRegime.HIGH_VOLATILITY: [
                'atr_breakout', 'bollinger', 'keltner_channel',
                'donchian', 'supertrend'
            ],
            MarketRegime.LOW_VOLATILITY: [
                'bollinger', 'awesome_oscillator', 'adx',
                'volume_price', 'momentum'
            ],
            MarketRegime.UNKNOWN: [
                'bollinger', 'atr_breakout', 'awesome_oscillator'
            ]
        }
        
        # 最佳参数 (从之前的优化)
        self.best_params = {
            'bollinger': {'period': 15, 'std_dev': 2.5},
            'atr_breakout': {'period': 14, 'multiplier': 2.0},
            'donchian': {'period': 20},
            'awesome_oscillator': {'short_period': 5, 'long_period': 34},
            'adx': {'period': 14, 'threshold': 20.0},
            'keltner_channel': {'period': 20, 'atr_multiplier': 2.0},
            'ichimoku': {'tenkan_period': 9, 'kijun_period': 26, 'senkou_b_period': 52},
            'williams_r': {'period': 14, 'upper': -20, 'lower': -80},
            'stochastic': {'k_period': 14, 'd_period': 3, 'overbought': 80, 'oversold': 20},
            'vortex_indicator': {'period': 20},
            'dual_ma': {'fast': 5, 'slow': 20, 'ma_type': 'sma'},
            'momentum': {'period': 30},
            'volume_price': {'period': 10},
            'rsi': {'period': 14, 'overbought': 80, 'oversold': 20},
            'aroon': {'period': 25},
            'supertrend': {'period': 14, 'multiplier': 2.0},
        }
        
        self.performance_history: Dict[str, List[StrategyPerformance]] = {}
    
    def evaluate_strategy(self, strategy_name: str, 
                         data: pd.DataFrame) -> Optional[StrategyPerformance]:
        """评估策略表现"""
        try:
            params = self.best_params.get(strategy_name, {})
            signals = generate_strategy(data, strategy_name, **params)
            
            if signals.abs().sum() == 0:
                return None
            
            engine = BacktestEngine(
                initial_cash=100000,
                commission_rate=0.00025,
                engine_type="ashare"
            )
            
            result = engine.run(data, signals, symbol="TEST")
            
            sharpe = result['return_pct'] / abs(result['max_drawdown']) if result['max_drawdown'] != 0 else 0
            
            score = (
                result['return_pct'] * 0.4 +
                sharpe * 25 +
                result['win_rate'] * 0.2 +
                (100 - min(result['total_trades'] / 50, 1.0) * 10) * 0.1
            )
            
            return StrategyPerformance(
                strategy_name=strategy_name,
                recent_return=result['return_pct'],
                win_rate=result['win_rate'],
                sharpe=sharpe,
                max_dd=result['max_drawdown'],
                score=score
            )
            
        except Exception as e:
            return None
    
    def select_strategies(self, lookback: int = 60, top_n: int = 5) -> List[Tuple[str, float]]:
        """
        选择当前最适合的策略
        
        Returns:
            List of (strategy_name, weight) tuples
        """
        # 检测市场状态
        regime = self.regime_detector.detect(self.data, lookback)
        print(f"\n📊 当前市场状态: {regime.value}")
        
        # 获取适合该状态的策略
        candidate_strategies = self.strategy_categories.get(regime, [])
        print(f"   候选策略: {len(candidate_strategies)} 个")
        
        # 评估候选策略
        recent_data = self.data.tail(lookback)
        performances = []
        
        print(f"\n   评估策略表现...")
        for strategy in candidate_strategies:
            perf = self.evaluate_strategy(strategy, recent_data)
            if perf:
                performances.append(perf)
                print(f"   • {strategy:20s}: 收益={perf.recent_return:+.2f}%, 得分={perf.score:.2f}")
        
        if not performances:
            print(f"   ⚠️ 无有效策略，使用默认")
            return [('bollinger', 0.5), ('atr_breakout', 0.5)]
        
        # 排序并选择top N
        performances.sort(key=lambda x: x.score, reverse=True)
        top_performers = performances[:top_n]
        
        # 计算权重 (softmax)
        scores = np.array([p.score for p in top_performers])
        scores = scores - scores.min() + 1  # 确保正值
        weights = np.exp(scores) / np.sum(np.exp(scores))
        
        selected = [(p.strategy_name, w) for p, w in zip(top_performers, weights)]
        
        print(f"\n   🎯 选中策略 (Top {len(selected)}):")
        for name, weight in selected:
            perf = next(p for p in performances if p.strategy_name == name)
            print(f"      {name:20s}: 权重={weight*100:5.1f}%, 收益={perf.recent_return:+.2f}%")
        
        return selected
    
    def generate_combined_signals(self, strategies: List[Tuple[str, float]]) -> pd.Series:
        """生成组合信号"""
        combined = pd.Series(0.0, index=self.data.index)
        
        for strategy_name, weight in strategies:
            params = self.best_params.get(strategy_name, {})
            try:
                signals = generate_strategy(self.data, strategy_name, **params)
                combined += signals * weight
            except:
                pass
        
        # 归一化
        combined = np.sign(combined)
        return combined
    
    def backtest_dynamic(self, window_size: int = 60, step_size: int = 30) -> Dict:
        """动态回测 - 定期调整策略"""
        print(f"\n{'='*80}")
        print("🔄 动态策略调整回测")
        print(f"{'='*80}")
        print(f"   窗口大小: {window_size} 天")
        print(f"   调整步长: {step_size} 天")
        
        all_signals = pd.Series(0, index=self.data.index)
        regime_history = []
        selection_history = []
        
        # 滑动窗口
        for start in range(window_size, len(self.data), step_size):
            end = min(start + step_size, len(self.data))
            
            train_data = self.data.iloc[start-window_size:start]
            test_data = self.data.iloc[start:end]
            
            print(f"\n   周期 {start-window_size} ~ {end}:")
            
            # 检测市场状态
            regime = self.regime_detector.detect(train_data, window_size)
            regime_history.append((self.data.index[start], regime))
            
            # 选择策略
            selected = self.select_strategies(lookback=window_size, top_n=3)
            selection_history.append((self.data.index[start], selected))
            
            # 生成信号
            for i in range(start, end):
                if i < len(self.data):
                    all_signals.iloc[i] = self._generate_signal_at(i, selected)
        
        # 回测
        engine = BacktestEngine(
            initial_cash=100000,
            commission_rate=0.00025,
            engine_type="ashare"
        )
        
        result = engine.run(self.data, all_signals, symbol="ADAPTIVE")
        
        return {
            'result': result,
            'regime_history': regime_history,
            'selection_history': selection_history,
            'signals': all_signals
        }
    
    def _generate_signal_at(self, idx: int, 
                           strategies: List[Tuple[str, float]]) -> int:
        """在特定索引生成信号"""
        data_slice = self.data.iloc[:idx+1]
        
        if len(data_slice) < 30:
            return 0
        
        combined_signal = 0.0
        
        for strategy_name, weight in strategies:
            params = self.best_params.get(strategy_name, {})
            try:
                signals = generate_strategy(data_slice, strategy_name, **params)
                if len(signals) > 0:
                    combined_signal += signals.iloc[-1] * weight
            except:
                pass
        
        return int(np.sign(combined_signal))


def generate_test_data(days=600, seed=42):
    """生成测试数据 (包含不同市场状态)"""
    np.random.seed(seed)
    dates = pd.date_range(start='2022-01-01', periods=days, freq='B')
    
    # 生成不同状态的数据
    prices = []
    current_price = 100
    
    for i in range(days):
        # 模拟市场状态切换
        if i < days * 0.2:  # 20% 上涨
            drift = 0.001
            vol = 0.015
        elif i < days * 0.4:  # 20% 震荡
            drift = 0.0
            vol = 0.012
        elif i < days * 0.6:  # 20% 下跌
            drift = -0.0005
            vol = 0.018
        elif i < days * 0.8:  # 20% 高波动
            drift = 0.0
            vol = 0.025
        else:  # 20% 低波动
            drift = 0.0003
            vol = 0.008
        
        ret = np.random.normal(drift, vol)
        current_price *= (1 + ret)
        prices.append(current_price)
    
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


def main():
    print("=" * 100)
    print("🎯 自适应策略选择器")
    print("=" * 100)
    
    # 生成数据
    print("\n📊 生成测试数据 (包含多种市场状态)...")
    data = generate_test_data(days=600)
    
    # 创建选择器
    selector = AdaptiveStrategySelector(data)
    
    # 测试单次选择
    print(f"\n{'='*80}")
    print("📋 单次策略选择测试")
    print(f"{'='*80}")
    
    selected = selector.select_strategies(lookback=60, top_n=5)
    
    # 生成组合信号
    print(f"\n{'='*80}")
    print("📈 生成组合信号并回测")
    print(f"{'='*80}")
    
    signals = selector.generate_combined_signals(selected)
    
    engine = BacktestEngine(
        initial_cash=100000,
        commission_rate=0.00025,
        engine_type="ashare"
    )
    
    result = engine.run(data, signals, symbol="ADAPTIVE")
    
    print(f"\n组合回测结果:")
    print(f"   收益率: {result['return_pct']:+.2f}%")
    print(f"   最大回撤: {result['max_drawdown']:.2f}%")
    print(f"   胜率: {result['win_rate']:.1f}%")
    print(f"   交易次数: {result['total_trades']}")
    
    # 动态回测
    print(f"\n{'='*80}")
    print("🔄 动态调整回测 (定期重新选择策略)")
    print(f"{'='*80}")
    
    dynamic_result = selector.backtest_dynamic(window_size=60, step_size=30)
    
    print(f"\n动态调整回测结果:")
    print(f"   收益率: {dynamic_result['result']['return_pct']:+.2f}%")
    print(f"   最大回撤: {dynamic_result['result']['max_drawdown']:.2f}%")
    print(f"   胜率: {dynamic_result['result']['win_rate']:.1f}%")
    print(f"   交易次数: {dynamic_result['result']['total_trades']}")
    
    # 显示市场状态历史
    print(f"\n市场状态变化:")
    for date, regime in dynamic_result['regime_history'][:5]:
        print(f"   {date.date()}: {regime.value}")
    
    print("\n" + "=" * 100)
    print("✅ 自适应策略选择完成！")
    print("=" * 100)


if __name__ == "__main__":
    main()
