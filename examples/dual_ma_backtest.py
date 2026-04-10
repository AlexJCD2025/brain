#!/usr/bin/env python3
"""
Brain 量化框架 - 双均线策略回测示例

这是一个完整的回测示例脚本，展示如何使用 Brain 框架进行量化回测。

功能:
1. 从 AKShare 获取股票数据
2. 使用双均线策略（金叉买入/死叉卖出）
3. 运行回测并生成报告

使用方法:
    cd /home/alex_jiang/brain
    python examples/dual_ma_backtest.py

注意:
    - 需要安装 AKShare: pip install akshare
    - 首次运行会从网络获取数据，可能需要一些时间
    - 数据会自动缓存到 data/cache 目录
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入 Brain 框架模块
from brain.data import DataFetcher
from brain.backtest import BacktestEngine, BacktestReporter
from brain.strategies import DualMAStrategy


def main():
    """
    主函数: 执行双均线策略回测
    """
    print("=" * 60)
    print("🧠 Brain 量化框架 - 双均线策略回测")
    print("=" * 60)
    print()

    # 配置参数
    symbol = "000001"           # 平安银行
    start_date = "20230101"     # 开始日期: 2023年1月1日
    end_date = "20231231"       # 结束日期: 2023年12月31日
    initial_cash = 100000.0     # 初始资金: 10万元
    fast_period = 10            # 快线周期: 10日均线
    slow_period = 30            # 慢线周期: 30日均线

    # 第1步: 获取数据
    print("📊 第1步: 获取股票数据")
    print(f"   股票代码: {symbol} (平安银行)")
    print(f"   时间范围: {start_date} - {end_date}")
    print()

    try:
        fetcher = DataFetcher()
        df = fetcher.fetch_stock_daily(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            use_cache=True,
        )
        print(f"   ✅ 成功获取 {len(df)} 条数据记录")
        print(f"   📈 数据列: {list(df.columns)}")
        print()
    except Exception as e:
        print(f"   ❌ 获取数据失败: {e}")
        print()
        print("提示: 如果 AKShare 网络访问有问题，可以:")
        print("  1. 检查网络连接")
        print("  2. 使用本地缓存数据（如果之前有运行过）")
        print("  3. 暂时注释掉数据获取部分进行测试")
        return

    # 第2步: 设置回测引擎
    print("⚙️  第2步: 设置回测引擎")
    print(f"   初始资金: {initial_cash:,.2f} 元")
    print()

    engine = BacktestEngine(
        initial_cash=initial_cash,
        commission=0.001,  # 手续费率 0.1%
    )

    # 添加数据到引擎
    engine.add_data(df, name=symbol, datetime_col="date")
    print(f"   ✅ 数据已添加到回测引擎")
    print()

    # 第3步: 添加策略
    print("📈 第3步: 添加双均线策略")
    print(f"   快线周期: {fast_period} 日")
    print(f"   慢线周期: {slow_period} 日")
    print(f"   交易规则: 金叉买入, 死叉卖出")
    print()

    engine.add_strategy(
        DualMAStrategy,
        fast_period=fast_period,
        slow_period=slow_period,
    )
    print(f"   ✅ 策略已添加")
    print()

    # 第4步: 运行回测
    print("🚀 第4步: 运行回测")
    print("   正在执行回测...")
    print()

    try:
        result = engine.run()
        print(f"   ✅ 回测完成")
        print()
    except Exception as e:
        print(f"   ❌ 回测失败: {e}")
        return

    # 第5步: 生成报告
    print("📋 第5步: 生成回测报告")
    print()

    reporter = BacktestReporter(output_dir="reports")

    # 生成文本报告
    text_report = reporter.generate_text_report(result)
    print(text_report)
    print()

    # 生成摘要
    summary = reporter.generate_summary(result)
    print("📊 回测摘要:")
    print(f"   {summary}")
    print()

    # 第6步: 保存报告到文件
    print("💾 第6步: 保存报告到文件")

    report_path = reporter.save_report(result, name="dual_ma_backtest")
    print(f"   ✅ 报告已保存: {report_path}")
    print(f"   📁 报告目录: {reporter.output_dir.absolute()}")
    print()

    print("=" * 60)
    print("✨ 回测完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
