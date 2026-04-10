"""
回测引擎模块
提供不同市场的回测引擎实现
"""
from brain.backtest.base_engine import BaseEngine
from brain.backtest.engines.china_a import AShareEngine

__all__ = ["BaseEngine", "AShareEngine"]
