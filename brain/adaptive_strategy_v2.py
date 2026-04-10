#!/usr/bin/env python3
"""
自适应策略系统 V2 - 改进版

改进点:
1. 使用V2市场状态检测器 (多维度确认)
2. 渐进式仓位管理 (非二元切换)
3. 趋势持续性平滑
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import numpy as np

from brain.market_regime_v2 import (
    MarketRegimeDetectorV2,
    get_strategy_for_regime_v2,
    MarketRegime,
    RegimeInfo
)
from brain.strategies.lib import generate_strategy


class AdaptiveStrategyV2:
    """
    改进版自适应策略引擎
    
    特性:
    - 多维度市场状态检测
    - 渐进式仓位管理 (20%-100%)
    - 状态切换平滑 (避免频繁切换)
    """
    
    def __init__(
        self,
        min_data_points: int = 60,
        smooth_factor: float = 0.3,  # 仓位平滑系数
        verbose: bool = False
    ):
        self.regime_detector = MarketRegimeDetectorV2()
        self.min_data_points = min_data_points
        self.smooth_factor = smooth_factor
        self.verbose = verbose
        
        # 状态历史 (用于平滑)
        self.regime_history: List[Tuple[datetime, MarketRegime, float]] = []
        self.prev_position: float = 0.0
        
        # 策略参数
        self.strategy_params = {
            'ichimoku': {'tenkan_period': 9, 'kijun_period': 26, 'senkou_b_period': 52},
            'momentum': {'period': 30},
            'tsi': {'long_period': 20, 'short_period': 10},
            'vwap': {'period': 50},
            'bollinger': {'period': 15, 'std_dev': 2.5},
            'rsi': {'period': 14, 'overbought': 80, 'oversold': 20},
            'keltner_channel': {'period': 20, 'atr_multiplier': 2.0},
            'cci': {'period': 14, 'upper': 150, 'lower': -150},
            'awesome_oscillator': {'short_period': 5, 'long_period': 34},
            'aroon': {'period': 25},
            'atr_breakout': {'period': 14, 'multiplier': 2.0},
            'donchian': {'period': 20},
            'dual_ma': {'fast': 5, 'slow': 20, 'ma_type': 'sma'},
        }
    
    def calculate_position_size(
        self,
        regime: MarketRegime,
        info: RegimeInfo,
        smooth: bool = True
    ) -> float:
        """
        计算仓位大小 (渐进式)
        
        基础仓位由市场状态决定，然后根据以下调整:
        - 置信度 (高置信度 -> 更高仓位)
        - 趋势一致性 (多时间框架一致 -> 更高仓位)
        - 波动率 (高波动 -> 降低仓位)
        
        Returns:
            position_size: 0.0 to 1.0
        """
        # 1. 获取基础仓位范围
        strategy_config = get_strategy_for_regime_v2(regime)
        min_pos, max_pos = strategy_config['position_range']
        
        # 2. 根据置信度调整
        confidence_factor = info.confidence
        
        # 3. 根据趋势一致性调整
        trends = [info.trend_short, info.trend_medium, info.trend_long]
        trend_consistency = 1 - np.std(trends) / (abs(np.mean(trends)) + 0.01)
        trend_consistency = np.clip(trend_consistency, 0, 1)
        
        # 4. 根据波动率调整
        vol_factor = max(0, 1 - info.volatility / 50)  # 波动率>50%时大幅降低
        
        # 5. 根据成交量确认
        vol_confirm = (info.volume_trend + 1) / 2  # 转换为 0-1
        
        # 6. 综合计算
        # 牛市: 趋势一致性更重要
        if regime in [MarketRegime.STRONG_BULL, MarketRegime.BULL]:
            base_position = min_pos + (max_pos - min_pos) * (
                confidence_factor * 0.4 +
                trend_consistency * 0.4 +
                vol_confirm * 0.2
            )
        
        # 熊市: 保守优先
        elif regime in [MarketRegime.STRONG_BEAR, MarketRegime.BEAR]:
            base_position = min_pos + (max_pos - min_pos) * (
                confidence_factor * 0.3 +
                vol_factor * 0.4 +
                (1 - trend_consistency) * 0.3  # 趋势不一致时更保守
            )
        
        # 震荡市: 中等仓位
        else:
            base_position = (min_pos + max_pos) / 2 * (
                confidence_factor * 0.5 +
                vol_factor * 0.5
            )
        
        # 7. 平滑处理 (避免剧烈变化)
        if smooth and self.prev_position is not None:
            smoothed_position = (
                self.prev_position * (1 - self.smooth_factor) +
                base_position * self.smooth_factor
            )
        else:
            smoothed_position = base_position
        
        # 保存当前仓位
        self.prev_position = smoothed_position
        
        return np.clip(smoothed_position, 0.0, 1.0)
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        生成自适应信号 (V2)
        
        流程:
        1. 检测市场状态 (多维度)
        2. 选择策略组合
        3. 计算渐进式仓位
        4. 生成加权信号
        """
        signals = pd.Series(0.0, index=data.index)
        
        # 重置历史
        self.regime_history = []
        self.prev_position = 0.0
        
        # 滚动生成信号
        for i in range(self.min_data_points, len(data)):
            chunk = data.iloc[:i+1]
            current_time = data.index[i]
            
            # 1. 检测市场状态
            regime_info = self.regime_detector.detect(chunk)
            
            # 2. 记录状态历史
            self.regime_history.append((current_time, regime_info.regime, regime_info.confidence))
            
            # 3. 计算仓位大小
            position_size = self.calculate_position_size(
                regime_info.regime, regime_info, smooth=True
            )
            
            # 4. 获取策略组合
            strategy_config = get_strategy_for_regime_v2(regime_info.regime)
            strategies = strategy_config['strategies']
            weights = strategy_config['weights']
            
            # 5. 计算加权信号
            weighted_signal = 0.0
            for strategy_name, weight in zip(strategies, weights):
                try:
                    params = self.strategy_params.get(strategy_name, {})
                    strategy_signals = generate_strategy(chunk, strategy_name, **params)
                    raw_signal = strategy_signals.iloc[i]
                    weighted_signal += raw_signal * weight
                except Exception as e:
                    pass
            
            # 6. 应用仓位控制
            final_signal = np.clip(weighted_signal, -1, 1) * position_size
            signals.iloc[i] = final_signal
            
            # 7. 日志
            if self.verbose and i % 30 == 0:
                print(f"[{current_time}] {regime_info.regime.value:15s} "
                      f"仓位={position_size:.1%} 信号={final_signal:+.2f} "
                      f"置信度={regime_info.confidence:.0%}")
        
        return signals
    
    def get_regime_analysis(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        获取详细的市场状态分析
        """
        analysis = []
        
        for i in range(self.min_data_points, len(data)):
            chunk = data.iloc[:i+1]
            info = self.regime_detector.detect(chunk)
            position = self.calculate_position_size(info.regime, info, smooth=False)
            
            strategy_config = get_strategy_for_regime_v2(info.regime)
            
            analysis.append({
                'date': data.index[i],
                'close': data['close'].iloc[i],
                'regime': info.regime.value,
                'trend_short': info.trend_short,
                'trend_medium': info.trend_medium,
                'trend_long': info.trend_long,
                'volatility': info.volatility,
                'adx': info.adx,
                'new_high_ratio': info.new_high_ratio,
                'ma_alignment': info.ma_alignment,
                'confidence': info.confidence,
                'position_size': position,
                'primary_strategy': strategy_config['strategies'][0],
                'description': info.description
            })
        
        return pd.DataFrame(analysis).set_index('date')
    
    def generate_report(self, data: pd.DataFrame) -> Dict:
        """
        生成策略运行报告
        """
        analysis = self.get_regime_analysis(data)
        
        # 状态分布
        regime_counts = analysis['regime'].value_counts()
        regime_pct = analysis['regime'].value_counts(normalize=True) * 100
        
        # 平均仓位
        avg_position = analysis['position_size'].mean()
        max_position = analysis['position_size'].max()
        min_position = analysis['position_size'].min()
        
        # 各状态下的表现
        regime_performance = []
        for regime in analysis['regime'].unique():
            mask = analysis['regime'] == regime
            if mask.sum() < 2:
                continue
            
            period_data = analysis[mask]
            start_price = period_data['close'].iloc[0]
            end_price = period_data['close'].iloc[-1]
            returns = (end_price / start_price - 1) * 100
            
            regime_performance.append({
                'regime': regime,
                'duration': mask.sum(),
                'avg_position': period_data['position_size'].mean(),
                'returns': returns
            })
        
        report = {
            'summary': {
                'total_days': len(analysis),
                'avg_position': avg_position,
                'position_range': (min_position, max_position),
                'dominant_regime': regime_counts.index[0] if len(regime_counts) > 0 else 'unknown'
            },
            'regime_distribution': {
                regime: {'count': count, 'percentage': f"{pct:.1f}%"}
                for regime, count, pct in zip(regime_counts.index, regime_counts.values, regime_pct.values)
            },
            'regime_performance': regime_performance,
            'position_stats': {
                'avg': avg_position,
                'min': min_position,
                'max': max_position,
                'std': analysis['position_size'].std()
            }
        }
        
        return report


class MultiTimeframeStrategy:
    """
    多时间框架策略
    
    整合短期/中期/长期信号
    """
    
    def __init__(self):
        self.detector = MarketRegimeDetectorV2()
    
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        生成多时间框架信号
        
        需要三个时间框架一致才产生强信号
        """
        signals = pd.Series(0.0, index=data.index)
        
        for i in range(60, len(data)):
            chunk = data.iloc[:i+1]
            
            # 获取多时间框架确认
            confirmation = self.detector.get_multi_timeframe_confirmation(chunk)
            info = self.detector.detect(chunk)
            
            # 只有高一致性时才交易
            if confirmation['trend_agreement'] > 0.7:
                # 获取策略
                strategy_config = get_strategy_for_regime_v2(info.regime)
                strategy_name = strategy_config['strategies'][0]
                
                try:
                    params = self._get_params(strategy_name)
                    strategy_signals = generate_strategy(chunk, strategy_name, **params)
                    raw_signal = strategy_signals.iloc[i]
                    
                    # 根据一致性调整仓位
                    position = confirmation['trend_agreement'] * 0.8
                    signals.iloc[i] = np.clip(raw_signal, -1, 1) * position
                    
                except:
                    pass
        
        return signals
    
    def _get_params(self, strategy_name: str) -> dict:
        """获取策略参数"""
        default_params = {
            'ichimoku': {'tenkan_period': 9, 'kijun_period': 26, 'senkou_b_period': 52},
            'awesome_oscillator': {'short_period': 5, 'long_period': 34},
            'bollinger': {'period': 15, 'std_dev': 2.5},
            'dual_ma': {'fast': 5, 'slow': 20, 'ma_type': 'sma'},
            'momentum': {'period': 30},
            'tsi': {'long_period': 20, 'short_period': 10},
        }
        return default_params.get(strategy_name, {})


def test_adaptive_v2():
    """测试V2自适应策略"""
    print("=" * 100)
    print("🧪 测试自适应策略 V2")
    print("=" * 100)
    
    np.random.seed(42)
    
    # 生成包含不同状态的数据
    n = 400
    
    # 分段: 牛市 -> 熊市 -> 震荡
    bull = 100 * (1 + np.random.normal(0.0015, 0.012, 150)).cumprod()
    bear = bull[-1] * (1 + np.random.normal(-0.0012, 0.018, 100)).cumprod()
    range_base = bear[-1]
    range_prices = range_base + np.cumsum(np.random.normal(0, 0.8, 150))
    
    prices = np.concatenate([bull, bear, range_prices])
    
    data = pd.DataFrame({
        'open': prices * 0.995,
        'high': prices * 1.015,
        'low': prices * 0.985,
        'close': prices,
        'volume': np.random.normal(10000000, 2000000, n)
    }, index=pd.date_range('2024-01-01', periods=n, freq='B'))
    
    print("\n1. 测试V2自适应策略...")
    adaptive = AdaptiveStrategyV2(verbose=False)
    
    # 获取分析报告
    report = adaptive.generate_report(data)
    
    print("\n📊 运行报告:")
    print(f"   总天数: {report['summary']['total_days']}")
    print(f"   平均仓位: {report['summary']['avg_position']:.1%}")
    print(f"   仓位范围: {report['position_stats']['min']:.1%} - {report['position_stats']['max']:.1%}")
    print(f"   主导状态: {report['summary']['dominant_regime']}")
    
    print(f"\n   状态分布:")
    for regime, stats in report['regime_distribution'].items():
        print(f"     {regime}: {stats['count']}天 ({stats['percentage']})")
    
    # 生成信号
    signals = adaptive.generate_signals(data)
    print(f"\n   信号统计:")
    print(f"   平均持仓: {signals.abs().mean():.2f}")
    print(f"   最大持仓: {signals.abs().max():.2f}")
    print(f"   交易频率: {(signals != 0).sum()}/{len(signals)} ({(signals != 0).mean():.1%})")
    
    print("\n" + "=" * 100)
    print("✅ V2自适应策略测试完成")
    print("=" * 100)


if __name__ == "__main__":
    test_adaptive_v2()
