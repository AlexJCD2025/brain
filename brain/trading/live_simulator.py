"""
C. 实盘模拟交易框架

功能:
1. 每日信号生成和推送
2. 模拟订单执行和持仓管理
3. 实时盈亏计算
4. 风险监控和报警
5. 交易记录和报告
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

import pandas as pd
import numpy as np


@dataclass
class Position:
    """持仓信息"""
    symbol: str
    direction: int  # 1=多, -1=空
    entry_price: float
    entry_time: datetime
    size: float
    unrealized_pnl: float = 0.0


@dataclass
class TradeRecord:
    """交易记录"""
    symbol: str
    action: str  # 'buy', 'sell'
    price: float
    size: float
    timestamp: datetime
    pnl: Optional[float] = None
    commission: float = 0.0


@dataclass
class DailyReport:
    """日报"""
    date: str
    cash: float
    positions_value: float
    total_value: float
    daily_pnl: float
    daily_return: float
    trades: List[TradeRecord]


class LiveSimulator:
    """
    实盘模拟器
    
    使用方法:
        simulator = LiveSimulator(initial_cash=100000)
        simulator.add_data(data)
        
        for date in dates:
            signal = generate_signal(data.loc[:date])
            simulator.on_bar(date, signal, data.loc[date])
    """
    
    def __init__(self, initial_cash: float = 100000.0, 
                 commission_rate: float = 0.00025,
                 max_position_pct: float = 0.95):
        """
        初始化模拟器
        
        Args:
            initial_cash: 初始资金
            commission_rate: 手续费率
            max_position_pct: 最大仓位比例
        """
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.commission_rate = commission_rate
        self.max_position_pct = max_position_pct
        
        self.positions: Dict[str, Position] = {}
        self.trades: List[TradeRecord] = []
        self.daily_reports: List[DailyReport] = []
        
        self.current_date: Optional[datetime] = None
        self.total_commission = 0.0
        
    def on_bar(self, timestamp: datetime, signal: int, 
               bar: pd.Series, symbol: str = "STOCK") -> Dict:
        """
        处理每根K线
        
        Args:
            timestamp: 时间戳
            signal: 交易信号 (1=买入, -1=卖出, 0=持有)
            bar: OHLCV数据
            symbol: 股票代码
            
        Returns:
            交易结果字典
        """
        self.current_date = timestamp
        price = bar['close']
        
        result = {
            'timestamp': timestamp,
            'signal': signal,
            'price': price,
            'action': 'hold',
            'trades': []
        }
        
        current_pos = self.positions.get(symbol)
        
        # 根据信号执行交易
        if signal == 1 and (current_pos is None or current_pos.direction != 1):
            # 买入信号
            if current_pos and current_pos.direction == -1:
                # 先平空
                trade = self._close_position(symbol, price, timestamp)
                result['trades'].append(asdict(trade))
            
            # 开多
            trade = self._open_position(symbol, 1, price, timestamp)
            if trade:
                result['action'] = 'buy'
                result['trades'].append(asdict(trade))
                
        elif signal == -1 and (current_pos is None or current_pos.direction != -1):
            # 卖出信号 (A股不允许做空，这里只能平仓)
            if current_pos and current_pos.direction == 1:
                trade = self._close_position(symbol, price, timestamp)
                result['action'] = 'sell'
                result['trades'].append(asdict(trade))
        
        # 更新持仓盈亏
        self._update_unrealized_pnl(symbol, price)
        
        return result
    
    def _open_position(self, symbol: str, direction: int, 
                      price: float, timestamp: datetime) -> Optional[TradeRecord]:
        """开仓"""
        # 计算可买入数量 (A股100股整数倍)
        max_amount = self.cash * self.max_position_pct
        raw_size = max_amount / price
        size = int(raw_size / 100) * 100
        
        if size < 100:
            return None
        
        # 计算成本
        cost = size * price
        commission = max(cost * self.commission_rate, 5.0)  # 最低5元
        total_cost = cost + commission
        
        if total_cost > self.cash:
            return None
        
        # 扣除资金
        self.cash -= total_cost
        self.total_commission += commission
        
        # 创建持仓
        self.positions[symbol] = Position(
            symbol=symbol,
            direction=direction,
            entry_price=price,
            entry_time=timestamp,
            size=size
        )
        
        # 记录交易
        trade = TradeRecord(
            symbol=symbol,
            action='buy' if direction == 1 else 'sell',
            price=price,
            size=size,
            timestamp=timestamp,
            commission=commission
        )
        self.trades.append(trade)
        
        return trade
    
    def _close_position(self, symbol: str, price: float, 
                       timestamp: datetime) -> TradeRecord:
        """平仓"""
        pos = self.positions.pop(symbol)
        
        # 计算盈亏
        if pos.direction == 1:
            pnl = (price - pos.entry_price) * pos.size
        else:
            pnl = (pos.entry_price - price) * pos.size
        
        # 计算手续费
        amount = pos.size * price
        commission = max(amount * self.commission_rate, 5.0)
        
        # 返还资金
        self.cash += amount - commission
        self.total_commission += commission
        
        # 记录交易
        trade = TradeRecord(
            symbol=symbol,
            action='sell' if pos.direction == 1 else 'buy',
            price=price,
            size=pos.size,
            timestamp=timestamp,
            pnl=pnl,
            commission=commission
        )
        self.trades.append(trade)
        
        return trade
    
    def _update_unrealized_pnl(self, symbol: str, current_price: float):
        """更新未实现盈亏"""
        if symbol in self.positions:
            pos = self.positions[symbol]
            if pos.direction == 1:
                pos.unrealized_pnl = (current_price - pos.entry_price) * pos.size
            else:
                pos.unrealized_pnl = (pos.entry_price - current_price) * pos.size
    
    def generate_daily_report(self) -> DailyReport:
        """生成日报"""
        positions_value = sum(
            pos.size * pos.entry_price + pos.unrealized_pnl 
            for pos in self.positions.values()
        )
        
        total_value = self.cash + positions_value
        
        # 计算当日盈亏
        if self.daily_reports:
            last_value = self.daily_reports[-1].total_value
            daily_pnl = total_value - last_value
            daily_return = daily_pnl / last_value * 100
        else:
            daily_pnl = total_value - self.initial_cash
            daily_return = daily_pnl / self.initial_cash * 100
        
        # 当日交易
        today_trades = [
            t for t in self.trades 
            if t.timestamp.date() == self.current_date.date()
        ]
        
        report = DailyReport(
            date=self.current_date.strftime('%Y-%m-%d'),
            cash=self.cash,
            positions_value=positions_value,
            total_value=total_value,
            daily_pnl=daily_pnl,
            daily_return=daily_return,
            trades=today_trades
        )
        
        self.daily_reports.append(report)
        return report
    
    def get_summary(self) -> Dict:
        """获取交易总结"""
        if not self.daily_reports:
            return {}
        
        final_value = self.daily_reports[-1].total_value
        total_return = (final_value - self.initial_cash) / self.initial_cash * 100
        
        # 计算最大回撤
        values = [r.total_value for r in self.daily_reports]
        peak = values[0]
        max_dd = 0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100
            if dd > max_dd:
                max_dd = dd
        
        # 交易统计
        winning_trades = [t for t in self.trades if t.pnl and t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl and t.pnl < 0]
        
        return {
            'initial_cash': self.initial_cash,
            'final_value': final_value,
            'total_return': total_return,
            'max_drawdown': max_dd,
            'total_trades': len(self.trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(self.trades) * 100 if self.trades else 0,
            'total_commission': self.total_commission,
            'current_cash': self.cash,
            'current_positions': len(self.positions)
        }
    
    def save_results(self, output_dir: str = "reports"):
        """保存交易结果"""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存日报
        report_file = f"{output_dir}/live_simulation_{timestamp}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump({
                'summary': self.get_summary(),
                'daily_reports': [asdict(r) for r in self.daily_reports],
                'trades': [asdict(t) for t in self.trades]
            }, f, ensure_ascii=False, indent=2, default=str)
        
        return report_file
    
    def print_daily_report(self, report: DailyReport):
        """打印日报"""
        print(f"\n📊 {report.date} 日报")
        print(f"   现金: ¥{report.cash:,.2f}")
        print(f"   持仓市值: ¥{report.positions_value:,.2f}")
        print(f"   总资产: ¥{report.total_value:,.2f}")
        print(f"   当日盈亏: ¥{report.daily_pnl:,.2f} ({report.daily_return:+.2f}%)")
        
        if report.trades:
            print(f"   当日交易: {len(report.trades)} 笔")
            for t in report.trades:
                pnl_str = f"盈亏: ¥{t.pnl:,.2f}" if t.pnl else ""
                print(f"     {t.action} {t.size}股 @ ¥{t.price} {pnl_str}")


def example_usage():
    """使用示例"""
    print("=" * 80)
    print("🚀 实盘模拟器使用示例")
    print("=" * 80)
    
    # 创建模拟器
    sim = LiveSimulator(initial_cash=100000)
    
    # 模拟10天交易
    print("\n📈 模拟交易10天...")
    
    for i in range(10):
        date = datetime(2024, 1, 1) + timedelta(days=i)
        
        # 模拟价格
        price = 100 + i * 0.5 + np.random.randn() * 2
        bar = pd.Series({'close': price, 'open': price - 1, 'high': price + 1, 'low': price - 1})
        
        # 模拟信号 (每3天买入，每5天卖出)
        signal = 0
        if i % 3 == 0:
            signal = 1
        elif i % 5 == 0:
            signal = -1
        
        # 处理bar
        result = sim.on_bar(date, signal, bar)
        
        # 生成日报
        report = sim.generate_daily_report()
        
        # 打印
        if result['action'] != 'hold':
            sim.print_daily_report(report)
    
    # 打印总结
    print("\n" + "=" * 80)
    print("📊 交易总结")
    print("=" * 80)
    
    summary = sim.get_summary()
    print(f"   初始资金: ¥{summary['initial_cash']:,.2f}")
    print(f"   最终资产: ¥{summary['final_value']:,.2f}")
    print(f"   总收益率: {summary['total_return']:+.2f}%")
    print(f"   最大回撤: {summary['max_drawdown']:.2f}%")
    print(f"   总交易数: {summary['total_trades']}")
    print(f"   胜率: {summary['win_rate']:.1f}%")
    print(f"   总手续费: ¥{summary['total_commission']:.2f}")
    
    # 保存结果
    filename = sim.save_results()
    print(f"\n💾 结果已保存: {filename}")


if __name__ == "__main__":
    import numpy as np
    example_usage()
