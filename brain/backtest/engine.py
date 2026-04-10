"""
回测引擎模块
提供基于新架构的回测功能

新架构特点:
1. 抽象基类 BaseEngine 定义回测框架
2. AShareEngine 实现A股规则
3. 支持自定义市场引擎
"""
from typing import Dict, Any, Optional
from pathlib import Path

import pandas as pd
import backtrader as bt

from brain.backtest.base_engine import BaseEngine
from brain.backtest.engines import AShareEngine
from brain.backtest.models import TradeRecord, Position, EquitySnapshot
from brain.backtest.reporter import BacktestReporter

# 尝试导入配置，如果不存在则使用默认值
try:
    from brain.config import config
except ImportError:
    class _DefaultConfig:
        def get(self, key, default=None):
            defaults = {
                "backtest.initial_cash": 100000.0,
                "backtest.commission": 0.0003
            }
            return defaults.get(key, default)
    config = _DefaultConfig()


class BacktestEngine:
    """
    回测引擎 (新版)
    
    提供统一的回测接口，内部使用新的架构
    
    支持两种模式:
    1. 简单模式: 使用内置 AShareEngine，适合A股回测
    2. Backtrader模式: 使用 Backtrader 引擎 (保留兼容)
    
    Example:
        # 新版简单模式
        engine = BacktestEngine(initial_cash=100000)
        
        # 生成信号
        signals = generate_signals(data)  # 1=买入, -1=卖出, 0=平仓
        
        # 运行回测
        result = engine.run(data, signals, symbol="000001")
        
        # 打印结果
        print(f"收益率: {result['return_pct']}%")
    """
    
    def __init__(
        self,
        initial_cash: Optional[float] = None,
        commission_rate: Optional[float] = None,
        engine_type: str = "ashare"  # "ashare" 或 "backtrader"
    ):
        """
        初始化回测引擎
        
        Args:
            initial_cash: 初始资金，默认从配置读取
            commission_rate: 手续费率，默认从配置读取
            engine_type: 引擎类型 ("ashare" 或 "backtrader")
        """
        self.engine_type = engine_type
        
        # 配置参数
        self.initial_cash = initial_cash or config.get("backtest.initial_cash", 100000.0)
        self.commission_rate = commission_rate or config.get("backtest.commission", 0.0003)
        
        # 内部引擎
        self._engine: Optional[BaseEngine] = None
        self._cerebro: Optional[bt.Cerebro] = None
        
        # 初始化对应引擎
        if engine_type == "ashare":
            self._init_ashare_engine()
        else:
            self._init_backtrader_engine()
    
    def _init_ashare_engine(self) -> None:
        """初始化A股引擎"""
        engine_config = {
            "initial_cash": self.initial_cash,
            "commission_rate": self.commission_rate,
            "commission_min": 5.0,
            "stamp_tax": 0.0005,
            "transfer_fee": 0.00001,
            "slippage": 0.001
        }
        self._engine = AShareEngine(engine_config)
    
    def _init_backtrader_engine(self) -> None:
        """初始化Backtrader引擎 (兼容旧版)"""
        self._cerebro = bt.Cerebro()
        self._cerebro.broker.setcash(self.initial_cash)
        self._cerebro.broker.setcommission(commission=self.commission_rate)
        
        # 添加分析器
        self._cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
        self._cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
        self._cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
        self._cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    
    def run(
        self,
        data: pd.DataFrame,
        signals: Optional[pd.Series] = None,
        symbol: str = "STOCK",
        strategy_class=None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        运行回测
        
        根据 engine_type 自动选择回测方式
        
        Args:
            data: OHLCV DataFrame (index=datetime)
            signals: 交易信号序列 (1=多, -1=空, 0=平仓)
            symbol: 股票代码
            strategy_class: Backtrader策略类 (仅backtrader模式)
            **kwargs: 额外参数
            
        Returns:
            回测结果字典
        """
        if self.engine_type == "ashare" and signals is not None:
            return self._run_ashare(data, signals, symbol)
        else:
            return self._run_backtrader(data, strategy_class, **kwargs)
    
    def _run_ashare(self, data: pd.DataFrame, 
                    signals: pd.Series, symbol: str) -> Dict[str, Any]:
        """使用A股引擎运行回测"""
        if self._engine is None:
            raise RuntimeError("A股引擎未初始化")
        
        result = self._engine.run_backtest(data, signals, symbol)
        
        # 格式化结果
        return {
            "initial_value": result["initial_value"],
            "final_value": result["final_value"],
            "return_pct": result["return_pct"],
            "sharpe_ratio": 0.0,  # TODO: 计算夏普比率
            "max_drawdown": result["max_drawdown"],
            "total_trades": result["total_trades"],
            "win_rate": result["win_rate"],
            "profit_loss_ratio": result["profit_loss_ratio"],
            "total_commission": result["total_commission"],
            "trades": result["trades"],
            "equity_curve": result["equity_curve"]
        }
    
    def _run_backtrader(self, data: pd.DataFrame,
                        strategy_class=None, **kwargs) -> Dict[str, Any]:
        """使用Backtrader运行回测 (兼容旧版)"""
        if self._cerebro is None:
            raise RuntimeError("Backtrader引擎未初始化")
        
        # 添加数据
        data_feed = bt.feeds.PandasData(
            dataname=data,
            datetime=None,  # 使用索引
            open="open",
            high="high",
            low="low",
            close="close",
            volume="volume",
            openinterest=-1
        )
        self._cerebro.adddata(data_feed)
        
        # 添加策略
        if strategy_class:
            self._cerebro.addstrategy(strategy_class, **kwargs)
        
        # 运行
        results = self._cerebro.run()
        strat = results[0]
        
        # 提取结果
        final_value = self._cerebro.broker.getvalue()
        initial_value = self.initial_cash
        
        return {
            "initial_value": initial_value,
            "final_value": final_value,
            "return_pct": (final_value - initial_value) / initial_value * 100,
            "sharpe_ratio": strat.analyzers.sharpe.get_analysis().get("sharperatio", 0) or 0,
            "max_drawdown": strat.analyzers.drawdown.get_analysis().get("max", {}).get("drawdown", 0),
            "total_trades": strat.analyzers.trades.get_analysis().get("total", {}).get("total", 0),
        }
    
    def add_data(self, df: pd.DataFrame, name: str = "data") -> None:
        """
        添加数据 (兼容旧版接口)
        
        Args:
            df: DataFrame数据
            name: 数据名称
        """
        if self._cerebro is not None:
            import polars as pl
            
            # 支持 Polars 转 Pandas
            if isinstance(df, pl.DataFrame):
                df = df.to_pandas()
            
            data_feed = bt.feeds.PandasData(
                dataname=df,
                datetime="datetime" if "datetime" in df.columns else None,
                open="open",
                high="high",
                low="low",
                close="close",
                volume="volume",
                openinterest=-1
            )
            self._cerebro.adddata(data_feed, name=name)
    
    def add_strategy(self, strategy_class, **kwargs) -> None:
        """
        添加策略 (兼容旧版接口)
        
        Args:
            strategy_class: 策略类
            **kwargs: 策略参数
        """
        if self._cerebro is not None:
            self._cerebro.addstrategy(strategy_class, **kwargs)
    
    def get_trades(self) -> list:
        """获取交易记录"""
        if self._engine is not None:
            return self._engine.trades
        return []
    
    def get_equity_curve(self) -> pd.Series:
        """获取权益曲线"""
        if self._engine is not None and self._engine.equity_snapshots:
            timestamps = [s.timestamp for s in self._engine.equity_snapshots]
            equities = [s.equity for s in self._engine.equity_snapshots]
            return pd.Series(equities, index=timestamps)
        return pd.Series()
    
    def plot(self, **kwargs) -> None:
        """绘制回测结果 (仅backtrader模式)"""
        if self._cerebro is not None:
            self._cerebro.plot(style="candlestick", barup="red", bardown="green", **kwargs)


# 导出
__all__ = [
    "BacktestEngine",
    "BaseEngine",
    "AShareEngine",
    "TradeRecord",
    "Position",
    "EquitySnapshot"
]
