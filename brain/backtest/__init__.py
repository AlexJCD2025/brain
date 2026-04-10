"""
回测引擎模块
提供量化策略回测功能
"""
from brain.backtest.engine import BacktestEngine
from brain.backtest.base_engine import BaseEngine
from brain.backtest.engines import AShareEngine
from brain.backtest.models import (
    Position,
    TradeRecord,
    EquitySnapshot,
    BacktestConfig
)
from brain.backtest.reporter import BacktestReporter

__all__ = [
    "BacktestEngine",
    "BaseEngine",
    "AShareEngine",
    "Position",
    "TradeRecord",
    "EquitySnapshot",
    "BacktestConfig",
    "BacktestReporter"
]
