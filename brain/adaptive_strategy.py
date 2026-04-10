#!/usr/bin/env python3
"""
自适应策略系统

根据市场状态自动切换最优策略
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import numpy as np

from brain.market_regime import (
    MarketRegimeDetector, 
    get_strategy_for_regime,
    MarketRegime
)
from brain.strategies.lib import generate_strategy


@dataclass
class AdaptiveSignal:
    """自适应策略信号"""
    signal: int  # -1, 0, 1
    regime: MarketRegime
    strategy_used: str
    confidence: float
    position_size: float


class AdaptiveStrategy:
    """
    自适应策略引擎
    
    根据市场状态自动选择最优策略
    """
    
    def __init__(
        self,
        regime_window: int = 15,  # 更短的窗口，更灵敏
        min_confidence: float = 0.2,  # 更低的置信度阈值
        verbose: bool = False
    ):
        self.regime_detector = MarketRegimeDetector(lookback=regime_window)
        self.min_confidence = min_confidence
        self.verbose = verbose
        
        # 策略参数
        self.strategy_params = {
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
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        生成自适应信号
        
        流程:
        1. 检测当前市场状态
        2. 选择对应策略
        3. 生成交易信号
        4. 应用仓位控制
        
        Args:
            data: 价格数据
        
        Returns:
            Series of signals (-1, 0, 1)
        """
        signals = pd.Series(0.0, index=data.index)
        
        # 滚动检测市场状态并生成信号
        lookback = self.regime_detector.lookback * 2
        
        for i in range(lookback, len(data)):
            chunk = data.iloc[i-lookback:i]
            
            # 检测市场状态
            regime_info = self.regime_detector.detect(chunk)
            
            # 获取策略配置
            strategy_config = get_strategy_for_regime(regime_info.regime)
            strategy_name = strategy_config['primary']
            position_size = strategy_config['position_size']
            
            # 生成信号 - 使用足够的数据重新计算
            params = self.strategy_params.get(strategy_name, {})
            try:
                # 使用全部历史数据生成信号
                strategy_signals = generate_strategy(data.iloc[:i+1], strategy_name, **params)
                raw_signal = strategy_signals.iloc[i]
                
                # 应用仓位控制
                if abs(raw_signal) > 0:
                    adjusted_signal = np.sign(raw_signal) * position_size
                    signals.iloc[i] = adjusted_signal
                else:
                    signals.iloc[i] = 0
                
                # 记录日志
                if self.verbose and i % 20 == 0:
                    print(f"[{data.index[i]}] Regime: {regime_info.regime}, "
                          f"Strategy: {strategy_name}, Signal: {signals.iloc[i]:.2f}")
                
            except Exception as e:
                signals.iloc[i] = 0
        
        return signals
    
    def get_regime_transitions(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        获取市场状态转换历史
        
        Args:
            data: 价格数据
        
        Returns:
            DataFrame with regime transitions
        """
        regimes = []
        lookback = self.regime_detector.lookback * 2
        
        for i in range(lookback, len(data)):
            chunk = data.iloc[i-lookback:i]
            info = self.regime_detector.detect(chunk)
            strategy_config = get_strategy_for_regime(info.regime)
            
            regimes.append({
                'date': data.index[i],
                'close': data['close'].iloc[i],
                'regime': info.regime,
                'trend_score': info.trend_score,
                'volatility': info.volatility,
                'adx': info.adx,
                'confidence': info.confidence,
                'strategy': strategy_config['primary'],
                'position_size': strategy_config['position_size']
            })
        
        df = pd.DataFrame(regimes).set_index('date')
        
        # 标记状态转换点
        df['regime_change'] = df['regime'] != df['regime'].shift(1)
        
        return df
    
    def summarize_regime_periods(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        总结各市场状态期间的表现
        
        Args:
            data: 价格数据
        
        Returns:
            Summary DataFrame
        """
        regime_df = self.get_regime_transitions(data)
        
        summary = []
        
        for regime in regime_df['regime'].unique():
            mask = regime_df['regime'] == regime
            period_data = regime_df[mask]
            
            if len(period_data) < 2:
                continue
            
            # 计算期间收益
            start_price = period_data['close'].iloc[0]
            end_price = period_data['close'].iloc[-1]
            returns = (end_price / start_price - 1) * 100
            
            # 平均指标
            avg_vol = period_data['volatility'].mean()
            avg_adx = period_data['adx'].mean()
            avg_conf = period_data['confidence'].mean()
            
            # 持续天数
            duration = len(period_data)
            
            summary.append({
                'regime': regime,
                'duration_days': duration,
                'return_pct': returns,
                'avg_volatility': avg_vol,
                'avg_adx': avg_adx,
                'avg_confidence': avg_conf,
                'strategy_used': period_data['strategy'].iloc[0]
            })
        
        return pd.DataFrame(summary)


class MultiRegimeStrategy:
    """
    多策略组合 (针对不同市场状态的最优策略组合)
    """
    
    def __init__(self):
        self.regime_detector = MarketRegimeDetector()
        
        # 各状态最优策略 (基于回测结果)
        self.regime_best_strategies = {
            'bull': {
                'strategies': ['ichimoku', 'momentum', 'tsi'],
                'weights': [0.5, 0.3, 0.2]
            },
            'bear': {
                'strategies': ['awesome_oscillator', 'cci', 'aroon'],
                'weights': [0.5, 0.3, 0.2]
            },
            'range': {
                'strategies': ['bollinger', 'rsi', 'williams_r'],
                'weights': [0.4, 0.3, 0.3]
            },
            'high_vol': {
                'strategies': ['atr_breakout', 'donchian', 'keltner_channel'],
                'weights': [0.5, 0.3, 0.2]
            }
        }
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        生成多策略组合信号
        
        根据市场状态加权组合多个策略的信号
        """
        signals = pd.Series(0.0, index=data.index)
        lookback = self.regime_detector.lookback * 2
        
        for i in range(lookback, len(data)):
            chunk = data.iloc[i-lookback:i]
            
            # 检测市场状态
            regime_info = self.regime_detector.detect(chunk)
            regime = regime_info.regime if regime_info.confidence > 0.3 else 'range'
            
            # 获取该状态的策略组合
            config = self.regime_best_strategies.get(regime, self.regime_best_strategies['range'])
            strategies = config['strategies']
            weights = config['weights']
            
            # 计算加权信号
            weighted_signal = 0
            for strategy_name, weight in zip(strategies, weights):
                try:
                    strategy_signals = generate_strategy(
                        chunk, strategy_name, 
                        **self._get_params(strategy_name)
                    )
                    raw_signal = strategy_signals.iloc[-1]
                    weighted_signal += raw_signal * weight
                except:
                    pass
            
            signals.iloc[i] = np.clip(weighted_signal, -1, 1)
        
        return signals
    
    def _get_params(self, strategy_name: str) -> dict:
        """获取策略参数"""
        default_params = {
            'dual_ma': {'fast': 5, 'slow': 20, 'ma_type': 'sma'},
            'macd': {'fast': 8, 'slow': 21, 'signal': 5},
            'rsi': {'period': 14, 'overbought': 80, 'oversold': 20},
            'bollinger': {'period': 15, 'std_dev': 2.5},
            'momentum': {'period': 30},
            'atr_breakout': {'period': 14, 'multiplier': 2.0},
            'donchian': {'period': 20},
            'cci': {'period': 14, 'upper': 150, 'lower': -150},
            'williams_r': {'period': 14, 'upper': -20, 'lower': -80},
            'ichimoku': {'tenkan_period': 9, 'kijun_period': 26, 'senkou_b_period': 52},
            'awesome_oscillator': {'short_period': 5, 'long_period': 34},
            'tsi': {'long_period': 20, 'short_period': 10},
            'keltner_channel': {'period': 20, 'atr_multiplier': 2.0},
            'aroon': {'period': 25},
        }
        return default_params.get(strategy_name, {})


def test_adaptive_strategy():
    """测试自适应策略"""
    print("=" * 100)
    print("🧪 测试自适应策略系统")
    print("=" * 100)
    
    # 生成测试数据 (包含不同市场状态)
    np.random.seed(42)
    n = 300
    
    # 分段模拟不同市场
    # 1-100: 牛市
    bull = 100 * (1 + np.random.normal(0.0015, 0.012, 100)).cumprod()
    # 101-200: 熊市
    bear = bull[-1] * (1 + np.random.normal(-0.001, 0.018, 100)).cumprod()
    # 201-300: 震荡市
    range_base = bear[-1]
    range_prices = range_base + np.cumsum(np.random.normal(0, 0.8, 100))
    
    prices = np.concatenate([bull, bear, range_prices])
    
    data = pd.DataFrame({
        'open': prices * 0.995,
        'high': prices * 1.015,
        'low': prices * 0.985,
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, n)
    }, index=pd.date_range('2024-01-01', periods=n, freq='B'))
    
    # 测试自适应策略
    print("\n1. 测试自适应单策略...")
    adaptive = AdaptiveStrategy(verbose=False)
    
    # 获取状态转换
    regime_df = adaptive.get_regime_transitions(data)
    print(f"   检测到 {regime_df['regime'].nunique()} 种市场状态")
    print(f"   状态分布:")
    print(regime_df['regime'].value_counts())
    
    # 生成信号
    signals = adaptive.generate_signals(data)
    print(f"\n   信号统计:")
    print(f"   买入信号: {(signals > 0).sum()}")
    print(f"   卖出信号: {(signals < 0).sum()}")
    print(f"   持仓天数: {(signals != 0).sum()}")
    
    # 总结各状态期间
    print(f"\n2. 各市场状态期间表现:")
    summary = adaptive.summarize_regime_periods(data)
    print(summary.to_string())
    
    # 测试多策略组合
    print(f"\n3. 测试多策略组合...")
    multi = MultiRegimeStrategy()
    multi_signals = multi.generate_signals(data)
    print(f"   组合信号范围: [{multi_signals.min():.2f}, {multi_signals.max():.2f}]")
    print(f"   平均信号强度: {multi_signals.abs().mean():.2f}")
    
    print("\n" + "=" * 100)
    print("✅ 自适应策略测试完成")
    print("=" * 100)


if __name__ == "__main__":
    test_adaptive_strategy()
