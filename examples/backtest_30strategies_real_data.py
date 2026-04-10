#!/usr/bin/env python3
"""
30策略真实A股数据回测

使用真实A股数据对30个策略进行全面回测
"""
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.strategies.lib import generate_strategy
from brain.backtest import BacktestEngine
from brain.data.ashare_data import AshareDataProvider, get_stock_data


@dataclass
class BacktestResult:
    """回测结果"""
    strategy_name: str
    symbol: str
    return_pct: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    profit_factor: float
    sharpe_ratio: float
    start_date: str
    end_date: str
    trading_days: int


# 30策略最佳参数
BEST_PARAMS_30 = {
    'dual_ma': {'fast': 5, 'slow': 20, 'ma_type': 'sma'},
    'macd': {'fast': 8, 'slow': 21, 'signal': 5},
    'rsi': {'period': 14, 'overbought': 80, 'oversold': 20},
    'bollinger': {'period': 15, 'std_dev': 2.5},
    'momentum': {'period': 30},
    'atr_breakout': {'period': 14, 'multiplier': 2.0},
    'donchian': {'period': 20},
    'volume_price': {'period': 10},
    'supertrend': {'period': 14, 'multiplier': 2.0},
    'kdj': {'n': 9, 'm1': 5, 'm2': 5},
    'cci': {'period': 14, 'upper': 150, 'lower': -150},
    'williams_r': {'period': 14, 'upper': -20, 'lower': -80},
    'ichimoku': {'tenkan_period': 9, 'kijun_period': 26, 'senkou_b_period': 52},
    'parabolic_sar': {'af_start': 0.03, 'af_max': 0.3},
    'obv': {},
    'adx': {'period': 14, 'threshold': 20.0},
    'mfi': {'period': 10, 'overbought': 80, 'oversold': 20},
    'vwap': {'period': 50},
    'stochastic': {'k_period': 14, 'd_period': 3, 'overbought': 80, 'oversold': 20},
    'heikin_ashi': {},
    'trix': {'period': 20, 'signal_period': 9},
    'aroon': {'period': 25},
    'ultimate_oscillator': {'short_period': 7, 'medium_period': 14, 'long_period': 28},
    'chaikin_money_flow': {'period': 30},
    'keltner_channel': {'period': 20, 'atr_multiplier': 2.0},
    'rate_of_change': {'period': 20},
    'tsi': {'long_period': 20, 'short_period': 10},
    'vortex_indicator': {'period': 20},
    'awesome_oscillator': {'short_period': 5, 'long_period': 34},
    'alligator': {'jaw_period': 13, 'teeth_period': 8, 'lips_period': 5},
}


class RealDataBacktest:
    """真实数据回测器"""
    
    def __init__(self, initial_cash: float = 100000):
        self.initial_cash = initial_cash
        self.data_provider = AshareDataProvider()
        self.results: List[BacktestResult] = []
    
    def run_single_strategy(
        self,
        strategy_name: str,
        symbol: str,
        data: pd.DataFrame
    ) -> Optional[BacktestResult]:
        """运行单策略回测"""
        try:
            params = BEST_PARAMS_30.get(strategy_name, {})
            signals = generate_strategy(data, strategy_name, **params)
            
            if signals.abs().sum() == 0:
                return None
            
            engine = BacktestEngine(
                initial_cash=self.initial_cash,
                commission_rate=0.00025,
                engine_type="ashare"
            )
            
            result = engine.run(data, signals, symbol=symbol)
            
            # 计算夏普比率
            sharpe = (result['return_pct'] / abs(result['max_drawdown']) 
                     if result['max_drawdown'] != 0 else 0)
            
            return BacktestResult(
                strategy_name=strategy_name,
                symbol=symbol,
                return_pct=result['return_pct'],
                max_drawdown=result['max_drawdown'],
                win_rate=result['win_rate'],
                total_trades=result['total_trades'],
                profit_factor=result.get('profit_factor', 0),
                sharpe_ratio=sharpe,
                start_date=str(data.index[0].date()),
                end_date=str(data.index[-1].date()),
                trading_days=len(data)
            )
            
        except Exception as e:
            print(f"   ❌ 回测失败: {e}")
            return None
    
    def run_all_strategies(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> List[BacktestResult]:
        """运行所有30个策略"""
        print(f"\n{'='*100}")
        print(f"🚀 回测标的: {symbol}")
        print(f"📅 回测区间: {start_date} ~ {end_date}")
        print(f"{'='*100}")
        
        # 获取数据
        print(f"\n📊 获取数据...")
        data = self.data_provider.get_stock_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )
        
        if data is None or len(data) < 100:
            print(f"⚠️  数据不足，跳过")
            return []
        
        print(f"   数据长度: {len(data)} 天")
        print(f"   日期范围: {data.index[0].date()} ~ {data.index[-1].date()}")
        print(f"   价格范围: {data['low'].min():.2f} ~ {data['high'].max():.2f}")
        
        # 计算基准收益 (买入持有)
        baseline_return = (data['close'].iloc[-1] / data['close'].iloc[0] - 1) * 100
        print(f"   基准收益 (买入持有): {baseline_return:+.2f}%")
        
        # 运行所有策略
        print(f"\n🧪 开始回测30个策略...")
        print("-" * 100)
        
        results = []
        strategy_names = list(BEST_PARAMS_30.keys())
        
        for i, strategy_name in enumerate(strategy_names, 1):
            print(f"\n{i:2d}. 测试 {strategy_name}...", end=" ")
            
            result = self.run_single_strategy(strategy_name, symbol, data)
            
            if result:
                results.append(result)
                print(f"✅ 收益={result.return_pct:>+7.2f}%, "
                      f"回撤={result.max_drawdown:>6.2f}%, "
                      f"胜率={result.win_rate:>5.1f}%, "
                      f"夏普={result.sharpe_ratio:>5.2f}")
            else:
                print(f"❌ 无信号或失败")
        
        return results
    
    def print_summary(self, results: List[BacktestResult], symbol: str):
        """打印汇总报告"""
        if not results:
            return
        
        print("\n" + "=" * 100)
        print(f"📊 回测结果汇总: {symbol}")
        print("=" * 100)
        
        # 排序
        by_return = sorted(results, key=lambda x: x.return_pct, reverse=True)
        by_sharpe = sorted(results, key=lambda x: x.sharpe_ratio, reverse=True)
        
        # TOP 10 收益
        print(f"\n🏆 收益排名 TOP 10:")
        print("-" * 100)
        print(f"{'排名':<4} {'策略':<20} {'收益':<10} {'回撤':<8} {'胜率':<8} {'夏普':<8} {'交易':<6}")
        print("-" * 100)
        
        for i, r in enumerate(by_return[:10], 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
            print(f"{medal} {i:<2} {r.strategy_name:<18} {r.return_pct:>+7.2f}% {r.max_drawdown:>6.2f}% "
                  f"{r.win_rate:>6.1f}% {r.sharpe_ratio:>6.2f} {r.total_trades:>4}")
        
        # TOP 10 夏普
        print(f"\n⚖️ 夏普比率排名 TOP 10:")
        print("-" * 100)
        print(f"{'排名':<4} {'策略':<20} {'夏普':<8} {'收益':<10} {'回撤':<8} {'胜率':<8}")
        print("-" * 100)
        
        for i, r in enumerate(by_sharpe[:10], 1):
            print(f"   {i:<2} {r.strategy_name:<18} {r.sharpe_ratio:>6.2f} {r.return_pct:>+7.2f}% "
                  f"{r.max_drawdown:>6.2f}% {r.win_rate:>6.1f}%")
        
        # 统计
        returns = [r.return_pct for r in results]
        sharpes = [r.sharpe_ratio for r in results]
        win_rates = [r.win_rate for r in results]
        
        print(f"\n📈 统计信息:")
        print(f"   策略数量: {len(results)}")
        print(f"   平均收益: {np.mean(returns):+.2f}%")
        print(f"   平均夏普: {np.mean(sharpes):.2f}")
        print(f"   平均胜率: {np.mean(win_rates):.1f}%")
        print(f"   正收益策略: {sum(1 for r in returns if r > 0)}/{len(results)}")
        print(f"   最佳策略: {by_return[0].strategy_name} ({by_return[0].return_pct:+.2f}%)")
        print(f"   最差策略: {by_return[-1].strategy_name} ({by_return[-1].return_pct:+.2f}%)")
        
        return by_return, by_sharpe
    
    def save_results(self, results: List[BacktestResult], symbol: str, filename: str = None):
        """保存结果"""
        if not results:
            return
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"reports/real_data_backtest_{symbol}_{timestamp}.json"
        
        import os
        os.makedirs('reports', exist_ok=True)
        
        data = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'total_strategies': len(results),
            'results': [
                {
                    'strategy': r.strategy_name,
                    'return_pct': r.return_pct,
                    'max_drawdown': r.max_drawdown,
                    'win_rate': r.win_rate,
                    'sharpe': r.sharpe_ratio,
                    'trades': r.total_trades
                }
                for r in results
            ]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 结果已保存: {filename}")


def run_multi_stock_backtest(
    symbols: List[str],
    start_date: str,
    end_date: str
) -> Dict[str, List[BacktestResult]]:
    """
    多股票回测
    
    Args:
        symbols: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期
    
    Returns:
        Dict[symbol, results]
    """
    print("=" * 100)
    print(f"🚀 多股票30策略回测")
    print(f"📅 回测区间: {start_date} ~ {end_date}")
    print(f"📊 股票数量: {len(symbols)}")
    print("=" * 100)
    
    backtester = RealDataBacktest()
    all_results = {}
    
    for symbol in symbols:
        results = backtester.run_all_strategies(symbol, start_date, end_date)
        if results:
            all_results[symbol] = results
            backtester.print_summary(results, symbol)
            backtester.save_results(results, symbol)
    
    # 跨股票汇总
    if all_results:
        print("\n" + "=" * 100)
        print("📊 跨股票汇总分析")
        print("=" * 100)
        
        # 统计每个策略在所有股票上的表现
        strategy_performance = {}
        for symbol, results in all_results.items():
            for r in results:
                if r.strategy_name not in strategy_performance:
                    strategy_performance[r.strategy_name] = []
                strategy_performance[r.strategy_name].append(r.return_pct)
        
        # 计算平均表现
        avg_performance = {
            name: np.mean(returns)
            for name, returns in strategy_performance.items()
        }
        
        sorted_strategies = sorted(avg_performance.items(), key=lambda x: x[1], reverse=True)
        
        print(f"\n🏆 跨股票平均收益排名 TOP 15:")
        print("-" * 100)
        print(f"{'排名':<4} {'策略':<20} {'平均收益':<12} {'胜率':<8}")
        print("-" * 100)
        
        for i, (name, avg_ret) in enumerate(sorted_strategies[:15], 1):
            positive = sum(1 for r in strategy_performance[name] if r > 0)
            total = len(strategy_performance[name])
            win_pct = positive / total * 100
            print(f"{i:<4} {name:<18} {avg_ret:>+9.2f}%    {win_pct:>5.1f}% ({positive}/{total})")
    
    return all_results


def main():
    """主函数"""
    print("=" * 100)
    print("🎯 Brain 30策略真实A股数据回测")
    print("=" * 100)
    
    # 测试单只股票
    symbol = "000001"  # 平安银行
    start_date = "2023-01-01"
    end_date = "2024-12-31"
    
    backtester = RealDataBacktest()
    results = backtester.run_all_strategies(symbol, start_date, end_date)
    
    if results:
        backtester.print_summary(results, symbol)
        backtester.save_results(results, symbol)
    
    # 多股票回测 (可选)
    # symbols = ["000001", "000002", "600519", "000858"]
    # run_multi_stock_backtest(symbols, start_date, end_date)
    
    print("\n" + "=" * 100)
    print("✅ 真实数据回测完成！")
    print("=" * 100)


if __name__ == "__main__":
    main()
