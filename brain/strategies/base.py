"""
策略基类模块
继承 backtrader.Strategy 实现基础策略功能
"""

import backtrader as bt
from abc import abstractmethod
from datetime import datetime


class BaseStrategy(bt.Strategy):
    """
    策略基类，继承 backtrader.Strategy
    提供基础功能：日志记录、订单通知、交易分析
    """
    
    params = (
        ('verbose', False),
    )
    
    def __init__(self):
        """初始化策略"""
        self.order = None
        self.trades = []
    
    def log(self, txt, dt=None):
        """
        日志输出函数
        
        Args:
            txt: 日志内容
            dt: 日期时间，默认为当前数据日期
        """
        if self.params.verbose:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()} {txt}')
    
    def notify_order(self, order):
        """
        订单状态回调函数
        
        Args:
            order: backtrader 订单对象
        """
        if order.status in [order.Submitted, order.Accepted]:
            # 订单已提交/接受，等待执行
            return
        
        if order.status in [order.Completed]:
            # 订单执行完成
            if order.isbuy():
                self.log(f'买入执行, 价格: {order.executed.price:.2f}, '
                        f'数量: {order.executed.size}, '
                        f'成本: {order.executed.value:.2f}, '
                        f'手续费: {order.executed.comm:.2f}')
            else:
                self.log(f'卖出执行, 价格: {order.executed.price:.2f}, '
                        f'数量: {order.executed.size}, '
                        f'成本: {order.executed.value:.2f}, '
                        f'手续费: {order.executed.comm:.2f}')
            
            # 记录交易
            trade_record = {
                'datetime': self.datas[0].datetime.datetime(0),
                'type': 'buy' if order.isbuy() else 'sell',
                'price': order.executed.price,
                'size': order.executed.size,
                'value': order.executed.value,
                'commission': order.executed.comm,
            }
            self.trades.append(trade_record)
            
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'订单取消/保证金不足/拒绝')
        
        # 重置订单状态
        self.order = None
    
    @abstractmethod
    def next(self):
        """
        抽象方法，子类必须实现
        在每个时间步调用，实现策略逻辑
        """
        pass
    
    def get_analytics(self):
        """
        获取交易分析数据
        
        Returns:
            dict: 包含交易统计信息的字典
        """
        total_trades = len(self.trades)
        buy_trades = [t for t in self.trades if t['type'] == 'buy']
        sell_trades = [t for t in self.trades if t['type'] == 'sell']
        
        total_commission = sum(t['commission'] for t in self.trades)
        total_value = sum(t['value'] for t in self.trades)
        
        return {
            'total_trades': total_trades,
            'buy_count': len(buy_trades),
            'sell_count': len(sell_trades),
            'total_commission': total_commission,
            'total_value': total_value,
            'trades': self.trades,
        }
