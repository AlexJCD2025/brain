#!/usr/bin/env python3
"""
市场状态检测模块 V2 - 改进版

改进点:
1. 增强牛市识别 (多维度确认)
2. 多时间框架确认 (短期/中期/长期)
3. 趋势持续性检查
"""
from typing import Literal, Dict, Tuple, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import pandas as pd
import numpy as np


class MarketRegime(Enum):
    """市场状态枚举"""
    STRONG_BULL = "strong_bull"      # 强劲牛市
    BULL = "bull"                    # 牛市
    WEAK_BULL = "weak_bull"          # 弱势上涨
    RANGE = "range"                  # 震荡市
    WEAK_BEAR = "weak_bear"          # 弱势下跌
    BEAR = "bear"                    # 熊市
    STRONG_BEAR = "strong_bear"      # 强劲熊市
    HIGH_VOL = "high_vol"            # 高波动
    UNKNOWN = "unknown"


@dataclass
class RegimeInfo:
    """市场状态信息 V2"""
    regime: MarketRegime
    trend_short: float      # 短期趋势 (-1 to 1)
    trend_medium: float     # 中期趋势
    trend_long: float       # 长期趋势
    volatility: float       # 波动率
    adx: float             # ADX
    volume_trend: float     # 成交量趋势
    new_high_ratio: float   # 新高比例 (0-1)
    ma_alignment: float     # MA多头排列得分
    confidence: float       # 置信度
    description: str


class MarketRegimeDetectorV2:
    """
    改进版市场状态检测器
    
    使用多时间框架和多维度指标确认市场状态
    """
    
    def __init__(self):
        self.short_window = 10   # 短期
        self.medium_window = 30  # 中期
        self.long_window = 60    # 长期
    
    def detect(self, data: pd.DataFrame) -> RegimeInfo:
        """
        检测当前市场状态 (多时间框架)
        """
        if len(data) < self.long_window:
            return self._create_unknown_info()
        
        close = data['close']
        volume = data.get('volume', pd.Series(1, index=data.index))
        
        # 1. 多时间框架趋势计算
        trend_short = self._calculate_trend(close, self.short_window)
        trend_medium = self._calculate_trend(close, self.medium_window)
        trend_long = self._calculate_trend(close, self.long_window)
        
        # 2. 波动率
        volatility = self._calculate_volatility(close)
        
        # 3. ADX
        adx = self._calculate_adx(data)
        
        # 4. 成交量趋势
        volume_trend = self._calculate_volume_trend(volume)
        
        # 5. 新高比例 (过去20天)
        new_high_ratio = self._calculate_new_high_ratio(close, 20)
        
        # 6. MA多头排列
        ma_alignment = self._calculate_ma_alignment(close)
        
        # 7. 综合判断市场状态
        regime, confidence, description = self._classify_regime_v2(
            trend_short, trend_medium, trend_long,
            volatility, adx, volume_trend, new_high_ratio, ma_alignment
        )
        
        return RegimeInfo(
            regime=regime,
            trend_short=trend_short,
            trend_medium=trend_medium,
            trend_long=trend_long,
            volatility=volatility,
            adx=adx,
            volume_trend=volume_trend,
            new_high_ratio=new_high_ratio,
            ma_alignment=ma_alignment,
            confidence=confidence,
            description=description
        )
    
    def _calculate_trend(self, prices: pd.Series, window: int) -> float:
        """计算趋势得分 (-1 to 1)"""
        if len(prices) < window:
            return 0.0
        
        sma = prices.rolling(window).mean()
        
        # 价格相对MA的位置
        position = (prices.iloc[-1] / sma.iloc[-1] - 1) * 10
        
        # MA斜率
        slope = (sma.iloc[-1] / sma.iloc[-window//2] - 1) * 20
        
        # 综合得分
        score = (position + slope) / 2
        return np.clip(score, -1, 1)
    
    def _calculate_volatility(self, prices: pd.Series, window: int = 20) -> float:
        """计算年化波动率"""
        returns = prices.pct_change().dropna()
        if len(returns) < window:
            return 20.0
        vol = returns.iloc[-window:].std() * np.sqrt(252) * 100
        return vol
    
    def _calculate_adx(self, data: pd.DataFrame, period: int = 14) -> float:
        """计算ADX"""
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
        
        # Smooth
        atr = tr.ewm(span=period, adjust=False).mean()
        plus_di = 100 * plus_dm.ewm(span=period, adjust=False).mean() / atr
        minus_di = 100 * minus_dm.ewm(span=period, adjust=False).mean() / atr
        
        # DX and ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.ewm(span=period, adjust=False).mean()
        
        return adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 25.0
    
    def _calculate_volume_trend(self, volume: pd.Series, window: int = 20) -> float:
        """计算成交量趋势"""
        if len(volume) < window:
            return 0.0
        
        vol_sma = volume.rolling(window).mean()
        current_vol = volume.iloc[-1]
        avg_vol = vol_sma.iloc[-1]
        
        # 相对平均成交量的变化
        trend = (current_vol / avg_vol - 1) * 2
        return np.clip(trend, -1, 1)
    
    def _calculate_new_high_ratio(self, prices: pd.Series, window: int = 20) -> float:
        """计算近期新高的比例"""
        if len(prices) < window * 2:
            return 0.5
        
        recent = prices.iloc[-window:]
        previous_max = prices.iloc[-window*2:-window].max()
        
        new_highs = (recent > previous_max).sum()
        return new_highs / window
    
    def _calculate_ma_alignment(self, prices: pd.Series) -> float:
        """计算MA多头排列得分"""
        if len(prices) < 60:
            return 0.0
        
        ma5 = prices.rolling(5).mean().iloc[-1]
        ma10 = prices.rolling(10).mean().iloc[-1]
        ma20 = prices.rolling(20).mean().iloc[-1]
        ma60 = prices.rolling(60).mean().iloc[-1]
        
        # 检查多头排列
        score = 0.0
        if ma5 > ma10:
            score += 0.25
        if ma10 > ma20:
            score += 0.25
        if ma20 > ma60:
            score += 0.25
        if ma5 > ma20:
            score += 0.25
        
        # 转换为 -1 to 1
        return (score - 0.5) * 2
    
    def _classify_regime_v2(
        self,
        trend_short: float,
        trend_medium: float,
        trend_long: float,
        volatility: float,
        adx: float,
        volume_trend: float,
        new_high_ratio: float,
        ma_alignment: float
    ) -> Tuple[MarketRegime, float, str]:
        """
        V2分类逻辑 - 多维度确认
        """
        # 高波动优先判断
        if volatility > 45:
            confidence = min(volatility / 60, 1.0)
            return MarketRegime.HIGH_VOL, confidence, f"高波动市场 (波动率={volatility:.1f}%)"
        
        # 牛市确认条件 (更严格)
        bull_signals = sum([
            trend_short > 0.2,           # 短期上涨
            trend_medium > 0.1,          # 中期上涨
            trend_long > 0.0,            # 长期不跌
            adx > 20,                    # 有趋势
            ma_alignment > 0.2,          # MA多头排列
            new_high_ratio > 0.3,        # 有创新高
        ])
        
        # 熊市确认条件
        bear_signals = sum([
            trend_short < -0.2,
            trend_medium < -0.1,
            trend_long < 0.0,
            adx > 20,
            ma_alignment < -0.2,
            new_high_ratio < 0.1,
        ])
        
        # 多时间框架一致性检查
        trend_consistency = abs(trend_short + trend_medium + trend_long) / 3
        
        # 牛市分级
        if bull_signals >= 4:
            if bull_signals >= 5 and trend_short > 0.5 and volume_trend > 0.2:
                confidence = 0.7 + trend_consistency * 0.3
                return MarketRegime.STRONG_BULL, min(confidence, 1.0), \
                       f"强劲牛市 (信号={bull_signals}/6, 新高率={new_high_ratio:.0%})"
            else:
                confidence = 0.5 + trend_consistency * 0.3
                return MarketRegime.BULL, min(confidence, 1.0), \
                       f"牛市 (信号={bull_signals}/6, 趋势一致={trend_consistency:.2f})"
        
        # 熊市分级
        if bear_signals >= 4:
            if bear_signals >= 5 and trend_short < -0.5:
                confidence = 0.7 + trend_consistency * 0.3
                return MarketRegime.STRONG_BEAR, min(confidence, 1.0), \
                       f"强劲熊市 (信号={bear_signals}/6)"
            else:
                confidence = 0.5 + trend_consistency * 0.3
                return MarketRegime.BEAR, min(confidence, 1.0), \
                       f"熊市 (信号={bear_signals}/6)"
        
        # 弱势涨跌
        if bull_signals >= 2 and trend_short > 0:
            return MarketRegime.WEAK_BULL, 0.4, "弱势上涨"
        if bear_signals >= 2 and trend_short < 0:
            return MarketRegime.WEAK_BEAR, 0.4, "弱势下跌"
        
        # 震荡市
        if adx < 20 and abs(trend_medium) < 0.15:
            confidence = 0.5 + (20 - adx) / 40
            return MarketRegime.RANGE, min(confidence, 0.8), \
                   f"震荡市 (ADX={adx:.1f}, 趋势={trend_medium:+.2f})"
        
        # 默认
        if trend_medium > 0:
            return MarketRegime.WEAK_BULL, 0.3, "默认弱势上涨"
        else:
            return MarketRegime.WEAK_BEAR, 0.3, "默认弱势下跌"
    
    def _create_unknown_info(self) -> RegimeInfo:
        """创建未知状态信息"""
        return RegimeInfo(
            regime=MarketRegime.UNKNOWN,
            trend_short=0, trend_medium=0, trend_long=0,
            volatility=20, adx=25, volume_trend=0,
            new_high_ratio=0.5, ma_alignment=0,
            confidence=0, description="数据不足"
        )
    
    def get_multi_timeframe_confirmation(self, data: pd.DataFrame) -> Dict:
        """
        获取多时间框架确认信息
        
        Returns:
            dict with confirmation details
        """
        info = self.detect(data)
        
        # 检查三个时间框架的一致性
        trends = [info.trend_short, info.trend_medium, info.trend_long]
        
        all_bullish = all(t > 0.1 for t in trends)
        all_bearish = all(t < -0.1 for t in trends)
        mixed = any(t > 0.1 for t in trends) and any(t < -0.1 for t in trends)
        
        confirmation = {
            'all_bullish': all_bullish,
            'all_bearish': all_bearish,
            'mixed_signals': mixed,
            'trend_agreement': 1 - np.std(trends) / (abs(np.mean(trends)) + 0.01),
            'recommended_action': self._get_recommendation(info, all_bullish, all_bearish)
        }
        
        return confirmation
    
    def _get_recommendation(
        self, 
        info: RegimeInfo, 
        all_bullish: bool, 
        all_bearish: bool
    ) -> str:
        """生成操作建议"""
        if info.regime in [MarketRegime.STRONG_BULL, MarketRegime.BULL]:
            if all_bullish:
                return "强烈买入 - 多时间框架确认牛市"
            else:
                return "谨慎买入 - 牛市但短期有分歧"
        
        elif info.regime in [MarketRegime.STRONG_BEAR, MarketRegime.BEAR]:
            if all_bearish:
                return "强烈卖出 - 多时间框架确认熊市"
            else:
                return "谨慎卖出 - 熊市但可能有反弹"
        
        elif info.regime == MarketRegime.RANGE:
            return "高抛低吸 - 震荡市策略"
        
        else:
            return "观望 - 方向不明"


# 状态到策略的映射 (V2)
REGIME_STRATEGY_MAP_V2 = {
    MarketRegime.STRONG_BULL: {
        'strategies': ['ichimoku', 'momentum'],
        'weights': [0.6, 0.4],
        'position_range': (0.7, 1.0),  # 70%-100%
        'description': '强劲牛市 - 重仓追涨'
    },
    MarketRegime.BULL: {
        'strategies': ['ichimoku', 'tsi'],
        'weights': [0.5, 0.5],
        'position_range': (0.5, 0.8),
        'description': '牛市 - 积极做多'
    },
    MarketRegime.WEAK_BULL: {
        'strategies': ['momentum', 'vwap'],
        'weights': [0.5, 0.5],
        'position_range': (0.3, 0.6),
        'description': '弱势上涨 - 谨慎做多'
    },
    MarketRegime.RANGE: {
        'strategies': ['bollinger', 'rsi'],
        'weights': [0.5, 0.5],
        'position_range': (0.3, 0.7),
        'description': '震荡市 - 高抛低吸'
    },
    MarketRegime.WEAK_BEAR: {
        'strategies': ['keltner_channel', 'cci'],
        'weights': [0.5, 0.5],
        'position_range': (0.1, 0.4),
        'description': '弱势下跌 - 减仓观望'
    },
    MarketRegime.BEAR: {
        'strategies': ['awesome_oscillator', 'aroon'],
        'weights': [0.6, 0.4],
        'position_range': (0.0, 0.3),
        'description': '熊市 - 空仓或轻仓'
    },
    MarketRegime.STRONG_BEAR: {
        'strategies': ['awesome_oscillator'],
        'weights': [1.0],
        'position_range': (0.0, 0.2),
        'description': '强劲熊市 - 空仓等待'
    },
    MarketRegime.HIGH_VOL: {
        'strategies': ['atr_breakout', 'donchian'],
        'weights': [0.5, 0.5],
        'position_range': (0.2, 0.5),
        'description': '高波动 - 突破策略'
    },
    MarketRegime.UNKNOWN: {
        'strategies': ['dual_ma'],
        'weights': [1.0],
        'position_range': (0.3, 0.5),
        'description': '未知 - 默认策略'
    }
}


def get_strategy_for_regime_v2(regime: MarketRegime) -> Dict:
    """根据市场状态获取推荐策略 V2"""
    return REGIME_STRATEGY_MAP_V2.get(regime, REGIME_STRATEGY_MAP_V2[MarketRegime.UNKNOWN])


def print_regime_info_v2(info: RegimeInfo):
    """打印V2市场状态信息"""
    regime_emoji = {
        MarketRegime.STRONG_BULL: '🚀',
        MarketRegime.BULL: '📈',
        MarketRegime.WEAK_BULL: '↗️',
        MarketRegime.RANGE: '🔄',
        MarketRegime.WEAK_BEAR: '↘️',
        MarketRegime.BEAR: '📉',
        MarketRegime.STRONG_BEAR: '🐻',
        MarketRegime.HIGH_VOL: '⚡',
        MarketRegime.UNKNOWN: '❓'
    }
    
    emoji = regime_emoji.get(info.regime, '❓')
    print(f"\n{emoji} 市场状态: {info.regime.value.upper()}")
    print(f"   描述: {info.description}")
    print(f"   趋势(短/中/长): {info.trend_short:+.2f} / {info.trend_medium:+.2f} / {info.trend_long:+.2f}")
    print(f"   波动率: {info.volatility:.2f}%")
    print(f"   ADX: {info.adx:.2f}")
    print(f"   成交量趋势: {info.volume_trend:+.2f}")
    print(f"   新高比例: {info.new_high_ratio:.1%}")
    print(f"   MA排列: {info.ma_alignment:+.2f}")
    print(f"   置信度: {info.confidence:.1%}")


# 测试函数
def test_detector_v2():
    """测试V2检测器"""
    print("=" * 100)
    print("🧪 测试市场状态检测器 V2")
    print("=" * 100)
    
    np.random.seed(42)
    
    # 生成测试数据
    n = 300
    
    # 强劲牛市数据
    bull_prices = 100 * (1 + np.random.normal(0.002, 0.015, n)).cumprod()
    bull_data = pd.DataFrame({
        'open': bull_prices * 0.99,
        'high': bull_prices * 1.025,
        'low': bull_prices * 0.975,
        'close': bull_prices,
        'volume': np.random.normal(10000000, 2000000, n) * (1 + np.arange(n) * 0.001)
    }, index=pd.date_range('2024-01-01', periods=n, freq='B'))
    
    detector = MarketRegimeDetectorV2()
    
    print("\n1. 牛市测试:")
    info = detector.detect(bull_data)
    print_regime_info_v2(info)
    
    # 多时间框架确认
    confirmation = detector.get_multi_timeframe_confirmation(bull_data)
    print(f"   多时间框架确认: {confirmation}")
    
    print("\n" + "=" * 100)
    print("✅ V2检测器测试完成")
    print("=" * 100)


if __name__ == "__main__":
    test_detector_v2()
