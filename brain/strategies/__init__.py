"""
策略模块
提供策略基类和具体策略实现
"""

from .base import BaseStrategy
from .dual_ma import DualMAStrategy

__all__ = ['BaseStrategy', 'DualMAStrategy']
