"""
回测引擎抽象基类
定义回测流程框架和抽象市场规则接口

设计模式：模板方法模式 (Template Method Pattern)
- 主干流程固定 (run_backtest)
- 市场规则抽象 (子类实现具体规则)
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime
import json

import pandas as pd
import numpy as np

from brain.backtest.models import Position, TradeRecord, EquitySnapshot, BacktestConfig


class BaseEngine(ABC):
    """
    回测引擎抽象基类
    
    所有市场引擎继承此类，实现具体的市场规则：
    - can_execute: 交易执行规则（涨跌停、T+1等）
    - round_size: 手数规则（A股100股整数倍）
    - calc_commission: 手续费计算
    - apply_slippage: 滑点模型
    - on_bar: 逐K线钩子（资金费、强平等）
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化回测引擎
        
        Args:
            config: 配置字典，包含 initial_cash, commission_rate 等
        """
        self.config = BacktestConfig(**(config or {}))
        self.initial_capital: float = self.config.initial_cash
        self.default_leverage: float = self.config.leverage
        
        # 回测状态
        self.capital: float = self.initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[TradeRecord] = []
        self.equity_snapshots: List[EquitySnapshot] = []
        self._bar_idx: int = 0
        self._current_date: Optional[datetime] = None
        
    # ============================================================
    # 抽象接口 (子类必须实现)
    # ============================================================
    
    @abstractmethod
    def can_execute(self, symbol: str, direction: int, bar: pd.Series) -> bool:
        """
        判断交易是否允许执行（市场规则检查）
        
        Args:
            symbol: 股票代码
            direction: 交易方向 (1=买入/开多, -1=卖出/开空, 0=平仓)
            bar: 当前K线数据 (包含 open, high, low, close, volume 等)
        
        Returns:
            True 如果允许执行，False 如果被规则阻止
            
        示例规则：
        - A股：涨停不能买，跌停不能卖，T+1当天不能卖
        - 期货：检查保证金、强平线
        -  crypto：无限制
        """
        pass
    
    @abstractmethod
    def round_size(self, raw_size: float, price: float) -> float:
        """
        根据市场规则调整持仓数量
        
        Args:
            raw_size: 原始目标数量
            price: 当前价格
            
        Returns:
            调整后的数量
            
        示例规则：
        - A股：向下取整到100的整数倍
        - 美股：整数股或支持小数股
        - 期货：按合约乘数调整
        """
        pass
    
    @abstractmethod
    def calc_commission(self, size: float, price: float, direction: int, is_open: bool) -> float:
        """
        计算交易手续费
        
        Args:
            size: 交易数量
            price: 成交价格
            direction: 方向 (1=多, -1=空)
            is_open: 是否开仓 (True=开仓, False=平仓)
            
        Returns:
            手续费金额
            
        示例规则：
        - A股：佣金(万2.5, 最低5元) + 印花税(卖出万5) + 过户费
        - 美股：固定费率或按股数
        """
        pass
    
    @abstractmethod
    def apply_slippage(self, price: float, direction: int) -> float:
        """
        应用滑点到成交价格
        
        Args:
            price: 原始价格
            direction: 方向 (1=买入, -1=卖出)
            
        Returns:
            应用滑点后的价格
            
        示例：
        - 买入：price * (1 + slippage)
        - 卖出：price * (1 - slippage)
        """
        pass
    
    def on_bar(self, symbol: str, bar: pd.Series, timestamp: datetime) -> None:
        """
        逐K线钩子（可选实现）
        
        用于处理每根K线的特殊逻辑：
        - 期货：计算资金费
        - 杠杆交易：检查强平
        - 分红除息处理
        
        Args:
            symbol: 股票代码
            bar: 当前K线数据
            timestamp: 时间戳
        """
        pass  # 默认空实现
    
    # ============================================================
    # PnL / 保证金计算钩子 (子类可覆盖)
    # ============================================================
    
    def _calc_pnl(self, symbol: str, direction: int, size: float,
                  entry_price: float, exit_price: float) -> float:
        """计算已实现盈亏 (子类可覆盖以支持合约乘数等)"""
        return direction * size * (exit_price - entry_price)
    
    def _calc_margin(self, symbol: str, size: float, price: float, leverage: float) -> float:
        """计算保证金 (子类可覆盖)"""
        return size * price / leverage
    
    def _calc_raw_size(self, symbol: str, target_notional: float, price: float) -> float:
        """计算原始数量"""
        if price <= 0:
            return 0.0
        return target_notional / price
    
    # ============================================================
    # 核心回测流程 (模板方法)
    # ============================================================
    
    def run_backtest(self, data: pd.DataFrame, signal_series: pd.Series,
                     symbol: str = "STOCK") -> Dict[str, Any]:
        """
        运行回测 (模板方法)
        
        执行流程：
        1. 数据对齐
        2. 逐K线执行
        3. 计算绩效指标
        4. 返回结果
        
        Args:
            data: OHLCV DataFrame (index=datetime)
            signal_series: 信号序列 (1=多, -1=空, 0=平仓)
            symbol: 股票代码
            
        Returns:
            回测结果字典
        """
        # 1. 重置状态
        self._reset_state()
        
        # 2. 对齐数据
        dates, prices, signals = self._align_data(data, signal_series)
        
        if len(dates) == 0:
            return self._empty_result()
        
        # 3. 逐K线执行
        self._execute_bars(dates, data, prices, signals, symbol)
        
        # 4. 计算指标
        metrics = self._calc_metrics(dates, prices)
        
        return metrics
    
    def _reset_state(self) -> None:
        """重置回测状态"""
        self.capital = self.initial_capital
        self.positions.clear()
        self.trades.clear()
        self.equity_snapshots.clear()
        self._bar_idx = 0
    
    def _align_data(self, data: pd.DataFrame, 
                    signal_series: pd.Series) -> Tuple[pd.DatetimeIndex, pd.Series, pd.Series]:
        """
        对齐数据和信号
        
        - 确保信号延迟1个bar执行 (避免未来函数)
        - 填充缺失值
        """
        # 使用数据的日期索引
        dates = data.index
        
        # 对齐价格 (使用 close 或设定价格)
        if 'close' in data.columns:
            prices = data['close'].reindex(dates)
        else:
            prices = pd.Series(0, index=dates)
        
        # 对齐信号并延迟1bar
        signals = signal_series.reindex(dates).fillna(0).clip(-1, 1)
        signals = signals.shift(1).fillna(0)  # 延迟1bar执行
        
        return dates, prices, signals
    
    def _execute_bars(self, dates: pd.DatetimeIndex, data: pd.DataFrame,
                      prices: pd.Series, signals: pd.Series, symbol: str) -> None:
        """
        逐K线执行回测
        """
        for i, ts in enumerate(dates):
            self._bar_idx = i
            self._current_date = ts
            
            # 获取当前K线
            if ts not in data.index:
                continue
            bar = data.loc[ts]
            
            # 市场规则钩子
            self.on_bar(symbol, bar, ts)
            
            # 获取当前信号
            signal = signals.iloc[i] if i < len(signals) else 0.0
            
            # 再平衡仓位
            self._rebalance(symbol, signal, bar, ts)
            
            # 记录权益快照
            self._record_snapshot(ts, prices.iloc[i] if i < len(prices) else 0)
        
        # 回测结束，强制平仓
        if len(dates) > 0:
            last_ts = dates[-1]
            last_price = prices.iloc[-1] if len(prices) > 0 else 0
            for sym in list(self.positions.keys()):
                self._close_position(sym, last_price, last_ts, "end_of_backtest")
    
    def _rebalance(self, symbol: str, target_signal: float, 
                   bar: pd.Series, timestamp: datetime) -> None:
        """
        调整仓位至目标信号
        
        Args:
            symbol: 股票代码
            target_signal: 目标信号 (-1~1)
            bar: 当前K线
            timestamp: 时间戳
        """
        # 确定目标方向
        if target_signal > 1e-9:
            target_dir = 1  # 做多
        elif target_signal < -1e-9:
            target_dir = -1  # 做空
        else:
            target_dir = 0  # 平仓
        
        current_pos = self.positions.get(symbol)
        
        # 无需操作
        if current_pos is None and target_dir == 0:
            return
        
        # 需要平仓的情况
        if current_pos is not None:
            need_close = (target_dir == 0 or 
                         target_dir != current_pos.direction)
            
            if need_close:
                if self.can_execute(symbol, 0, bar):
                    open_price = float(bar.get('open', bar.get('close', 0)))
                    if open_price > 0:
                        price = self.apply_slippage(open_price, -current_pos.direction)
                        self._close_position(symbol, price, timestamp, "signal")
                else:
                    return  # 被规则阻止
        
        # 开新仓
        if target_dir != 0 and symbol not in self.positions:
            if not self.can_execute(symbol, target_dir, bar):
                return  # 被规则阻止
            
            open_price = float(bar.get('open', bar.get('close', 0)))
            if open_price <= 0:
                return
            
            slipped_price = self.apply_slippage(open_price, target_dir)
            leverage = self.default_leverage
            
            # 计算目标金额 (全仓)
            target_notional = self.capital * leverage
            raw_size = self._calc_raw_size(symbol, target_notional, slipped_price)
            size = self.round_size(raw_size, slipped_price)
            
            if size <= 0:
                return
            
            margin = self._calc_margin(symbol, size, slipped_price, leverage)
            comm = self.calc_commission(size, slipped_price, target_dir, is_open=True)
            
            # 资金检查
            if margin + comm > self.capital:
                available = self.capital - comm
                if available <= 0:
                    return
                size = self.round_size(
                    self._calc_raw_size(symbol, available * leverage, slipped_price),
                    slipped_price
                )
                if size <= 0:
                    return
                margin = self._calc_margin(symbol, size, slipped_price, leverage)
                comm = self.calc_commission(size, slipped_price, target_dir, is_open=True)
            
            # 扣除资金
            self.capital -= (margin + comm)
            
            # 创建持仓
            self.positions[symbol] = Position(
                symbol=symbol,
                direction=target_dir,
                entry_price=slipped_price,
                entry_time=timestamp,
                size=size,
                leverage=leverage,
                entry_bar_idx=self._bar_idx,
                entry_commission=comm
            )
    
    def _close_position(self, symbol: str, exit_price: float, 
                        exit_time: datetime, reason: str) -> None:
        """
        平仓并记录交易
        """
        pos = self.positions.pop(symbol, None)
        if pos is None:
            return
        
        # 计算盈亏
        pnl = self._calc_pnl(symbol, pos.direction, pos.size, 
                            pos.entry_price, exit_price)
        margin = self._calc_margin(symbol, pos.size, pos.entry_price, pos.leverage)
        pnl_pct = pnl / margin * 100 if margin > 1e-9 else 0.0
        
        # 计算出场手续费
        exit_comm = self.calc_commission(pos.size, exit_price, pos.direction, is_open=False)
        
        # 返还资金
        self.capital += margin + pnl - exit_comm
        
        # 持仓K线数
        holding_bars = max(self._bar_idx - pos.entry_bar_idx, 0)
        
        # 记录交易
        self.trades.append(TradeRecord(
            symbol=symbol,
            direction=pos.direction,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            entry_time=pos.entry_time,
            exit_time=exit_time,
            size=pos.size,
            leverage=pos.leverage,
            pnl=pnl,
            pnl_pct=pnl_pct,
            exit_reason=reason,
            holding_bars=holding_bars,
            commission=pos.entry_commission + exit_comm
        ))
    
    def _record_snapshot(self, timestamp: datetime, current_price: float) -> None:
        """记录权益快照"""
        total_unrealized = 0.0
        for pos in self.positions.values():
            unrealized = self._calc_pnl(pos.symbol, pos.direction, pos.size,
                                       pos.entry_price, current_price)
            total_unrealized += unrealized
        
        # 估算总权益
        equity = self.capital
        for pos in self.positions.values():
            margin = self._calc_margin(pos.symbol, pos.size, pos.entry_price, pos.leverage)
            unrealized = self._calc_pnl(pos.symbol, pos.direction, pos.size,
                                       pos.entry_price, current_price)
            equity += margin + unrealized
        
        self.equity_snapshots.append(EquitySnapshot(
            timestamp=timestamp,
            capital=self.capital,
            unrealized=total_unrealized,
            equity=equity,
            positions=len(self.positions)
        ))
    
    def _calc_metrics(self, dates: pd.DatetimeIndex, 
                      prices: pd.Series) -> Dict[str, Any]:
        """
        计算回测绩效指标
        """
        final_equity = self.capital
        if self.positions:
            last_price = prices.iloc[-1] if len(prices) > 0 else 0
            for pos in self.positions.values():
                margin = self._calc_margin(pos.symbol, pos.size, pos.entry_price, pos.leverage)
                unrealized = self._calc_pnl(pos.symbol, pos.direction, pos.size,
                                           pos.entry_price, last_price)
                final_equity += margin + unrealized
        
        # 基础指标
        total_return = (final_equity - self.initial_capital) / self.initial_capital
        
        # 从权益曲线计算
        equity_series = pd.Series([s.equity for s in self.equity_snapshots], 
                                  index=[s.timestamp for s in self.equity_snapshots])
        
        # 最大回撤
        max_drawdown = 0.0
        if len(equity_series) > 0:
            peak = equity_series.expanding().max()
            drawdown = (equity_series - peak) / peak
            max_drawdown = drawdown.min()
        
        # 交易统计
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl < 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0
        
        # 盈亏比
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = abs(np.mean([t.pnl for t in losing_trades])) if losing_trades else 1e-10
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 1e-10 else 0.0
        
        # 总手续费
        total_commission = sum(t.commission for t in self.trades)
        
        return {
            "initial_value": self.initial_capital,
            "final_value": final_equity,
            "return_pct": round(total_return * 100, 4),
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": round(win_rate * 100, 2),
            "profit_loss_ratio": round(profit_loss_ratio, 4),
            "max_drawdown": round(max_drawdown * 100, 4),
            "total_commission": round(total_commission, 2),
            "trades": self.trades,
            "equity_curve": equity_series.to_dict() if len(equity_series) > 0 else {}
        }
    
    def _empty_result(self) -> Dict[str, Any]:
        """返回空结果"""
        return {
            "initial_value": self.initial_capital,
            "final_value": self.initial_capital,
            "return_pct": 0.0,
            "total_trades": 0,
            "win_rate": 0.0,
            "max_drawdown": 0.0
        }
