"""
双均线策略模块
基于金叉/死叉进行买卖决策
"""

import backtrader as bt
from .base import BaseStrategy


class DualMAStrategy(BaseStrategy):
    """
    双均线策略
    当快线上穿慢线（金叉）时买入
    当快线下穿慢线（死叉）时卖出
    """
    
    params = (
        ('fast_period', 10),
        ('slow_period', 30),
    )
    
    def __init__(self):
        """初始化双均线策略"""
        super().__init__()
        
        # 计算快速和慢速移动平均线
        self.fast_ma = bt.indicators.SimpleMovingAverage(
            self.datas[0].close, 
            period=self.params.fast_period
        )
        self.slow_ma = bt.indicators.SimpleMovingAverage(
            self.datas[0].close, 
            period=self.params.slow_period
        )
        
        # 计算交叉指标
        self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)
    
    def next(self):
        """
        策略逻辑：在每个时间步调用
        金叉买入，死叉卖出
        """
        # 检查是否有待执行订单
        if self.order:
            return
        
        # 检查是否持仓
        if not self.position:
            # 没有持仓，检查金叉买入信号
            if self.crossover > 0:
                self.log(f'金叉信号: 快线({self.params.fast_period})上穿慢线({self.params.slow_period})')
                self.log(f'买入价格: {self.datas[0].close[0]:.2f}')
                self.order = self.buy()
        else:
            # 有持仓，检查死叉卖出信号
            if self.crossover < 0:
                self.log(f'死叉信号: 快线({self.params.fast_period})下穿慢线({self.params.slow_period})')
                self.log(f'卖出价格: {self.datas[0].close[0]:.2f}')
                self.order = self.sell()
