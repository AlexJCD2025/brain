#!/usr/bin/env python3
"""
测试新版回测引擎
演示 AShareEngine 的完整功能
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.backtest import BacktestEngine, AShareEngine
from brain.backtest.reporter import BacktestReporter


def generate_mock_data(days=252, start_price=100, trend=0.0003, volatility=0.02):
    """生成模拟股票数据"""
    np.random.seed(42)
    
    dates = pd.date_range(start='2023-01-01', periods=days, freq='B')  # 工作日
    
    # 随机游走生成价格
    returns = np.random.normal(trend, volatility, days)
    prices = start_price * (1 + returns).cumprod()
    
    # 生成 OHLCV
    data = []
    for i, (date, close) in enumerate(zip(dates, prices)):
        daily_range = close * volatility * 0.5
        open_price = close + np.random.normal(0, daily_range * 0.3)
        high_price = max(open_price, close) + abs(np.random.normal(0, daily_range * 0.3))
        low_price = min(open_price, close) - abs(np.random.normal(0, daily_range * 0.3))
        volume = int(np.random.normal(1000000, 300000))
        
        data.append({
            'datetime': date,
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close, 2),
            'volume': max(volume, 100000),
            'pre_close': round(prices[i-1], 2) if i > 0 else round(close * 0.99, 2)
        })
    
    df = pd.DataFrame(data)
    df.set_index('datetime', inplace=True)
    return df


def generate_dual_ma_signals(data, fast=10, slow=30):
    """
    生成双均线交易信号
    
    Returns:
        pd.Series: 1=买入, -1=卖出, 0=平仓/持有
    """
    close = data['close']
    fast_ma = close.rolling(fast).mean()
    slow_ma = close.rolling(slow).mean()
    
    signals = pd.Series(0, index=data.index)
    
    # 金叉买入，死叉卖出
    for i in range(1, len(data)):
        if fast_ma.iloc[i] > slow_ma.iloc[i] and fast_ma.iloc[i-1] <= slow_ma.iloc[i-1]:
            signals.iloc[i] = 1  # 金叉买入
        elif fast_ma.iloc[i] < slow_ma.iloc[i] and fast_ma.iloc[i-1] >= slow_ma.iloc[i-1]:
            signals.iloc[i] = -1  # 死叉卖出
    
    return signals


def main():
    print("=" * 70)
    print("🧠 Brain 量化框架 - 新版回测引擎测试")
    print("=" * 70)
    
    # 1. 生成模拟数据
    print("\n📊 生成模拟数据...")
    data = generate_mock_data(days=252, start_price=100)
    print(f"   数据条数: {len(data)}")
    print(f"   日期范围: {data.index[0].date()} ~ {data.index[-1].date()}")
    print(f"   价格范围: {data['close'].min():.2f} ~ {data['close'].max():.2f}")
    
    # 2. 生成信号
    print("\n📈 生成双均线信号 (10日/30日)...")
    signals = generate_dual_ma_signals(data, fast=10, slow=30)
    buy_signals = (signals == 1).sum()
    sell_signals = (signals == -1).sum()
    print(f"   买入信号: {buy_signals} 次")
    print(f"   卖出信号: {sell_signals} 次")
    
    # 3. 使用新版引擎运行回测
    print("\n🚀 运行回测 (A股规则)...")
    print("-" * 70)
    
    engine = BacktestEngine(
        initial_cash=100000,
        commission_rate=0.00025,
        engine_type="ashare"
    )
    
    result = engine.run(data, signals, symbol="000001")
    
    print("-" * 70)
    
    # 4. 显示结果
    print("\n📋 回测结果:")
    print(f"   初始资金: ¥{result['initial_value']:,.2f}")
    print(f"   最终资金: ¥{result['final_value']:,.2f}")
    print(f"   收益率:   {result['return_pct']:+.2f}%")
    print(f"   最大回撤: {result['max_drawdown']:.2f}%")
    print(f"   总交易:   {result['total_trades']} 笔")
    print(f"   胜率:     {result['win_rate']:.1f}%")
    print(f"   盈亏比:   {result['profit_loss_ratio']:.2f}")
    print(f"   总手续费: ¥{result['total_commission']:.2f}")
    
    # 5. 显示交易明细
    print("\n📝 交易明细:")
    trades = result.get('trades', [])
    if trades:
        print(f"{'时间':<20} {'方向':<6} {'入场价':<10} {'出场价':<10} {'盈亏':<12} {'持仓天数'}")
        print("-" * 70)
        for t in trades[:10]:  # 只显示前10笔
            direction = "买入" if t.direction == 1 else "卖出"
            pnl_str = f"{t.pnl:+.2f}"
            print(f"{str(t.entry_time)[:19]:<20} {direction:<6} "
                  f"{t.entry_price:<10.2f} {t.exit_price:<10.2f} "
                  f"{pnl_str:<12} {t.holding_bars}")
        if len(trades) > 10:
            print(f"... 还有 {len(trades) - 10} 笔交易")
    
    # 6. 生成报告
    print("\n📄 生成报告...")
    reporter = BacktestReporter()
    report_text = f"""
╔════════════════════════════════════════════════════════════════╗
║                     回测报告                                    ║
╠════════════════════════════════════════════════════════════════╣
  初始资金: ¥{result['initial_value']:,.2f}
  最终资金: ¥{result['final_value']:,.2f}
  收益率:   {result['return_pct']:+.2f}%
  最大回撤: {result['max_drawdown']:.2f}%
  总交易:   {result['total_trades']} 笔
  胜率:     {result['win_rate']:.1f}%
  盈亏比:   {result['profit_loss_ratio']:.2f}
  总手续费: ¥{result['total_commission']:.2f}
╚════════════════════════════════════════════════════════════════╝
"""
    print(report_text)
    
    # 7. 测试A股规则
    print("\n🔍 验证A股规则:")
    
    # 检查手数规则
    ashare = AShareEngine()
    test_sizes = [150, 250, 99, 1000]
    print("   手数规则测试 (100股整数倍):")
    for size in test_sizes:
        rounded = ashare.round_size(size, price=100)
        print(f"     {size}股 → {rounded}股")
    
    # 检查手续费计算
    print("\n   手续费测试 (买入10万元):")
    commission_buy = ashare.calc_commission(1000, 100, direction=1, is_open=True)
    commission_sell = ashare.calc_commission(1000, 100, direction=1, is_open=False)
    print(f"     买入: ¥{commission_buy:.2f}")
    print(f"     卖出: ¥{commission_sell:.2f} (含印花税)")
    
    print("\n" + "=" * 70)
    print("✅ 测试完成！")
    print("=" * 70)


if __name__ == "__main__":
    main()
