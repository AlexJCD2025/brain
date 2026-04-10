"""
回测引擎模块
基于 backtrader 实现回测功能
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

import backtrader as bt
import polars as pl


class PandasDataFeed(bt.feeds.PandasData):
    """
    自定义 Pandas DataFeed，支持从 Polars DataFrame 转换
    """
    pass


class BacktestEngine:
    """
    回测引擎类
    封装 backtrader.Cerebro 提供简洁的回测接口
    """

    def __init__(
        self,
        initial_cash: Optional[float] = None,
        commission: Optional[float] = None,
    ):
        """
        初始化回测引擎

        Args:
            initial_cash: 初始资金，默认从环境变量或设为 100000
            commission: 手续费率，默认从环境变量或设为 0.001
        """
        self.cerebro = bt.Cerebro()
        self.initial_cash = initial_cash or float(
            os.getenv("INITIAL_CASH", "100000")
        )
        self.commission = commission or float(
            os.getenv("COMMISSION_RATE", "0.001")
        )

        # 设置初始资金
        self.cerebro.broker.setcash(self.initial_cash)

        # 设置手续费
        self.cerebro.broker.setcommission(commission=self.commission)

        # 添加分析器
        self._add_analyzers()

        # 存储结果
        self.results: Optional[List[Any]] = None
        self.strategy: Optional[Any] = None

    def _add_analyzers(self) -> None:
        """添加回测分析器"""
        # 夏普比率
        self.cerebro.addanalyzer(
            bt.analyzers.SharpeRatio,
            _name="sharpe",
            riskfreerate=0.02,
            annualize=True,
        )

        # 回撤分析
        self.cerebro.addanalyzer(
            bt.analyzers.DrawDown,
            _name="drawdown",
        )

        # 收益分析
        self.cerebro.addanalyzer(
            bt.analyzers.Returns,
            _name="returns",
        )

        # 交易分析
        self.cerebro.addanalyzer(
            bt.analyzers.TradeAnalyzer,
            _name="trades",
        )

    def add_data(
        self,
        df: pl.DataFrame,
        name: str = "data",
        datetime_col: str = "datetime",
    ) -> None:
        """
        添加 Polars DataFrame 数据到回测引擎

        Args:
            df: Polars DataFrame，需要包含 datetime, open, high, low, close, volume 列
            name: 数据名称
            datetime_col: 时间列名称
        """
        # 转换为 Pandas DataFrame（backtrader 原生支持）
        pandas_df = df.to_pandas()

        # 确保 datetime 列是索引
        if datetime_col in pandas_df.columns:
            pandas_df[datetime_col] = pandas_df[datetime_col].astype("datetime64[ns]")
            pandas_df.set_index(datetime_col, inplace=True)

        # 确保列名符合 backtrader 要求
        column_mapping = {}
        for col in pandas_df.columns:
            col_lower = col.lower()
            if col_lower in ["open", "high", "low", "close", "volume"]:
                column_mapping[col] = col_lower

        if column_mapping:
            pandas_df.rename(columns=column_mapping, inplace=True)

        # 创建数据 feed
        data_feed = PandasDataFeed(
            dataname=pandas_df,
            name=name,
        )

        self.cerebro.adddata(data_feed, name=name)

    def add_strategy(
        self,
        strategy_class: Type[bt.Strategy],
        **kwargs: Any,
    ) -> None:
        """
        添加策略到回测引擎

        Args:
            strategy_class: 策略类（继承自 bt.Strategy）
            **kwargs: 策略参数
        """
        self.cerebro.addstrategy(strategy_class, **kwargs)

    def run(self) -> Dict[str, Any]:
        """
        运行回测

        Returns:
            dict: 包含回测结果的字典
        """
        # 运行回测
        self.results = self.cerebro.run()

        if not self.results:
            raise RuntimeError("回测未产生结果")

        self.strategy = self.results[0]

        # 提取分析结果
        result = self._extract_results()

        return result

    def _extract_results(self) -> Dict[str, Any]:
        """
        从回测结果中提取关键指标

        Returns:
            dict: 回测结果字典
        """
        if self.strategy is None:
            raise RuntimeError("请先运行回测")

        # 获取分析器结果
        sharpe_analysis = self.strategy.analyzers.sharpe.get_analysis()
        drawdown_analysis = self.strategy.analyzers.drawdown.get_analysis()
        returns_analysis = self.strategy.analyzers.returns.get_analysis()
        trades_analysis = self.strategy.analyzers.trades.get_analysis()

        # 计算关键指标
        final_value = self.cerebro.broker.getvalue()
        initial_value = self.initial_cash
        return_pct = (final_value - initial_value) / initial_value * 100

        # 夏普比率
        sharpe_ratio = sharpe_analysis.get("sharperatio", 0)
        if sharpe_ratio is None:
            sharpe_ratio = 0

        # 最大回撤
        max_drawdown = drawdown_analysis.get("max", {}).get("drawdown", 0)

        # 总交易数
        total_trades = trades_analysis.get("total", {}).get("total", 0)
        if isinstance(total_trades, dict):
            total_trades = total_trades.get("total", 0)

        # 详细结果字典
        result = {
            "initial_value": initial_value,
            "final_value": final_value,
            "return_pct": round(return_pct, 4),
            "sharpe_ratio": round(sharpe_ratio, 4) if sharpe_ratio else 0,
            "max_drawdown": round(max_drawdown, 4),
            "total_trades": int(total_trades) if total_trades else 0,
            "drawdown_analysis": dict(drawdown_analysis),
            "returns_analysis": dict(returns_analysis),
            "trades_analysis": dict(trades_analysis),
            "strategy_trades": self.strategy.get_analytics()
            if hasattr(self.strategy, "get_analytics")
            else {},
        }

        return result

    def plot(self, **kwargs: Any) -> None:
        """
        绘制回测结果

        Args:
            **kwargs: 传递给 cerebro.plot 的参数
        """
        default_kwargs = {
            "style": "candlestick",
            "barup": "red",
            "bardown": "green",
            "volup": "red",
            "voldown": "green",
        }
        default_kwargs.update(kwargs)

        self.cerebro.plot(**default_kwargs)

    def get_cerebro(self) -> bt.Cerebro:
        """
        获取底层 Cerebro 实例（用于高级配置）

        Returns:
            bt.Cerebro: backtrader Cerebro 实例
        """
        return self.cerebro
