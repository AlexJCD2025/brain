"""
回测数据模型
定义 Position、TradeRecord、EquitySnapshot 等核心数据结构
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass(frozen=True)
class Position:
    """
    持仓数据模型
    
    Attributes:
        symbol: 股票代码
        direction: 方向 (1=多仓, -1=空仓)
        entry_price: 入场价格
        entry_time: 入场时间
        size: 持仓数量
        leverage: 杠杆倍数 (默认1.0)
        entry_bar_idx: 入场时的K线索引
        entry_commission: 入场手续费
    """
    symbol: str
    direction: int
    entry_price: float
    entry_time: datetime
    size: float
    leverage: float = 1.0
    entry_bar_idx: int = 0
    entry_commission: float = 0.0


@dataclass(frozen=True)
class TradeRecord:
    """
    交易记录数据模型
    
    Attributes:
        symbol: 股票代码
        direction: 方向 (1=多, -1=空)
        entry_price: 入场价格
        exit_price: 出场价格
        entry_time: 入场时间
        exit_time: 出场时间
        size: 交易数量
        leverage: 杠杆倍数
        pnl: 实现盈亏 (绝对金额)
        pnl_pct: 收益率百分比
        exit_reason: 出场原因
        holding_bars: 持仓K线数
        commission: 总手续费
    """
    symbol: str
    direction: int
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    size: float
    leverage: float
    pnl: float
    pnl_pct: float
    exit_reason: str
    holding_bars: int
    commission: float


@dataclass(frozen=True)
class EquitySnapshot:
    """
    权益快照数据模型
    
    Attributes:
        timestamp: 时间戳
        capital: 可用资金
        unrealized: 浮动盈亏
        equity: 总权益 (capital + margin + unrealized)
        positions: 持仓数量
    """
    timestamp: datetime
    capital: float
    unrealized: float
    equity: float
    positions: int


@dataclass
class BacktestConfig:
    """
    回测配置数据模型
    
    Attributes:
        initial_cash: 初始资金
        commission_rate: 手续费率
        commission_min: 最低手续费
        slippage: 滑点率
        leverage: 杠杆倍数
        stamp_tax: 印花税率 (A股)
        transfer_fee: 过户费率 (A股)
    """
    initial_cash: float = 100000.0
    commission_rate: float = 0.0003
    commission_min: float = 0.0
    slippage: float = 0.001
    leverage: float = 1.0
    stamp_tax: float = 0.0
    transfer_fee: float = 0.0
