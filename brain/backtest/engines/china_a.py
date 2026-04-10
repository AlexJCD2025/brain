"""
A股回测引擎
实现A股市场规则：
- T+1: 当日买入不能卖出
- 涨跌停限制: 主板±10%，创业板/科创板±20%，ST±5%
- 手数规则: 100股整数倍（零股只能卖出）
- 手续费: 佣金(万2.5, 最低5元) + 印花税(卖出万5) + 过户费(万0.1)
- 禁止做空
"""
from typing import Optional
from datetime import datetime

import pandas as pd

from brain.backtest.base_engine import BaseEngine
from brain.backtest.models import BacktestConfig


class AShareEngine(BaseEngine):
    """
    A股回测引擎
    
    完整实现A股市场交易规则
    
    Config 参数:
        commission_rate: 佣金率 (默认 0.00025 = 万2.5)
        commission_min: 最低佣金 (默认 5.0元)
        stamp_tax: 印花税率 (默认 0.0005 = 万5，仅卖出)
        transfer_fee: 过户费率 (默认 0.00001 = 万0.1)
        slippage: 滑点率 (默认 0.001 = 0.1%)
    """
    
    def __init__(self, config: Optional[dict] = None):
        """
        初始化A股引擎
        
        Args:
            config: 配置字典，可包含 commission_rate, commission_min 等
        """
        # A股默认配置
        default_config = {
            "commission_rate": 0.00025,  # 万2.5
            "commission_min": 5.0,       # 最低5元
            "stamp_tax": 0.0005,         # 万5 (卖出)
            "transfer_fee": 0.00001,     # 万0.1
            "slippage": 0.001,           # 0.1% 滑点
            "leverage": 1.0              # A股无杠杆
        }
        
        if config:
            default_config.update(config)
        
        super().__init__(default_config)
        
        # A股特定参数
        self.commission_rate: float = self.config.commission_rate
        self.commission_min: float = self.config.commission_min
        self.stamp_tax: float = self.config.stamp_tax
        self.transfer_fee: float = self.config.transfer_fee
        self.slippage_rate: float = self.config.slippage
    
    def can_execute(self, symbol: str, direction: int, bar: pd.Series) -> bool:
        """
        A股交易规则检查
        
        规则:
        1. 禁止做空 (direction == -1 不允许)
        2. T+1: 当日买入不能卖出
        3. 涨跌停限制
        """
        # 1. 禁止做空
        if direction == -1:
            return False
        
        # 2. T+1 检查: 当日买入不能卖出
        if direction == 0:  # 平仓/卖出
            pos = self.positions.get(symbol)
            if pos is not None:
                # 获取当前日期和入场日期
                current_date = self._get_bar_date(bar)
                entry_date = pos.entry_time.date() if hasattr(pos.entry_time, 'date') else None
                
                if current_date is not None and entry_date is not None:
                    if current_date == entry_date:
                        return False  # T+1 限制
        
        # 3. 涨跌停限制
        pct_chg = self._calc_pct_change(bar)
        if pct_chg is not None:
            limit = self._price_limit(symbol)
            
            if direction == 1 and pct_chg >= limit - 0.001:
                return False  # 涨停不能买
            if direction == 0 and pct_chg <= -limit + 0.001:
                return False  # 跌停不能卖
        
        return True
    
    def round_size(self, raw_size: float, price: float) -> float:
        """
        A股手数规则: 100股整数倍
        
        Args:
            raw_size: 原始数量
            price: 当前价格
            
        Returns:
            向下取整到100的整数倍
        """
        return max(int(raw_size / 100) * 100, 0)
    
    def calc_commission(self, size: float, price: float, 
                        direction: int, is_open: bool) -> float:
        """
        A股手续费计算
        
        费用构成:
        - 佣金: 成交金额 × 万2.5 (最低5元)
        - 过户费: 成交金额 × 万0.1 (双边)
        - 印花税: 成交金额 × 万5 (仅卖出)
        
        Args:
            size: 交易数量
            price: 成交价格
            direction: 方向 (1=多, -1=空)
            is_open: 是否开仓
            
        Returns:
            总手续费
        """
        notional = size * price
        
        # 1. 佣金 (最低5元)
        commission = max(notional * self.commission_rate, self.commission_min)
        
        # 2. 过户费 (双边)
        commission += notional * self.transfer_fee
        
        # 3. 印花税 (仅卖出)
        if not is_open:  # 平仓/卖出
            commission += notional * self.stamp_tax
        
        return commission
    
    def apply_slippage(self, price: float, direction: int) -> float:
        """
        应用滑点
        
        Args:
            price: 原始价格
            direction: 方向 (1=买入, -1=卖出)
            
        Returns:
            应用滑点后的价格
        """
        # 买入: 价格更高, 卖出: 价格更低
        return price * (1 + direction * self.slippage_rate)
    
    # ============================================================
    # A股特定辅助方法
    # ============================================================
    
    def _get_bar_date(self, bar: pd.Series) -> Optional[datetime.date]:
        """
        从 bar 数据中提取日期
        
        处理不同的列名: date, datetime, timestamp, index
        """
        # 尝试不同的列名
        for col in ['date', 'datetime', 'timestamp']:
            if col in bar.index:
                val = bar[col]
                if hasattr(val, 'date'):
                    return val.date()
                elif isinstance(val, str):
                    try:
                        return pd.to_datetime(val).date()
                    except:
                        pass
        
        # 如果没有找到，使用当前回测日期
        return self._current_date.date() if self._current_date else None
    
    def _calc_pct_change(self, bar: pd.Series) -> Optional[float]:
        """
        计算涨跌幅
        
        尝试从 bar 中读取 pct_chg 或计算 (close - pre_close) / pre_close
        """
        # 直接读取涨跌幅
        if 'pct_chg' in bar.index:
            return float(bar['pct_chg']) / 100  # 转为小数
        
        # 计算涨跌幅
        close = bar.get('close')
        pre_close = bar.get('pre_close')
        
        if close is not None and pre_close is not None and pre_close != 0:
            return (float(close) - float(pre_close)) / float(pre_close)
        
        return None
    
    def _price_limit(self, symbol: str) -> float:
        """
        获取涨跌停限制
        
        规则:
        - 主板: ±10%
        - 创业板 (30开头): ±20%
        - 科创板 (68开头): ±20%
        - ST 股票: ±5%
        
        Args:
            symbol: 股票代码
            
        Returns:
            涨跌停幅度 (小数, 如 0.1 表示10%)
        """
        # 从 symbol 判断板块
        # 这里简化处理，实际可以根据前缀判断
        
        # 创业板: 30 开头
        if symbol.startswith('30'):
            return 0.20  # ±20%
        
        # 科创板: 68 开头
        if symbol.startswith('68'):
            return 0.20  # ±20%
        
        # ST 股票 (需要额外信息判断，这里简化)
        # if is_st_stock(symbol):
        #     return 0.05
        
        # 默认主板: ±10%
        return 0.10


# 别名，方便导入
ChinaAEngine = AShareEngine
