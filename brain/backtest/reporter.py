"""
回测报告生成器模块
提供文本报告生成和保存功能
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class BacktestReporter:
    """
    回测报告生成器类
    用于生成和保存回测结果报告
    """

    def __init__(self, output_dir: str = "reports"):
        """
        初始化报告生成器

        Args:
            output_dir: 报告输出目录，默认为 "reports"
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_text_report(self, result: Dict[str, Any]) -> str:
        """
        生成文本格式的回测报告

        Args:
            result: 回测结果字典

        Returns:
            str: 格式化的文本报告
        """
        lines = []

        # 报告标题
        lines.append("=" * 60)
        lines.append("                 回测报告")
        lines.append("=" * 60)
        lines.append("")

        # 基本信息
        lines.append("【基本信息】")
        lines.append(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 资金信息
        lines.append("【资金统计】")
        lines.append(
            f"  初始资金: {result.get('initial_value', 0):,.2f}"
        )
        lines.append(
            f"  最终资金: {result.get('final_value', 0):,.2f}"
        )
        lines.append(
            f"  绝对收益: {result.get('final_value', 0) - result.get('initial_value', 0):,.2f}"
        )
        lines.append(
            f"  收益率:   {result.get('return_pct', 0):.2f}%"
        )
        lines.append("")

        # 风险指标
        lines.append("【风险指标】")
        lines.append(
            f"  夏普比率:     {result.get('sharpe_ratio', 0):.4f}"
        )
        lines.append(
            f"  最大回撤:     {result.get('max_drawdown', 0):.2f}%"
        )
        lines.append("")

        # 交易统计
        lines.append("【交易统计】")
        lines.append(
            f"  总交易数:     {result.get('total_trades', 0)}"
        )

        # 策略交易详情
        strategy_trades = result.get("strategy_trades", {})
        if strategy_trades:
            lines.append(
                f"  买入次数:     {strategy_trades.get('buy_count', 0)}"
            )
            lines.append(
                f"  卖出次数:     {strategy_trades.get('sell_count', 0)}"
            )
            lines.append(
                f"  总手续费:     {strategy_trades.get('total_commission', 0):,.2f}"
            )
            lines.append(
                f"  总交易额:     {strategy_trades.get('total_value', 0):,.2f}"
            )
        lines.append("")

        # 交易详情
        trades = strategy_trades.get("trades", [])
        if trades:
            lines.append("【交易明细】")
            lines.append(
                f"{'时间':<20} {'类型':<8} {'价格':<12} {'数量':<10} {'手续费':<12}"
            )
            lines.append("-" * 60)
            for trade in trades[-10:]:  # 只显示最近10笔交易
                dt = trade.get("datetime", "")
                if isinstance(dt, datetime):
                    dt_str = dt.strftime("%Y-%m-%d %H:%M")
                else:
                    dt_str = str(dt)[:16]
                trade_type = trade.get("type", "")
                price = trade.get("price", 0)
                size = trade.get("size", 0)
                comm = trade.get("commission", 0)
                lines.append(
                    f"{dt_str:<20} {trade_type:<8} {price:<12.2f} {size:<10} {comm:<12.2f}"
                )
            if len(trades) > 10:
                lines.append(f"  ... 还有 {len(trades) - 10} 笔交易未显示")
            lines.append("")

        # 结尾
        lines.append("=" * 60)
        lines.append("                      报告结束")
        lines.append("=" * 60)

        return "\n".join(lines)

    def save_report(
        self,
        result: Dict[str, Any],
        name: Optional[str] = None,
    ) -> str:
        """
        保存报告到文件

        Args:
            result: 回测结果字典
            name: 报告文件名（不含扩展名），默认为当前时间戳

        Returns:
            str: 保存的文件路径
        """
        if name is None:
            name = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存文本报告
        text_report = self.generate_text_report(result)
        text_path = self.output_dir / f"{name}.txt"
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text_report)

        # 保存 JSON 格式的详细数据
        json_path = self.output_dir / f"{name}.json"

        # 处理不可序列化的对象
        def serialize_value(v: Any) -> Any:
            if isinstance(v, datetime):
                return v.isoformat()
            elif isinstance(v, (list, tuple)):
                return [serialize_value(item) for item in v]
            elif isinstance(v, dict):
                return {k: serialize_value(val) for k, val in v.items()}
            else:
                return v

        serializable_result = serialize_value(result)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(serializable_result, f, indent=2, ensure_ascii=False)

        return str(text_path)

    def generate_summary(self, result: Dict[str, Any]) -> str:
        """
        生成简短的回测摘要（单行格式）

        Args:
            result: 回测结果字典

        Returns:
            str: 回测摘要字符串
        """
        return (
            f"收益: {result.get('return_pct', 0):.2f}% | "
            f"夏普: {result.get('sharpe_ratio', 0):.4f} | "
            f"回撤: {result.get('max_drawdown', 0):.2f}% | "
            f"交易: {result.get('total_trades', 0)}笔"
        )
