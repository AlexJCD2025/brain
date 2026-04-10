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
    def dual_ma(data: pd.DataFrame, fast: int = 10, slow: int = 30,
                ma_type: str = "sma") -> pd.Series:
        """
        双均线策略 (支持SMA和EMA)
        
        Args:
            data: OHLCV DataFrame
            fast: 短期均线周期
            slow: 长期均线周期
            ma_type: 均线类型 ("sma" 或 "ema")
            
        Returns:
            信号序列 (1=买入, -1=卖出, 0=持有)
        """
        close = data['close']
        
        # 支持 SMA 和 EMA 切换
        if ma_type == "ema":
            ma_fast = close.ewm(span=fast, adjust=False).mean()
            ma_slow = close.ewm(span=slow, adjust=False).mean()
        else:  # sma
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
    def supertrend(data: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.Series:
        """
        超级趋势策略 Supertrend (Jarvis版本优化)
        
        优化点:
        - 修复 Jarvis 版本的 close.class() Bug
        - 方向改变时才产生信号
        
        Args:
            data: OHLCV DataFrame
            period: ATR周期 (默认10)
            multiplier: ATR倍数 (默认3.0)
            
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
        
        # 计算上下轨
        hl2 = (high + low) / 2
        upper_band = hl2 + multiplier * atr
        lower_band = hl2 - multiplier * atr
        
        # 计算方向 (1=多头, -1=空头)
        direction = pd.Series(1, index=data.index)
        
        for i in range(1, len(close)):
            if close.iloc[i] > upper_band.iloc[i]:
                direction.iloc[i] = 1
            elif close.iloc[i] < lower_band.iloc[i]:
                direction.iloc[i] = -1
            else:
                direction.iloc[i] = direction.iloc[i-1]
        
        # 生成信号 (方向改变时)
        signals = pd.Series(0, index=data.index)
        signals[(direction == 1) & (direction.shift(1) == -1)] = 1   # 转多
        signals[(direction == -1) & (direction.shift(1) == 1)] = -1  # 转空
        
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
    
    # ============================================================
    # D. 新增策略 - KDJ, CCI, Williams %R
    # ============================================================
    
    @staticmethod
    def kdj(data: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.Series:
        """
        KDJ随机指标策略
        
        Args:
            data: OHLCV DataFrame
            n: RSV周期 (默认9)
            m1: K平滑因子 (默认3)
            m2: D平滑因子 (默认3)
            
        Returns:
            信号序列
            
        逻辑:
            K上穿D买入 (金叉)
            K下穿D卖出 (死叉)
        """
        low_list = data['low'].rolling(window=n, min_periods=n).min()
        high_list = data['high'].rolling(window=n, min_periods=n).max()
        rsv = (data['close'] - low_list) / (high_list - low_list) * 100
        
        # 计算K, D, J值
        k = rsv.ewm(alpha=1/m1, adjust=False).mean()
        d = k.ewm(alpha=1/m2, adjust=False).mean()
        j = 3 * k - 2 * d
        
        signals = pd.Series(0, index=data.index)
        
        # K上穿D买入，下穿卖出
        golden_cross = (k > d) & (k.shift(1) <= d.shift(1))
        death_cross = (k < d) & (k.shift(1) >= d.shift(1))
        
        signals[golden_cross] = 1
        signals[death_cross] = -1
        
        return signals
    
    @staticmethod
    def cci(data: pd.DataFrame, period: int = 20, upper: float = 100, lower: float = -100) -> pd.Series:
        """
        CCI商品通道指数策略
        
        Args:
            data: OHLCV DataFrame
            period: CCI周期 (默认20)
            upper: 超买阈值 (默认+100)
            lower: 超卖阈值 (默认-100)
            
        Returns:
            信号序列
            
        逻辑:
            CCI < lower 超卖买入
            CCI > upper 超买卖出
        """
        tp = (data['high'] + data['low'] + data['close']) / 3
        ma_tp = tp.rolling(window=period).mean()
        md = tp.rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean())
        
        cci = (tp - ma_tp) / (0.015 * md)
        
        signals = pd.Series(0, index=data.index)
        
        # CCI低于下界买入，高于上界卖出
        buy_signal = (cci < lower) & (cci.shift(1) >= lower)
        sell_signal = (cci > upper) & (cci.shift(1) <= upper)
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def williams_r(data: pd.DataFrame, period: int = 14, upper: float = -20, lower: float = -80) -> pd.Series:
        """
        Williams %R 威廉指标策略
        
        Args:
            data: OHLCV DataFrame
            period: 周期 (默认14)
            upper: 超买阈值 (默认-20)
            lower: 超卖阈值 (默认-80)
            
        Returns:
            信号序列
            
        逻辑:
            %R < lower (-80) 超卖买入
            %R > upper (-20) 超买卖出
        """
        highest_high = data['high'].rolling(window=period).max()
        lowest_low = data['low'].rolling(window=period).min()
        
        williams_r = (highest_high - data['close']) / (highest_high - lowest_low) * -100
        
        signals = pd.Series(0, index=data.index)
        
        # %R低于下界买入，高于上界卖出
        buy_signal = (williams_r < lower) & (williams_r.shift(1) >= lower)
        sell_signal = (williams_r > upper) & (williams_r.shift(1) <= upper)
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    # ============================================================
    # 更多新增策略 - 经典技术指标
    # ============================================================
    
    @staticmethod
    def ichimoku(data: pd.DataFrame, 
                 tenkan_period: int = 9, 
                 kijun_period: int = 26, 
                 senkou_b_period: int = 52) -> pd.Series:
        """
        Ichimoku Cloud (一目均衡表) 策略
        
        日本经典趋势指标，包含5条线:
        - Tenkan-sen (转换线): 短周期中线
        - Kijun-sen (基准线): 中周期中线  
        - Senkou Span A (先行上线): 未来26日的(Tenkan+Kijun)/2
        - Senkou Span B (先行下线): 未来26日的52周期中线
        - Chikou Span (延迟线): 26日前的收盘价
        
        Args:
            data: OHLCV DataFrame
            tenkan_period: 转换线周期 (默认9)
            kijun_period: 基准线周期 (默认26)
            senkou_b_period: 先行下线周期 (默认52)
            
        Returns:
            信号序列
            
        交易逻辑:
            价格上穿云层买入，下穿云层卖出
        """
        high = data['high']
        low = data['low']
        close = data['close']
        
        # Tenkan-sen (转换线): (9周期最高+最低)/2
        tenkan_sen = (high.rolling(window=tenkan_period).max() + 
                      low.rolling(window=tenkan_period).min()) / 2
        
        # Kijun-sen (基准线): (26周期最高+最低)/2
        kijun_sen = (high.rolling(window=kijun_period).max() + 
                     low.rolling(window=kijun_period).min()) / 2
        
        # Senkou Span A (先行上线): (Tenkan + Kijun) / 2，前移26日
        senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(kijun_period)
        
        # Senkou Span B (先行下线): (52周期最高+最低)/2，前移26日
        senkou_span_b = ((high.rolling(window=senkou_b_period).max() + 
                          low.rolling(window=senkou_b_period).min()) / 2).shift(kijun_period)
        
        # 云层 (Kumo)
        kumo_top = senkou_span_a.combine(senkou_span_b, max)
        kumo_bottom = senkou_span_a.combine(senkou_span_b, min)
        
        signals = pd.Series(0, index=data.index)
        
        # 价格上穿云层买入，下穿云层卖出
        above_cloud = close > kumo_top
        below_cloud = close < kumo_bottom
        
        buy_signal = above_cloud & (~above_cloud.shift(1).fillna(False))
        sell_signal = below_cloud & (~below_cloud.shift(1).fillna(False))
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def parabolic_sar(data: pd.DataFrame, 
                      af_start: float = 0.02, 
                      af_max: float = 0.20) -> pd.Series:
        """
        Parabolic SAR (抛物线SAR) 策略
        
        Welles Wilder开发的趋势追踪指标
        
        Args:
            data: OHLCV DataFrame
            af_start: 初始加速因子 (默认0.02)
            af_max: 最大加速因子 (默认0.20)
            
        Returns:
            信号序列
            
        交易逻辑:
            价格上穿SAR买入，下穿SAR卖出
        """
        high = data['high']
        low = data['low']
        close = data['close']
        
        # 简化版SAR计算
        sar = pd.Series(index=data.index, dtype=float)
        trend = pd.Series(index=data.index, dtype=float)
        af = pd.Series(index=data.index, dtype=float)
        ep = pd.Series(index=data.index, dtype=float)
        
        # 初始化
        sar.iloc[0] = low.iloc[0]
        trend.iloc[0] = 1  # 1为多头，-1为空头
        af.iloc[0] = af_start
        ep.iloc[0] = high.iloc[0]
        
        for i in range(1, len(data)):
            # 计算SAR
            sar.iloc[i] = sar.iloc[i-1] + af.iloc[i-1] * (ep.iloc[i-1] - sar.iloc[i-1])
            
            # 检查趋势反转
            if trend.iloc[i-1] == 1:  # 多头
                if low.iloc[i] < sar.iloc[i]:  # 跌破SAR，转为空头
                    trend.iloc[i] = -1
                    sar.iloc[i] = ep.iloc[i-1]
                    af.iloc[i] = af_start
                    ep.iloc[i] = low.iloc[i]
                else:  # 继续多头
                    trend.iloc[i] = 1
                    if high.iloc[i] > ep.iloc[i-1]:  # 创新高
                        ep.iloc[i] = high.iloc[i]
                        af.iloc[i] = min(af.iloc[i-1] + af_start, af_max)
                    else:
                        ep.iloc[i] = ep.iloc[i-1]
                        af.iloc[i] = af.iloc[i-1]
            else:  # 空头
                if high.iloc[i] > sar.iloc[i]:  # 突破SAR，转为多头
                    trend.iloc[i] = 1
                    sar.iloc[i] = ep.iloc[i-1]
                    af.iloc[i] = af_start
                    ep.iloc[i] = high.iloc[i]
                else:  # 继续空头
                    trend.iloc[i] = -1
                    if low.iloc[i] < ep.iloc[i-1]:  # 创新低
                        ep.iloc[i] = low.iloc[i]
                        af.iloc[i] = min(af.iloc[i-1] + af_start, af_max)
                    else:
                        ep.iloc[i] = ep.iloc[i-1]
                        af.iloc[i] = af.iloc[i-1]
        
        signals = pd.Series(0, index=data.index)
        
        # 趋势转变时产生信号
        buy_signal = (trend == 1) & (trend.shift(1) == -1)
        sell_signal = (trend == -1) & (trend.shift(1) == 1)
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def obv(data: pd.DataFrame) -> pd.Series:
        """
        OBV (On Balance Volume) 能量潮策略
        
        Joseph Granville开发的量价指标
        
        Args:
            data: OHLCV DataFrame
            
        Returns:
            信号序列
            
        逻辑:
            价格上涨: OBV += 成交量
            价格下跌: OBV -= 成交量
            OBV突破均线买入，跌破卖出
        """
        close = data['close']
        volume = data['volume']
        
        # 计算OBV
        obv = pd.Series(index=data.index, dtype=float)
        obv.iloc[0] = volume.iloc[0]
        
        for i in range(1, len(data)):
            if close.iloc[i] > close.iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] + volume.iloc[i]
            elif close.iloc[i] < close.iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] - volume.iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]
        
        # OBV均线
        obv_ma = obv.rolling(window=20).mean()
        
        signals = pd.Series(0, index=data.index)
        
        # OBV上穿均线买入，下穿卖出
        buy_signal = (obv > obv_ma) & (obv.shift(1) <= obv_ma.shift(1))
        sell_signal = (obv < obv_ma) & (obv.shift(1) >= obv_ma.shift(1))
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def adx(data: pd.DataFrame, period: int = 14, threshold: float = 25.0) -> pd.Series:
        """
        ADX (Average Directional Index) 平均趋向指数策略
        
        Welles Wilder开发的趋势强度指标
        
        Args:
            data: OHLCV DataFrame
            period: 周期 (默认14)
            threshold: 趋势强度阈值 (默认25)
            
        Returns:
            信号序列
            
        逻辑:
            ADX > 25: 趋势市场，+DI > -DI买入，反之卖出
            ADX < 25: 震荡市场，不交易
        """
        high = data['high']
        low = data['low']
        close = data['close']
        
        # 计算True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # 计算+DM和-DM
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        plus_dm[plus_dm <= minus_dm] = 0
        minus_dm[minus_dm <= plus_dm] = 0
        
        # 平滑
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * plus_dm.rolling(window=period).mean() / atr
        minus_di = 100 * minus_dm.rolling(window=period).mean() / atr
        
        # 计算DX和ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        signals = pd.Series(0, index=data.index)
        
        # 趋势市场才交易
        trending = adx > threshold
        
        # +DI > -DI买入，反之卖出
        buy_signal = trending & (plus_di > minus_di) & (plus_di.shift(1) <= minus_di.shift(1))
        sell_signal = trending & (plus_di < minus_di) & (plus_di.shift(1) >= minus_di.shift(1))
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def mfi(data: pd.DataFrame, period: int = 14, overbought: float = 80, oversold: float = 20) -> pd.Series:
        """
        MFI (Money Flow Index) 资金流量指标策略
        
        类似RSI但考虑成交量
        
        Args:
            data: OHLCV DataFrame
            period: 周期 (默认14)
            overbought: 超买阈值 (默认80)
            oversold: 超卖阈值 (默认20)
            
        Returns:
            信号序列
            
        逻辑:
            MFI < 20 超卖买入
            MFI > 80 超买卖出
        """
        high = data['high']
        low = data['low']
        close = data['close']
        volume = data['volume']
        
        # 典型价格
        typical_price = (high + low + close) / 3
        
        # 原始资金流
        raw_money_flow = typical_price * volume
        
        # 资金流方向
        money_flow_sign = (typical_price > typical_price.shift(1)).astype(int)
        money_flow_sign[typical_price < typical_price.shift(1)] = -1
        
        # 正负资金流
        positive_flow = raw_money_flow.copy()
        positive_flow[money_flow_sign <= 0] = 0
        
        negative_flow = raw_money_flow.copy()
        negative_flow[money_flow_sign >= 0] = 0
        
        # 资金流比率
        positive_sum = positive_flow.rolling(window=period).sum()
        negative_sum = negative_flow.rolling(window=period).sum()
        
        money_flow_ratio = positive_sum / negative_sum
        
        # MFI
        mfi = 100 - (100 / (1 + money_flow_ratio))
        
        signals = pd.Series(0, index=data.index)
        
        # MFI低于超卖线买入，高于超买线卖出
        buy_signal = (mfi < oversold) & (mfi.shift(1) >= oversold)
        sell_signal = (mfi > overbought) & (mfi.shift(1) <= overbought)
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def vwap(data: pd.DataFrame, period: int = 20) -> pd.Series:
        """
        VWAP (Volume Weighted Average Price) 成交量加权平均价策略
        
        机构常用指标
        
        Args:
            data: OHLCV DataFrame
            period: VWAP周期 (默认20)
            
        Returns:
            信号序列
            
        逻辑:
            价格上穿VWAP买入，下穿卖出
        """
        high = data['high']
        low = data['low']
        close = data['close']
        volume = data['volume']
        
        # 典型价格
        typical_price = (high + low + close) / 3
        
        # VWAP
        vwap = (typical_price * volume).rolling(window=period).sum() / volume.rolling(window=period).sum()
        
        signals = pd.Series(0, index=data.index)
        
        # 价格上穿VWAP买入，下穿卖出
        buy_signal = (close > vwap) & (close.shift(1) <= vwap.shift(1))
        sell_signal = (close < vwap) & (close.shift(1) >= vwap.shift(1))
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def stochastic(data: pd.DataFrame, 
                   k_period: int = 14, 
                   d_period: int = 3, 
                   overbought: float = 80, 
                   oversold: float = 20) -> pd.Series:
        """
        Stochastic Oscillator (随机震荡指标)
        
        与KDJ类似但更简单
        
        Args:
            data: OHLCV DataFrame
            k_period: %K周期 (默认14)
            d_period: %D周期 (默认3)
            overbought: 超买阈值 (默认80)
            oversold: 超卖阈值 (默认20)
            
        Returns:
            信号序列
            
        逻辑:
            %K < 20 超卖买入
            %K > 80 超买卖出
        """
        high = data['high']
        low = data['low']
        close = data['close']
        
        # 计算%K
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        
        k = 100 * (close - lowest_low) / (highest_high - lowest_low)
        
        # 计算%D (%K的移动平均)
        d = k.rolling(window=d_period).mean()
        
        signals = pd.Series(0, index=data.index)
        
        # %K低于超卖线买入，高于超买线卖出
        buy_signal = (k < oversold) & (k.shift(1) >= oversold)
        sell_signal = (k > overbought) & (k.shift(1) <= overbought)
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def heikin_ashi(data: pd.DataFrame) -> pd.Series:
        """
        Heikin-Ashi (平均K线) 策略
        
        日本蜡烛图变体，过滤噪音
        
        Args:
            data: OHLCV DataFrame
            
        Returns:
            信号序列
            
        逻辑:
            连续3根阳线买入，连续3根阴线卖出
        """
        open_price = data['open']
        high = data['high']
        low = data['low']
        close = data['close']
        
        # 计算Heikin-Ashi蜡烛
        ha_close = (open_price + high + low + close) / 4
        ha_open = (open_price.shift(1) + close.shift(1)) / 2
        ha_open.iloc[0] = (open_price.iloc[0] + close.iloc[0]) / 2
        
        # 填充na
        ha_open = ha_open.ffill()
        
        # 判断阳线/阴线
        ha_bull = ha_close > ha_open  # 阳线
        ha_bear = ha_close < ha_open  # 阴线
        
        signals = pd.Series(0, index=data.index)
        
        # 连续3根阳线买入
        buy_signal = (ha_bull & ha_bull.shift(1) & ha_bull.shift(2) & 
                      (~(ha_bull.shift(1) & ha_bull.shift(2) & ha_bull.shift(3)).fillna(False)))
        
        # 连续3根阴线卖出
        sell_signal = (ha_bear & ha_bear.shift(1) & ha_bear.shift(2) & 
                       (~(ha_bear.shift(1) & ha_bear.shift(2) & ha_bear.shift(3)).fillna(False)))
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    # ============================================================
    # 第三波新增策略 - 高级技术指标
    # ============================================================
    
    @staticmethod
    def trix(data: pd.DataFrame, period: int = 15, signal_period: int = 9) -> pd.Series:
        """
        TRIX (Triple Exponential Moving Average) 三重指数平滑
        
        Jack Hutson开发的趋势指标，过滤价格噪音
        
        Args:
            data: OHLCV DataFrame
            period: TRIX周期 (默认15)
            signal_period: 信号线周期 (默认9)
            
        Returns:
            信号序列
            
        逻辑:
            TRIX上穿信号线买入，下穿卖出
        """
        close = data['close']
        
        # 三重EMA
        ema1 = close.ewm(span=period, adjust=False).mean()
        ema2 = ema1.ewm(span=period, adjust=False).mean()
        ema3 = ema2.ewm(span=period, adjust=False).mean()
        
        # TRIX = 三重EMA的变化率(%)
        trix = (ema3 - ema3.shift(1)) / ema3.shift(1) * 100
        
        # 信号线
        signal_line = trix.ewm(span=signal_period, adjust=False).mean()
        
        signals = pd.Series(0, index=data.index)
        
        # TRIX上穿信号线买入，下穿卖出
        buy_signal = (trix > signal_line) & (trix.shift(1) <= signal_line.shift(1))
        sell_signal = (trix < signal_line) & (trix.shift(1) >= signal_line.shift(1))
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def aroon(data: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Aroon (阿隆指标) 趋势强度指标
        
        Tushar Chande开发，判断趋势强度和方向
        
        Args:
            data: OHLCV DataFrame
            period: Aroon周期 (默认14)
            
        Returns:
            信号序列
            
        逻辑:
            Aroon上穿上穿70且Aroon下穿30买入
        """
        high = data['high']
        low = data['low']
        
        # 计算Aroon Up和Aroon Down
        # Aroon Up = ((period - 距离最高点的天数) / period) * 100
        # Aroon Down = ((period - 距离最低点的天数) / period) * 100
        
        def get_days_since_high(x):
            return period - np.argmax(x) if len(x) > 0 else period
        
        def get_days_since_low(x):
            return period - np.argmin(x) if len(x) > 0 else period
        
        aroon_up = high.rolling(window=period).apply(
            lambda x: ((period - get_days_since_high(x)) / period) * 100
        )
        aroon_down = low.rolling(window=period).apply(
            lambda x: ((period - get_days_since_low(x)) / period) * 100
        )
        
        signals = pd.Series(0, index=data.index)
        
        # Aroon Up > 70 且 Aroon Down < 30 为强上升趋势
        buy_signal = (aroon_up > 70) & (aroon_down < 30) & \
                     (~((aroon_up.shift(1) > 70) & (aroon_down.shift(1) < 30)))
        
        # Aroon Up < 30 且 Aroon Down > 70 为强下降趋势
        sell_signal = (aroon_up < 30) & (aroon_down > 70) & \
                      (~((aroon_up.shift(1) < 30) & (aroon_down.shift(1) > 70)))
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def ultimate_oscillator(data: pd.DataFrame, 
                           short_period: int = 7,
                           medium_period: int = 14,
                           long_period: int = 28) -> pd.Series:
        """
        Ultimate Oscillator (终极震荡指标)
        
        Larry Williams开发，结合三个周期的动量
        
        Args:
            data: OHLCV DataFrame
            short_period: 短周期 (默认7)
            medium_period: 中周期 (默认14)
            long_period: 长周期 (默认28)
            
        Returns:
            信号序列
            
        逻辑:
            UO < 30 超卖买入，UO > 70 超买卖出
        """
        high = data['high']
        low = data['low']
        close = data['close']
        
        # 真实最低价
        true_low = pd.concat([low, close.shift(1)], axis=1).min(axis=1)
        # 真实最高价
        true_high = pd.concat([high, close.shift(1)], axis=1).max(axis=1)
        
        # 买入压力
        buying_pressure = close - true_low
        # 真实区间
        true_range = true_high - true_low
        
        # 计算三个周期的平均值
        avg_short = buying_pressure.rolling(short_period).sum() / true_range.rolling(short_period).sum()
        avg_medium = buying_pressure.rolling(medium_period).sum() / true_range.rolling(medium_period).sum()
        avg_long = buying_pressure.rolling(long_period).sum() / true_range.rolling(long_period).sum()
        
        # Ultimate Oscillator
        uo = 100 * ((4 * avg_short) + (2 * avg_medium) + avg_long) / 7
        
        signals = pd.Series(0, index=data.index)
        
        # UO < 30 买入，UO > 70 卖出
        buy_signal = (uo < 30) & (uo.shift(1) >= 30)
        sell_signal = (uo > 70) & (uo.shift(1) <= 70)
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def chaikin_money_flow(data: pd.DataFrame, period: int = 20) -> pd.Series:
        """
        Chaikin Money Flow (CMF) 蔡金资金流量
        
        Marc Chaikin开发，衡量资金流向
        
        Args:
            data: OHLCV DataFrame
            period: CMF周期 (默认20)
            
        Returns:
            信号序列
            
        逻辑:
            CMF > 0 资金流入买入，CMF < 0 资金流出卖出
        """
        high = data['high']
        low = data['low']
        close = data['close']
        volume = data['volume']
        
        # 资金流量乘数
        money_flow_multiplier = ((close - low) - (high - close)) / (high - low)
        money_flow_multiplier = money_flow_multiplier.replace([np.inf, -np.inf], 0).fillna(0)
        
        # 资金流量体积
        money_flow_volume = money_flow_multiplier * volume
        
        # CMF
        cmf = money_flow_volume.rolling(window=period).sum() / volume.rolling(window=period).sum()
        
        signals = pd.Series(0, index=data.index)
        
        # CMF上穿0买入，下穿0卖出
        buy_signal = (cmf > 0) & (cmf.shift(1) <= 0)
        sell_signal = (cmf < 0) & (cmf.shift(1) >= 0)
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def keltner_channel(data: pd.DataFrame, 
                       period: int = 20,
                       atr_multiplier: float = 2.0) -> pd.Series:
        """
        Keltner Channel (肯特纳通道)
        
        Chester Keltner开发，类似布林带但用ATR
        
        Args:
            data: OHLCV DataFrame
            period: EMA周期 (默认20)
            atr_multiplier: ATR倍数 (默认2.0)
            
        Returns:
            信号序列
            
        逻辑:
            价格上穿上轨买入，下穿下轨卖出
        """
        high = data['high']
        low = data['low']
        close = data['close']
        
        # 中轨 = EMA
        middle_line = close.ewm(span=period, adjust=False).mean()
        
        # ATR
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        # 上轨和下轨
        upper_band = middle_line + (atr_multiplier * atr)
        lower_band = middle_line - (atr_multiplier * atr)
        
        signals = pd.Series(0, index=data.index)
        
        # 突破上轨买入，跌破下轨卖出
        buy_signal = (close > upper_band) & (close.shift(1) <= upper_band.shift(1))
        sell_signal = (close < lower_band) & (close.shift(1) >= lower_band.shift(1))
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def rate_of_change(data: pd.DataFrame, period: int = 12) -> pd.Series:
        """
        ROC (Rate of Change) 变化率指标
        
        简单的动量指标
        
        Args:
            data: OHLCV DataFrame
            period: ROC周期 (默认12)
            
        Returns:
            信号序列
            
        逻辑:
            ROC > 0 买入，ROC < 0 卖出
        """
        close = data['close']
        
        # ROC = ((今日收盘价 - N日前收盘价) / N日前收盘价) * 100
        roc = ((close - close.shift(period)) / close.shift(period)) * 100
        
        signals = pd.Series(0, index=data.index)
        
        # ROC上穿0买入，下穿0卖出
        buy_signal = (roc > 0) & (roc.shift(1) <= 0)
        sell_signal = (roc < 0) & (roc.shift(1) >= 0)
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def tsi(data: pd.DataFrame, 
           long_period: int = 25,
           short_period: int = 13) -> pd.Series:
        """
        TSI (True Strength Index) 真实强弱指数
        
        双重平滑的动量指标
        
        Args:
            data: OHLCV DataFrame
            long_period: 长期周期 (默认25)
            short_period: 短期周期 (默认13)
            
        Returns:
            信号序列
            
        逻辑:
            TSI上穿0买入，下穿0卖出
        """
        close = data['close']
        
        # 价格变化
        price_change = close.diff()
        
        # 双重平滑
        double_smoothed_pc = price_change.ewm(span=long_period, adjust=False).mean().ewm(span=short_period, adjust=False).mean()
        double_smoothed_abs_pc = price_change.abs().ewm(span=long_period, adjust=False).mean().ewm(span=short_period, adjust=False).mean()
        
        # TSI
        tsi = (double_smoothed_pc / double_smoothed_abs_pc) * 100
        
        signals = pd.Series(0, index=data.index)
        
        # TSI上穿0买入，下穿0卖出
        buy_signal = (tsi > 0) & (tsi.shift(1) <= 0)
        sell_signal = (tsi < 0) & (tsi.shift(1) >= 0)
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def vortex_indicator(data: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Vortex Indicator (漩涡指标)
        
        Etienne Botes和Douglas Siepman开发，判断趋势方向
        
        Args:
            data: OHLCV DataFrame
            period: 周期 (默认14)
            
        Returns:
            信号序列
            
        逻辑:
            VI+ > VI- 上升趋势买入，反之卖出
        """
        high = data['high']
        low = data['low']
        close = data['close']
        
        # 真实区间
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # VM+ 和 VM-
        vm_plus = abs(high - low.shift(1))
        vm_minus = abs(low - high.shift(1))
        
        # VI+ 和 VI-
        vi_plus = vm_plus.rolling(window=period).sum() / tr.rolling(window=period).sum()
        vi_minus = vm_minus.rolling(window=period).sum() / tr.rolling(window=period).sum()
        
        signals = pd.Series(0, index=data.index)
        
        # VI+上穿VI-买入，下穿卖出
        buy_signal = (vi_plus > vi_minus) & (vi_plus.shift(1) <= vi_minus.shift(1))
        sell_signal = (vi_plus < vi_minus) & (vi_plus.shift(1) >= vi_minus.shift(1))
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def awesome_oscillator(data: pd.DataFrame, 
                          short_period: int = 5,
                          long_period: int = 34) -> pd.Series:
        """
        Awesome Oscillator (AO) 动量震荡指标
        
        Bill Williams开发，基于中间价
        
        Args:
            data: OHLCV DataFrame
            short_period: 短周期 (默认5)
            long_period: 长周期 (默认34)
            
        Returns:
            信号序列
            
        逻辑:
            AO上穿0买入，下穿0卖出
        """
        high = data['high']
        low = data['low']
        
        # 中间价
        median_price = (high + low) / 2
        
        # 简单移动平均
        sma_short = median_price.rolling(window=short_period).mean()
        sma_long = median_price.rolling(window=long_period).mean()
        
        # AO
        ao = sma_short - sma_long
        
        signals = pd.Series(0, index=data.index)
        
        # AO上穿0买入，下穿0卖出
        buy_signal = (ao > 0) & (ao.shift(1) <= 0)
        sell_signal = (ao < 0) & (ao.shift(1) >= 0)
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals
    
    @staticmethod
    def alligator(data: pd.DataFrame,
                 jaw_period: int = 13,
                 teeth_period: int = 8,
                 lips_period: int = 5) -> pd.Series:
        """
        Alligator (鳄鱼线)
        
        Bill Williams开发，三条平滑移动平均线
        
        Args:
            data: OHLCV DataFrame
            jaw_period: 颚线周期 (默认13)
            teeth_period: 齿线周期 (默认8)
            lips_period: 唇线周期 (默认5)
            
        Returns:
            信号序列
            
        逻辑:
            唇线上穿齿线和颚线买入 (鳄鱼张嘴)
            唇线下穿齿线和颚线卖出 (鳄鱼闭嘴)
        """
        median_price = (data['high'] + data['low']) / 2
        
        # 鳄鱼线 (SMMA)
        jaw = median_price.rolling(window=jaw_period).mean().shift(8)      # 颚线 (蓝)
        teeth = median_price.rolling(window=teeth_period).mean().shift(5)  # 齿线 (红)
        lips = median_price.rolling(window=lips_period).mean().shift(3)    # 唇线 (绿)
        
        signals = pd.Series(0, index=data.index)
        
        # 唇线上穿齿线和颚线 (买入)
        buy_signal = (lips > teeth) & (lips > jaw) & \
                     ((lips.shift(1) <= teeth.shift(1)) | (lips.shift(1) <= jaw.shift(1)))
        
        # 唇线下穿齿线和颚线 (卖出)
        sell_signal = (lips < teeth) & (lips < jaw) & \
                      ((lips.shift(1) >= teeth.shift(1)) | (lips.shift(1) >= jaw.shift(1)))
        
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
            'kdj': StrategyGenerator.kdj,
            'cci': StrategyGenerator.cci,
            'williams_r': StrategyGenerator.williams_r,
            'ichimoku': StrategyGenerator.ichimoku,
            'parabolic_sar': StrategyGenerator.parabolic_sar,
            'obv': StrategyGenerator.obv,
            'adx': StrategyGenerator.adx,
            'mfi': StrategyGenerator.mfi,
            'vwap': StrategyGenerator.vwap,
            'stochastic': StrategyGenerator.stochastic,
            'heikin_ashi': StrategyGenerator.heikin_ashi,
            'trix': StrategyGenerator.trix,
            'aroon': StrategyGenerator.aroon,
            'ultimate_oscillator': StrategyGenerator.ultimate_oscillator,
            'chaikin_money_flow': StrategyGenerator.chaikin_money_flow,
            'keltner_channel': StrategyGenerator.keltner_channel,
            'rate_of_change': StrategyGenerator.rate_of_change,
            'tsi': StrategyGenerator.tsi,
            'vortex_indicator': StrategyGenerator.vortex_indicator,
            'awesome_oscillator': StrategyGenerator.awesome_oscillator,
            'alligator': StrategyGenerator.alligator,
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
            'supertrend': [
                {'period': 10, 'multiplier': 3.0},
                {'period': 14, 'multiplier': 2.0},
                {'period': 20, 'multiplier': 1.5},
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
            'momentum', 'atr_breakout', 'donchian', 'volume_price',
            'supertrend'  # Jarvis新增
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
        'momentum', 'atr_breakout', 'donchian', 'volume_price',
        'supertrend', 'kdj', 'cci', 'williams_r',
        'ichimoku', 'parabolic_sar', 'obv', 'adx',
        'mfi', 'vwap', 'stochastic', 'heikin_ashi',
        'trix', 'aroon', 'ultimate_oscillator', 'chaikin_money_flow',
        'keltner_channel', 'rate_of_change', 'tsi', 'vortex_indicator',
        'awesome_oscillator', 'alligator',
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
        'supertrend': generator.supertrend,
        'kdj': generator.kdj,
        'cci': generator.cci,
        'williams_r': generator.williams_r,
        'ichimoku': generator.ichimoku,
        'parabolic_sar': generator.parabolic_sar,
        'obv': generator.obv,
        'adx': generator.adx,
        'mfi': generator.mfi,
        'vwap': generator.vwap,
        'stochastic': generator.stochastic,
        'heikin_ashi': generator.heikin_ashi,
        'trix': generator.trix,
        'aroon': generator.aroon,
        'ultimate_oscillator': generator.ultimate_oscillator,
        'chaikin_money_flow': generator.chaikin_money_flow,
        'keltner_channel': generator.keltner_channel,
        'rate_of_change': generator.rate_of_change,
        'tsi': generator.tsi,
        'vortex_indicator': generator.vortex_indicator,
        'awesome_oscillator': generator.awesome_oscillator,
        'alligator': generator.alligator,
    }
    
    if strategy_name not in strategy_map:
        raise ValueError(f"未知策略: {strategy_name}. 可用策略: {list(strategy_map.keys())}")
    
    return strategy_map[strategy_name](data, **params)
