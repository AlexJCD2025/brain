#!/usr/bin/env python3
"""
市场状态检测模块

检测市场处于:
- 牛市 (Bull): 强劲上涨趋势
- 熊市 (Bear): 下跌趋势
- 震荡市 (Range): 横盘震荡
- 高波动 (High Vol): 高波动率

使用指标:
- 价格趋势 (MA斜率)
- 波动率 (ATR/Std)
- 动量 (RSI/MACD)
- ADX (趋势强度)
"""
from typing import Literal, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import numpy as np


MarketRegime = Literal['bull', 'bear', 'range', 'high_vol', 'unknown']


@dataclass
class RegimeInfo:
    """市场状态信息"""
    regime: MarketRegime
    trend_score: float  # -1 to 1 (负=下跌, 正=上涨)
    volatility: float   # 波动率
    adx: float         # 趋势强度
    confidence: float  # 置信度 0-1
    description: str


class MarketRegimeDetector:
    """市场状态检测器"""
    
    def __init__(self, lookback: int = 20):
        self.lookback = lookback
    
    def detect(self, data: pd.DataFrame) -> RegimeInfo:
        """
        检测当前市场状态
        
        Returns:
            RegimeInfo: 市场状态信息
        """
        if len(data) < self.lookback * 2:
            return RegimeInfo(
                regime='unknown',
                trend_score=0,
                volatility=0,
                adx=0,
                confidence=0,
                description="数据不足"
            )
        
        # 计算指标
        close = data['close']
        
        # 1. 趋势得分 (-1 to 1)
        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(50).mean()
        
        # 短期趋势
        short_trend = (close.iloc[-1] / sma20.iloc[-1] - 1) * 10  # 标准化
        # 长期趋势
        long_trend = (sma20.iloc[-1] / sma50.iloc[-1] - 1) * 20
        
        trend_score = np.clip((short_trend + long_trend) / 2, -1, 1)
        
        # 2. 波动率 (年化)
        returns = close.pct_change().dropna()
        volatility = returns.iloc[-self.lookback:].std() * np.sqrt(252) * 100
        
        # 3. ADX (趋势强度)
        adx = self._calculate_adx(data, 14)
        
        # 4. 判断市场状态
        regime, confidence, description = self._classify_regime(
            trend_score, volatility, adx
        )
        
        return RegimeInfo(
            regime=regime,
            trend_score=trend_score,
            volatility=volatility,
            adx=adx,
            confidence=confidence,
            description=description
        )
    
    def _calculate_adx(self, data: pd.DataFrame, period: int = 14) -> float:
        """计算ADX指标"""
        high = data['high']
        low = data['low']
        close = data['close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # +DM and -DM
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        plus_dm[plus_dm <= minus_dm] = 0
        minus_dm[minus_dm <= plus_dm] = 0
        
        # Smooth TR and DM
        atr = tr.ewm(span=period, adjust=False).mean()
        plus_di = 100 * plus_dm.ewm(span=period, adjust=False).mean() / atr
        minus_di = 100 * minus_dm.ewm(span=period, adjust=False).mean() / atr
        
        # DX and ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.ewm(span=period, adjust=False).mean()
        
        return adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 25
    
    def _classify_regime(
        self,
        trend_score: float,
        volatility: float,
        adx: float
    ) -> Tuple[MarketRegime, float, str]:
        """
        分类市场状态
        
        规则:
        - Bull: 强趋势 + 上涨 + 高ADX
        - Bear: 强趋势 + 下跌 + 高ADX
        - Range: 低ADX + 低波动
        - High Vol: 高波动
        """
        # 高波动优先
        if volatility > 40:
            confidence = min(volatility / 50, 1.0)
            return 'high_vol', confidence, f"高波动市场 (波动率={volatility:.1f}%)"
        
        # 强趋势
        if adx > 25:
            if trend_score > 0.3:
                confidence = min(trend_score * adx / 30, 1.0)
                return 'bull', confidence, f"牛市 (趋势={trend_score:+.2f}, ADX={adx:.1f})"
            elif trend_score < -0.3:
                confidence = min(abs(trend_score) * adx / 30, 1.0)
                return 'bear', confidence, f"熊市 (趋势={trend_score:+.2f}, ADX={adx:.1f})"
        
        # 震荡市
        if abs(trend_score) < 0.2 and volatility < 25:
            confidence = 1 - abs(trend_score) * 2
            return 'range', confidence, f"震荡市 (趋势={trend_score:+.2f}, 波动={volatility:.1f}%)"
        
        # 默认
        if trend_score > 0:
            return 'bull', 0.5, f"温和上涨 (趋势={trend_score:+.2f})"
        else:
            return 'bear', 0.5, f"温和下跌 (趋势={trend_score:+.2f})"
    
    def get_regime_history(self, data: pd.DataFrame, window: int = 20) -> pd.DataFrame:
        """
        获取历史市场状态序列
        
        Args:
            data: 价格数据
            window: 每个状态检测使用的窗口
        
        Returns:
            DataFrame with regime information
        """
        regimes = []
        
        for i in range(window, len(data)):
            chunk = data.iloc[i-window:i]
            info = self.detect(chunk)
            
            regimes.append({
                'date': data.index[i],
                'close': data['close'].iloc[i],
                'regime': info.regime,
                'trend_score': info.trend_score,
                'volatility': info.volatility,
                'adx': info.adx,
                'confidence': info.confidence
            })
        
        return pd.DataFrame(regimes).set_index('date')


# 市场状态 -> 推荐策略映射
REGIME_STRATEGY_MAP = {
    'bull': {
        'primary': 'ichimoku',
        'secondary': ['momentum', 'tsi'],
        'description': '牛市跟随趋势',
        'position_size': 1.0,  # 满仓
        'leverage': 1.0
    },
    'bear': {
        'primary': 'awesome_oscillator',
        'secondary': ['keltner_channel', 'cci'],
        'description': '熊市控制回撤',
        'position_size': 0.5,  # 半仓
        'leverage': 1.0
    },
    'range': {
        'primary': 'bollinger',
        'secondary': ['rsi', 'williams_r', 'stochastic'],
        'description': '震荡市高抛低吸',
        'position_size': 0.7,
        'leverage': 1.0
    },
    'high_vol': {
        'primary': 'atr_breakout',
        'secondary': ['donchian', 'keltner_channel'],
        'description': '高波动突破策略',
        'position_size': 0.5,  # 降低仓位
        'leverage': 1.0
    },
    'unknown': {
        'primary': 'dual_ma',
        'secondary': [],
        'description': '默认策略',
        'position_size': 0.5,
        'leverage': 1.0
    }
}


def get_strategy_for_regime(regime: MarketRegime) -> Dict:
    """
    根据市场状态获取推荐策略
    
    Args:
        regime: 市场状态
    
    Returns:
        策略配置字典
    """
    return REGIME_STRATEGY_MAP.get(regime, REGIME_STRATEGY_MAP['unknown'])


def print_regime_info(info: RegimeInfo):
    """打印市场状态信息"""
    regime_emoji = {
        'bull': '🚀',
        'bear': '🐻',
        'range': '🔄',
        'high_vol': '⚡',
        'unknown': '❓'
    }
    
    emoji = regime_emoji.get(info.regime, '❓')
    print(f"\n{emoji} 市场状态: {info.regime.upper()}")
    print(f"   描述: {info.description}")
    print(f"   趋势得分: {info.trend_score:+.2f}")
    print(f"   波动率: {info.volatility:.2f}%")
    print(f"   ADX: {info.adx:.2f}")
    print(f"   置信度: {info.confidence:.1%}")
    
    # 推荐策略
    strategy_config = get_strategy_for_regime(info.regime)
    print(f"   推荐策略: {strategy_config['primary']}")
    print(f"   策略说明: {strategy_config['description']}")
    print(f"   建议仓位: {strategy_config['position_size']:.0%}")


def test_detector():
    """测试检测器"""
    print("=" * 80)
    print("🧪 测试市场状态检测器")
    print("=" * 80)
    
    # 生成测试数据
    np.random.seed(42)
    
    # 模拟不同市场状态
    n = 200
    
    # 牛市数据
    bull_prices = 100 * (1 + np.random.normal(0.001, 0.01, n)).cumprod()
    bull_data = pd.DataFrame({
        'open': bull_prices * 0.99,
        'high': bull_prices * 1.02,
        'low': bull_prices * 0.98,
        'close': bull_prices,
        'volume': np.random.randint(1000000, 10000000, n)
    }, index=pd.date_range('2024-01-01', periods=n, freq='B'))
    
    # 熊市数据
    bear_prices = 100 * (1 + np.random.normal(-0.001, 0.015, n)).cumprod()
    bear_data = pd.DataFrame({
        'open': bear_prices * 1.01,
        'high': bear_prices * 1.03,
        'low': bear_prices * 0.97,
        'close': bear_prices,
        'volume': np.random.randint(1000000, 10000000, n)
    }, index=pd.date_range('2024-01-01', periods=n, freq='B'))
    
    # 震荡市数据
    range_prices = 100 + np.cumsum(np.random.normal(0, 0.5, n))
    range_data = pd.DataFrame({
        'open': range_prices + np.random.normal(0, 0.5, n),
        'high': range_prices + 2 + np.random.normal(0, 0.5, n),
        'low': range_prices - 2 + np.random.normal(0, 0.5, n),
        'close': range_prices,
        'volume': np.random.randint(1000000, 10000000, n)
    }, index=pd.date_range('2024-01-01', periods=n, freq='B'))
    
    detector = MarketRegimeDetector()
    
    print("\n1. 牛市测试:")
    info = detector.detect(bull_data)
    print_regime_info(info)
    
    print("\n2. 熊市测试:")
    info = detector.detect(bear_data)
    print_regime_info(info)
    
    print("\n3. 震荡市测试:")
    info = detector.detect(range_data)
    print_regime_info(info)
    
    print("\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)


if __name__ == "__main__":
    test_detector()
