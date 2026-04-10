"""
策略库 - 提供多种量化交易策略

包含策略类型:
1. 趋势跟踪: 双均线、MACD、动量
2. 均值回归: RSI、布林带、ZScore
3. 波动率: ATR通道、唐奇安通道
4. 多因子: 量价组合、技术组合
"""
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np


class StrategyGenerator:
    """策略生成器 - 生成信号序列"""
    
    @staticmethod
    def dual_ma(data: pd.DataFrame, fast: int = 10, slow: int = 30) -> pd.Series:
        """
        双均线策略
        
        Args:
            data: OHLCV DataFrame
            fast: 短期均线周期
            slow: 长期均线周期
            
        Returns:
            信号序列 (1=买入, -1=卖出, 0=持有)
        """
        close = data['close']
        ma_fast = close.rolling(fast).mean()
        ma_slow = close.rolling(slow).mean()
        
        signals = pd.Series(0, index=data.index)
        
        # 金叉买入，死叉卖出
        golden_cross = (ma_fast > ma_slow) & (ma_fast.shift(1) <= ma_slow.shift(1))
        death_cross = (ma_fast < ma_slow) & (ma_fast.shift(1) >= ma_slow.shift(1))
        
        signals[golden_cross] = 1
        signals[death_cross] = -1
        
        return signals
    
    @staticmethod
    def macd(data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
        """
        MACD策略
        
        Args:
            data: OHLCV DataFrame
            fast: 快线周期
            slow: 慢线周期
            signal: 信号线周期
            
        Returns:
            信号序列
        """
        close = data['close']
        
        # 计算EMA
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        
        # MACD线和信号线
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        
        signals = pd.Series(0, index=data.index)
        
        # MACD上穿信号线买入，下穿卖出
        golden_cross = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
        death_cross = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))
        
        signals[golden_cross] = 1
        signals[death_cross] = -1
        
        return signals
    
    @staticmethod
    def rsi(data: pd.DataFrame, period: int = 14, overbought: int = 70, oversold: int = 30) -> pd.Series:
        """
        RSI均值回归策略
        
        Args:
            data: OHLCV DataFrame
            period: RSI周期
            overbought: 超买阈值
            oversold: 超卖阈值
            
        Returns:
            信号序列
        """
        close = data['close']
        
        # 计算RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        signals = pd.Series(0, index=data.index)
        
        # RSI低于超卖线买入，高于超买线卖出
        buy_signal = (rsi < oversold) & (rsi.shift(1) >= oversold)
        sell_signal = (rsi > overbought) & (rsi.shift(1) <= overbought)
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def bollinger_bands(data: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.Series:
        """
        布林带策略
        
        Args:
            data: OHLCV DataFrame
            period: 均线周期
            std_dev: 标准差倍数
            
        Returns:
            信号序列
        """
        close = data['close']
        
        # 计算布林带
        ma = close.rolling(period).mean()
        std = close.rolling(period).std()
        upper = ma + std_dev * std
        lower = ma - std_dev * std
        
        signals = pd.Series(0, index=data.index)
        
        # 触及下轨买入，触及上轨卖出
        buy_signal = (close < lower) & (close.shift(1) >= lower.shift(1))
        sell_signal = (close > upper) & (close.shift(1) <= upper.shift(1))
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def momentum(data: pd.DataFrame, period: int = 20) -> pd.Series:
        """
        动量策略
        
        Args:
            data: OHLCV DataFrame
            period: 动量周期
            
        Returns:
            信号序列
        """
        close = data['close']
        
        # 计算动量
        momentum = close.pct_change(period)
        
        signals = pd.Series(0, index=data.index)
        
        # 动量转正买入，转负卖出
        buy_signal = (momentum > 0) & (momentum.shift(1) <= 0)
        sell_signal = (momentum < 0) & (momentum.shift(1) >= 0)
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def atr_breakout(data: pd.DataFrame, period: int = 14, multiplier: float = 2.0) -> pd.Series:
        """
        ATR突破策略
        
        Args:
            data: OHLCV DataFrame
            period: ATR周期
            multiplier: ATR乘数
            
        Returns:
            信号序列
        """
        high = data['high']
        low = data['low']
        close = data['close']
        
        # 计算ATR
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        # 计算通道
        mid = close.rolling(period).mean()
        upper = mid + multiplier * atr
        lower = mid - multiplier * atr
        
        signals = pd.Series(0, index=data.index)
        
        # 突破上轨买入，跌破下轨卖出
        buy_signal = (close > upper) & (close.shift(1) <= upper.shift(1))
        sell_signal = (close < lower) & (close.shift(1) >= lower.shift(1))
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def donchian_channel(data: pd.DataFrame, period: int = 20) -> pd.Series:
        """
        唐奇安通道策略 (海龟交易法则)
        
        Args:
            data: OHLCV DataFrame
            period: 通道周期
            
        Returns:
            信号序列
        """
        high = data['high']
        low = data['low']
        close = data['close']
        
        # 计算通道
        upper = high.rolling(period).max()
        lower = low.rolling(period).min()
        
        signals = pd.Series(0, index=data.index)
        
        # 突破上轨买入，跌破下轨卖出
        buy_signal = (close > upper.shift(1)) & (close.shift(1) <= upper.shift(2))
        sell_signal = (close < lower.shift(1)) & (close.shift(1) >= lower.shift(2))
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def volume_price_trend(data: pd.DataFrame, period: int = 20) -> pd.Series:
        """
        量价趋势策略
        
        价格上涨+成交量放大 = 买入
        价格下跌+成交量放大 = 卖出
        
        Args:
            data: OHLCV DataFrame
            period: 均线周期
            
        Returns:
            信号序列
        """
        close = data['close']
        volume = data['volume']
        
        # 计算价格和成交量的趋势
        price_ma = close.rolling(period).mean()
        volume_ma = volume.rolling(period).mean()
        
        price_above_ma = close > price_ma
        volume_above_ma = volume > volume_ma
        
        signals = pd.Series(0, index=data.index)
        
        # 价格突破+放量买入
        buy_signal = price_above_ma & volume_above_ma & (~price_above_ma.shift(1).fillna(False))
        # 价格跌破+放量卖出
        sell_signal = (~price_above_ma) & volume_above_ma & (price_above_ma.shift(1).fillna(False))
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def combined_strategy(data: pd.DataFrame, 
                         strategies: List[Tuple[str, Dict]],
                         weights: Optional[List[float]] = None) -> pd.Series:
        """
        组合策略 - 多策略加权投票
        
        Args:
            data: OHLCV DataFrame
            strategies: 策略列表 [(strategy_name, params), ...]
            weights: 策略权重 (None则等权)
            
        Returns:
            信号序列
        """
        if weights is None:
            weights = [1.0 / len(strategies)] * len(strategies)
        
        # 生成各策略信号
        strategy_map = {
            'dual_ma': StrategyGenerator.dual_ma,
            'macd': StrategyGenerator.macd,
            'rsi': StrategyGenerator.rsi,
            'bollinger': StrategyGenerator.bollinger_bands,
            'momentum': StrategyGenerator.momentum,
            'atr_breakout': StrategyGenerator.atr_breakout,
            'donchian': StrategyGenerator.donchian_channel,
            'volume_price': StrategyGenerator.volume_price_trend,
        }
        
        combined_signal = pd.Series(0.0, index=data.index)
        
        for (name, params), weight in zip(strategies, weights):
            if name in strategy_map:
                signal = strategy_map[name](data, **params)
                combined_signal += signal * weight
        
        # 转换为离散信号
        result = pd.Series(0, index=data.index)
        result[combined_signal > 0.3] = 1
        result[combined_signal < -0.3] = -1
        
        return result


class StrategyOptimizer:
    """策略参数优化器"""
    
    @staticmethod
    def generate_param_grid(strategy_name: str) -> List[Dict]:
        """
        生成策略参数网格
        
        Args:
            strategy_name: 策略名称
            
        Returns:
            参数组合列表
        """
        param_grids = {
            'dual_ma': [
                {'fast': 5, 'slow': 20},
                {'fast': 10, 'slow': 30},
                {'fast': 20, 'slow': 60},
                {'fast': 5, 'slow': 60},
                {'fast': 10, 'slow': 50},
            ],
            'macd': [
                {'fast': 8, 'slow': 21, 'signal': 5},
                {'fast': 12, 'slow': 26, 'signal': 9},
                {'fast': 5, 'slow': 35, 'signal': 5},
            ],
            'rsi': [
                {'period': 7, 'overbought': 75, 'oversold': 25},
                {'period': 14, 'overbought': 70, 'oversold': 30},
                {'period': 21, 'overbought': 75, 'oversold': 25},
            ],
            'bollinger': [
                {'period': 20, 'std_dev': 1.5},
                {'period': 20, 'std_dev': 2.0},
                {'period': 20, 'std_dev': 2.5},
            ],
            'momentum': [
                {'period': 10},
                {'period': 20},
                {'period': 60},
            ],
            'atr_breakout': [
                {'period': 10, 'multiplier': 1.5},
                {'period': 14, 'multiplier': 2.0},
                {'period': 20, 'multiplier': 3.0},
            ],
            'donchian': [
                {'period': 20},
                {'period': 55},
                {'period': 100},
            ],
            'volume_price': [
                {'period': 10},
                {'period': 20},
                {'period': 30},
            ],
        }
        
        return param_grids.get(strategy_name, [{}])
    
    @staticmethod
    def generate_all_strategies() -> List[Tuple[str, str, Dict]]:
        """
        生成所有策略的参数组合
        
        Returns:
            列表 [(策略ID, 策略名称, 参数), ...]
        """
        all_strategies = []
        
        strategy_names = [
            'dual_ma', 'macd', 'rsi', 'bollinger', 
            'momentum', 'atr_breakout', 'donchian', 'volume_price'
        ]
        
        for name in strategy_names:
            params_list = StrategyOptimizer.generate_param_grid(name)
            for i, params in enumerate(params_list):
                strategy_id = f"{name}_{i+1}"
                all_strategies.append((strategy_id, name, params))
        
        return all_strategies


# 便捷函数
def get_strategy_names() -> List[str]:
    """获取所有策略名称"""
    return [
        'dual_ma', 'macd', 'rsi', 'bollinger',
        'momentum', 'atr_breakout', 'donchian', 'volume_price'
    ]


def generate_strategy(data: pd.DataFrame, strategy_name: str, **params) -> pd.Series:
    """
    生成指定策略的信号
    
    Args:
        data: OHLCV DataFrame
        strategy_name: 策略名称
        **params: 策略参数
        
    Returns:
        信号序列
    """
    generator = StrategyGenerator()
    
    strategy_map = {
        'dual_ma': generator.dual_ma,
        'macd': generator.macd,
        'rsi': generator.rsi,
        'bollinger': generator.bollinger_bands,
        'momentum': generator.momentum,
        'atr_breakout': generator.atr_breakout,
        'donchian': generator.donchian_channel,
        'volume_price': generator.volume_price_trend,
    }
    
    if strategy_name not in strategy_map:
        raise ValueError(f"未知策略: {strategy_name}. 可用策略: {list(strategy_map.keys())}")
    
    return strategy_map[strategy_name](data, **params)
