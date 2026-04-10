#!/usr/bin/env python3
"""
Walk-Forward 分析

避免过拟合的金标准方法
流程:
1. 将数据分成多个窗口
2. 训练窗口内优化参数
3. 测试窗口验证表现
4. 滑动窗口继续
5. 汇总所有测试结果

优点:
- 模拟真实交易场景
- 检测策略稳健性
- 避免过拟合
- 更接近实盘表现
"""
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.strategies.lib import generate_strategy
from brain.backtest import BacktestEngine


@dataclass
class WFResult:
    """Walk-Forward结果"""
    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    best_params: Dict
    train_return: float
    train_dd: float
    train_win_rate: float
    test_return: float
    test_dd: float
    test_win_rate: float
    parameter_stability: float  # 参数稳定性评分


class WalkForwardAnalyzer:
    """Walk-Forward分析器"""
    
    def __init__(
        self,
        data: pd.DataFrame,
        train_size: int = 200,    # 训练窗口大小
        test_size: int = 50,       # 测试窗口大小
        step_size: int = 50,       # 滑动步长
        strategy_name: str = None,
        param_grid: List[Dict] = None
    ):
        self.data = data
        self.train_size = train_size
        self.test_size = test_size
        self.step_size = step_size
        self.strategy_name = strategy_name
        self.param_grid = param_grid or []
        self.results: List[WFResult] = []
        
    def _create_windows(self) -> List[Tuple[int, int, int, int]]:
        """创建滑动窗口"""
        windows = []
        total_len = len(self.data)
        
        start = 0
        while start + self.train_size + self.test_size <= total_len:
            train_start = start
            train_end = start + self.train_size
            test_start = train_end
            test_end = train_end + self.test_size
            
            windows.append((train_start, train_end, test_start, test_end))
            start += self.step_size
        
        return windows
    
    def _optimize_params(self, train_data: pd.DataFrame) -> Tuple[Dict, Dict]:
        """在训练数据上优化参数"""
        best_params = None
        best_score = -999
        best_result = None
        
        for params in self.param_grid:
            try:
                signals = generate_strategy(train_data, self.strategy_name, **params)
                
                if signals.abs().sum() == 0:
                    continue
                
                engine = BacktestEngine(
                    initial_cash=100000,
                    commission_rate=0.00025,
                    engine_type="ashare"
                )
                
                result = engine.run(train_data, signals, symbol="TRAIN")
                
                # 评分
                score = (
                    result['return_pct'] * 0.4 +
                    (result['return_pct'] / abs(result['max_drawdown']) if result['max_drawdown'] != 0 else 0) * 30 +
                    result['win_rate'] * 0.2 +
                    (100 - min(result['total_trades'] / 50, 1.0) * 10) * 0.1
                )
                
                if score > best_score:
                    best_score = score
                    best_params = params
                    best_result = result
                    
            except Exception as e:
                continue
        
        return best_params, best_result or {}
    
    def _test_params(self, test_data: pd.DataFrame, params: Dict) -> Dict:
        """在测试数据上验证参数"""
        try:
            signals = generate_strategy(test_data, self.strategy_name, **params)
            
            if signals.abs().sum() == 0:
                return {}
            
            engine = BacktestEngine(
                initial_cash=100000,
                commission_rate=0.00025,
                engine_type="ashare"
            )
            
            return engine.run(test_data, signals, symbol="TEST")
        except:
            return {}
    
    def analyze(self) -> List[WFResult]:
        """执行Walk-Forward分析"""
        print(f"\n📊 Walk-Forward分析参数:")
        print(f"   数据长度: {len(self.data)}")
        print(f"   训练窗口: {self.train_size} 天")
        print(f"   测试窗口: {self.test_size} 天")
        print(f"   滑动步长: {self.step_size} 天")
        
        windows = self._create_windows()
        print(f"   窗口数量: {len(windows)}")
        
        if len(windows) == 0:
            print("⚠️  数据不足以创建窗口")
            return []
        
        for i, (train_s, train_e, test_s, test_e) in enumerate(windows, 1):
            print(f"\n{'='*80}")
            print(f"🔄 窗口 {i}/{len(windows)}")
            
            train_data = self.data.iloc[train_s:train_e]
            test_data = self.data.iloc[test_s:test_e]
            
            train_dates = f"{train_data.index[0].date()} ~ {train_data.index[-1].date()}"
            test_dates = f"{test_data.index[0].date()} ~ {test_data.index[-1].date()}"
            
            print(f"   训练期: {train_dates}")
            print(f"   测试期: {test_dates}")
            
            # 训练优化
            print(f"   优化参数中...")
            best_params, train_result = self._optimize_params(train_data)
            
            if not best_params:
                print(f"   ⚠️  优化失败")
                continue
            
            print(f"   训练表现: 收益={train_result.get('return_pct', 0):+.2f}%, "
                  f"回撤={train_result.get('max_drawdown', 0):.2f}%, "
                  f"胜率={train_result.get('win_rate', 0):.1f}%")
            
            # 测试验证
            print(f"   测试验证中...")
            test_result = self._test_params(test_data, best_params)
            
            if not test_result:
                print(f"   ⚠️  测试失败")
                continue
            
            print(f"   测试表现: 收益={test_result.get('return_pct', 0):+.2f}%, "
                  f"回撤={test_result.get('max_drawdown', 0):.2f}%, "
                  f"胜率={test_result.get('win_rate', 0):.1f}%")
            
            # 计算参数稳定性
            train_ret = train_result.get('return_pct', 0)
            test_ret = test_result.get('return_pct', 0)
            stability = 1 - abs(train_ret - test_ret) / (abs(train_ret) + 1e-6) if train_ret != 0 else 0
            stability = max(0, min(1, stability))
            
            wf_result = WFResult(
                window_id=i,
                train_start=str(train_data.index[0]),
                train_end=str(train_data.index[-1]),
                test_start=str(test_data.index[0]),
                test_end=str(test_data.index[-1]),
                best_params=best_params,
                train_return=train_ret,
                train_dd=train_result.get('max_drawdown', 0),
                train_win_rate=train_result.get('win_rate', 0),
                test_return=test_ret,
                test_dd=test_result.get('max_drawdown', 0),
                test_win_rate=test_result.get('win_rate', 0),
                parameter_stability=stability
            )
            
            self.results.append(wf_result)
        
        return self.results
    
    def generate_report(self) -> Dict:
        """生成分析报告"""
        if not self.results:
            return {}
        
        # 统计
        train_returns = [r.train_return for r in self.results]
        test_returns = [r.test_return for r in self.results]
        stabilities = [r.parameter_stability for r in self.results]
        
        # 过拟合检测
        overfit_score = np.mean([r.train_return - r.test_return for r in self.results])
        
        # 一致性检测
        positive_windows = sum(1 for r in self.results if r.test_return > 0)
        consistency = positive_windows / len(self.results) * 100
        
        report = {
            'strategy': self.strategy_name,
            'total_windows': len(self.results),
            'train': {
                'mean_return': np.mean(train_returns),
                'std_return': np.std(train_returns),
                'best_return': max(train_returns),
                'worst_return': min(train_returns),
            },
            'test': {
                'mean_return': np.mean(test_returns),
                'std_return': np.std(test_returns),
                'best_return': max(test_returns),
                'worst_return': min(test_returns),
            },
            'robustness': {
                'overfit_score': overfit_score,
                'consistency': consistency,
                'avg_stability': np.mean(stabilities),
                'is_robust': overfit_score < 5 and consistency > 50
            },
            'windows': [
                {
                    'id': r.window_id,
                    'best_params': r.best_params,
                    'train_return': r.train_return,
                    'test_return': r.test_return,
                    'stability': r.parameter_stability
                }
                for r in self.results
            ]
        }
        
        return report


def print_report(report: Dict):
    """打印报告"""
    print("\n" + "=" * 100)
    print(f"📊 Walk-Forward分析报告: {report['strategy']}")
    print("=" * 100)
    
    print(f"\n窗口数量: {report['total_windows']}")
    
    print(f"\n📈 训练表现 (样本内):")
    print(f"   平均收益: {report['train']['mean_return']:+.2f}%")
    print(f"   收益标准差: {report['train']['std_return']:.2f}%")
    print(f"   最佳: {report['train']['best_return']:+.2f}%")
    print(f"   最差: {report['train']['worst_return']:+.2f}%")
    
    print(f"\n📉 测试表现 (样本外):")
    print(f"   平均收益: {report['test']['mean_return']:+.2f}%")
    print(f"   收益标准差: {report['test']['std_return']:.2f}%")
    print(f"   最佳: {report['test']['best_return']:+.2f}%")
    print(f"   最差: {report['test']['worst_return']:+.2f}%")
    
    print(f"\n🔍 稳健性分析:")
    print(f"   过拟合评分: {report['robustness']['overfit_score']:+.2f}% (越低越好)")
    print(f"   一致性: {report['robustness']['consistency']:.1f}% 窗口盈利")
    print(f"   平均稳定性: {report['robustness']['avg_stability']:.2f}")
    
    robust = "✅ 稳健" if report['robustness']['is_robust'] else "❌ 可能过拟合"
    print(f"   结论: {robust}")
    
    # 参数一致性
    print(f"\n📝 各窗口最佳参数:")
    for w in report['windows'][:5]:  # 显示前5个
        params_str = str(w['best_params'])
        print(f"   窗口{w['id']}: {params_str}")
        print(f"           训练={w['train_return']:+.2f}% 测试={w['test_return']:+.2f}% 稳定={w['stability']:.2f}")


def generate_test_data(days=800, seed=42):
    """生成测试数据"""
    np.random.seed(seed)
    dates = pd.date_range(start='2020-01-01', periods=days, freq='B')
    returns = np.random.normal(0.0003, 0.02, days)
    prices = 100 * (1 + returns).cumprod()
    
    data = []
    for i, (date, close) in enumerate(zip(dates, prices)):
        daily_range = close * 0.01
        open_price = close + np.random.normal(0, daily_range * 0.3)
        high_price = max(open_price, close) + abs(np.random.normal(0, daily_range * 0.3))
        low_price = min(open_price, close) - abs(np.random.normal(0, daily_range * 0.3))
        
        data.append({
            'datetime': date,
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close, 2),
            'volume': int(np.random.normal(1000000, 300000)),
            'pre_close': round(prices[i-1], 2) if i > 0 else round(close * 0.99, 2)
        })
    
    df = pd.DataFrame(data)
    df.set_index('datetime', inplace=True)
    return df


def main():
    print("=" * 100)
    print("🔄 Walk-Forward 分析 (避免过拟合)")
    print("=" * 100)
    
    # 生成数据
    print("\n📊 生成测试数据...")
    data = generate_test_data(days=800)
    print(f"   数据长度: {len(data)}")
    print(f"   日期范围: {data.index[0].date()} ~ {data.index[-1].date()}")
    
    # 定义参数网格
    bollinger_grid = [
        {'period': 10, 'std_dev': 2.0},
        {'period': 15, 'std_dev': 2.5},
        {'period': 20, 'std_dev': 2.0},
        {'period': 20, 'std_dev': 2.5},
        {'period': 25, 'std_dev': 2.5},
    ]
    
    atr_grid = [
        {'period': 10, 'multiplier': 1.5},
        {'period': 14, 'multiplier': 2.0},
        {'period': 20, 'multiplier': 2.5},
    ]
    
    # 分析布林带
    print(f"\n{'='*100}")
    print("🧪 分析策略: 布林带")
    analyzer1 = WalkForwardAnalyzer(
        data=data,
        train_size=200,
        test_size=50,
        step_size=50,
        strategy_name='bollinger',
        param_grid=bollinger_grid
    )
    
    analyzer1.analyze()
    report1 = analyzer1.generate_report()
    if report1:
        print_report(report1)
    
    # 分析ATR突破
    print(f"\n{'='*100}")
    print("🧪 分析策略: ATR突破")
    analyzer2 = WalkForwardAnalyzer(
        data=data,
        train_size=200,
        test_size=50,
        step_size=50,
        strategy_name='atr_breakout',
        param_grid=atr_grid
    )
    
    analyzer2.analyze()
    report2 = analyzer2.generate_report()
    if report2:
        print_report(report2)
    
    # 总结
    print("\n" + "=" * 100)
    print("📊 Walk-Forward分析总结")
    print("=" * 100)
    
    reports = [r for r in [report1, report2] if r]
    
    for r in reports:
        robust = "✅" if r['robustness']['is_robust'] else "❌"
        print(f"\n{robust} {r['strategy']}:")
        print(f"   训练收益: {r['train']['mean_return']:+.2f}%")
        print(f"   测试收益: {r['test']['mean_return']:+.2f}%")
        print(f"   一致性: {r['robustness']['consistency']:.1f}%")
        print(f"   过拟合: {r['robustness']['overfit_score']:+.2f}%")
    
    print("\n" + "=" * 100)
    print("✅ Walk-Forward分析完成！")
    print("=" * 100)


if __name__ == "__main__":
    main()
