#!/usr/bin/env python3
"""
Brain 量化框架演示 - 使用模拟数据
无需网络连接即可运行
"""
import sys
from pathlib import Path
import random
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import polars as pl
import numpy as np

from brain.backtest.engine import BacktestEngine
from brain.backtest.reporter import BacktestReporter
from brain.strategies.dual_ma import DualMAStrategy


def generate_mock_data(days=252, start_price=100, trend=0.0002, volatility=0.02):
    """
    生成模拟股票数据
    
    Args:
        days: 交易日数量
        start_price: 起始价格
        trend: 每日趋势（正数上涨，负数下跌）
        volatility: 波动率
    
    Returns:
        Polars DataFrame with OHLCV data
    """
    random.seed(42)
    np.random.seed(42)
    
    # 生成日期序列（排除周末）
    dates = []
    current = datetime(2023, 1, 1)
    while len(dates) < days:
        if current.weekday() < 5:  # 周一到周五
            dates.append(current)
        current += timedelta(days=1)
    
    # 生成价格序列（随机游走）
    prices = [start_price]
    for _ in range(days - 1):
        change = np.random.normal(trend, volatility)
        new_price = prices[-1] * (1 + change)
        prices.append(max(new_price, 0.01))  # 确保价格为正
    
    # 生成 OHLCV 数据
    data = []
    for i, (date, close) in enumerate(zip(dates, prices)):
        # 基于收盘价生成开高低
        daily_vol = close * volatility * 0.5
        open_price = close + np.random.normal(0, daily_vol)
        high_price = max(open_price, close) + abs(np.random.normal(0, daily_vol * 0.5))
        low_price = min(open_price, close) - abs(np.random.normal(0, daily_vol * 0.5))
        volume = int(np.random.normal(1000000, 200000))
        
        data.append({
            "datetime": date,  # 使用 datetime 作为列名，符合 backtrader 要求
            "open": round(open_price, 2),
            "high": round(high_price, 2),
            "low": round(low_price, 2),
            "close": round(close, 2),
            "volume": max(volume, 100000)
        })
    
    return pl.DataFrame(data)


def main():
    """主函数"""
    print("=" * 60)
    print("🧠 Brain 量化框架 - 双均线策略回测 (演示模式)")
    print("=" * 60)
    
    # 1. 生成模拟数据
    print("\n📊 生成模拟股票数据...")
    df = generate_mock_data(days=252, start_price=100, trend=0.0003, volatility=0.02)
    print(f"   生成 {len(df)} 条数据")
    print(f"   日期范围: {df['datetime'][0]} ~ {df['datetime'][-1]}")
    print(f"   价格范围: {df['close'].min():.2f} ~ {df['close'].max():.2f}")
    
    # 显示前5行
    print("\n   数据预览:")
    print(df.head().to_pandas().to_string(index=False))
    
    # 2. 设置回测引擎
    print("\n⚙️  设置回测引擎...")
    engine = BacktestEngine(initial_cash=100000)
    engine.add_data(df, name="mock_stock")
    print("   初始资金: ¥100,000")
    print("   手续费: 0.03%")
    
    # 3. 添加策略
    print("\n📈 添加双均线策略...")
    print("   短期均线: 10日")
    print("   长期均线: 30日")
    engine.add_strategy(DualMAStrategy, fast_period=10, slow_period=30, verbose=True)
    
    # 4. 运行回测
    print("\n🚀 运行回测...")
    print("-" * 60)
    result = engine.run()
    print("-" * 60)
    
    # 5. 生成报告
    print("\n📋 生成报告...")
    reporter = BacktestReporter()
    report = reporter.generate_text_report(result)
    print(report)
    
    # 6. 保存报告
    report_file = reporter.save_report(result, name="demo_backtest")
    print(f"\n💾 报告已保存: {report_file}")
    
    # 7. 简单分析
    print("\n📊 策略分析:")
    if result['return_pct'] > 0:
        print(f"   ✅ 策略盈利: +{result['return_pct']:.2f}%")
    else:
        print(f"   ❌ 策略亏损: {result['return_pct']:.2f}%")
    
    print(f"   📉 最大回撤: {result['max_drawdown']:.2f}%")
    print(f"   📊 夏普比率: {result['sharpe_ratio']:.2f}")
    print(f"   🔄 总交易数: {result['total_trades']}")
    
    print("\n" + "=" * 60)
    print("✅ 回测完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
