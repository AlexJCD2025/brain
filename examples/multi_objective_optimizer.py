#!/usr/bin/env python3
"""
多目标优化器

使用NSGA-II算法进行多目标优化
优化目标:
1. 最大化收益
2. 最小化回撤
3. 最大化胜率
4. 最大化夏普比率
5. 最大化交易次数(流动性)

输出: 帕累托前沿 - 一组不可支配的最优解
"""
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, field
import random
import copy

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.strategies.lib import generate_strategy
from brain.backtest import BacktestEngine


@dataclass
class Solution:
    """多目标优化解"""
    params: Dict[str, Any]
    objectives: Dict[str, float] = field(default_factory=dict)  # 目标函数值
    rank: int = 0  # 非支配排序等级
    crowding_distance: float = 0.0  # 拥挤距离
    dominated_count: int = 0  # 支配该解的解数量
    dominating_solutions: List = field(default_factory=list)  # 该解支配的解
    
    def dominates(self, other: 'Solution') -> bool:
        """判断是否支配另一个解"""
        # 假设所有目标都是最大化
        better_in_one = False
        for key in self.objectives:
            if key == 'max_drawdown':
                # 回撤是最小化目标
                if self.objectives[key] > other.objectives[key]:
                    return False
                elif self.objectives[key] < other.objectives[key]:
                    better_in_one = True
            else:
                # 其他是最大化目标
                if self.objectives[key] < other.objectives[key]:
                    return False
                elif self.objectives[key] > other.objectives[key]:
                    better_in_one = True
        return better_in_one


class NSGA2Optimizer:
    """NSGA-II多目标优化器"""
    
    def __init__(
        self,
        strategy_name: str,
        data: pd.DataFrame,
        param_ranges: Dict[str, Tuple],
        population_size: int = 100,
        generations: int = 50,
        crossover_rate: float = 0.9,
        mutation_rate: float = 0.1
    ):
        self.strategy_name = strategy_name
        self.data = data
        self.param_ranges = param_ranges
        self.population_size = population_size
        self.generations = generations
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        
        self.population: List[Solution] = []
        self.pareto_fronts: List[List[Solution]] = []
        
    def _random_param(self, param_name: str, param_range: Tuple) -> Any:
        """生成随机参数"""
        min_val, max_val, param_type = param_range
        
        if param_type == 'int':
            return random.randint(int(min_val), int(max_val))
        elif param_type == 'float':
            return round(random.uniform(min_val, max_val), 4)
        elif param_type == 'choice':
            return random.choice(param_range[0])
        else:
            raise ValueError(f"Unknown param type: {param_type}")
    
    def _create_solution(self) -> Solution:
        """创建随机解"""
        params = {}
        for param_name, param_range in self.param_ranges.items():
            params[param_name] = self._random_param(param_name, param_range)
        return Solution(params=params)
    
    def _evaluate_solution(self, solution: Solution):
        """评估解的目标函数"""
        try:
            signals = generate_strategy(self.data, self.strategy_name, **solution.params)
            
            if signals.abs().sum() == 0:
                solution.objectives = {
                    'return_pct': -999,
                    'max_drawdown': 999,
                    'win_rate': 0,
                    'sharpe': -999,
                    'trades': 0
                }
                return
            
            engine = BacktestEngine(
                initial_cash=100000,
                commission_rate=0.00025,
                engine_type="ashare"
            )
            
            result = engine.run(self.data, signals, symbol="TEST")
            
            # 计算夏普
            sharpe = result['return_pct'] / abs(result['max_drawdown']) if result['max_drawdown'] != 0 else 0
            
            solution.objectives = {
                'return_pct': result['return_pct'],
                'max_drawdown': -result['max_drawdown'],  # 转为最大化
                'win_rate': result['win_rate'],
                'sharpe': sharpe,
                'trades': result['total_trades']
            }
            
        except Exception as e:
            solution.objectives = {
                'return_pct': -999,
                'max_drawdown': 0,
                'win_rate': 0,
                'sharpe': -999,
                'trades': 0
            }
    
    def _non_dominated_sort(self, population: List[Solution]) -> List[List[Solution]]:
        """非支配排序"""
        fronts = [[]]
        
        for p in population:
            p.dominated_count = 0
            p.dominating_solutions = []
            
            for q in population:
                if p.dominates(q):
                    p.dominating_solutions.append(q)
                elif q.dominates(p):
                    p.dominated_count += 1
            
            if p.dominated_count == 0:
                p.rank = 0
                fronts[0].append(p)
        
        i = 0
        while len(fronts[i]) > 0:
            next_front = []
            for p in fronts[i]:
                for q in p.dominating_solutions:
                    q.dominated_count -= 1
                    if q.dominated_count == 0:
                        q.rank = i + 1
                        next_front.append(q)
            i += 1
            fronts.append(next_front)
        
        return fronts[:-1]  # 去除空的最后一个
    
    def _calculate_crowding_distance(self, front: List[Solution]):
        """计算拥挤距离"""
        if len(front) <= 2:
            for s in front:
                s.crowding_distance = float('inf')
            return
        
        for s in front:
            s.crowding_distance = 0
        
        objectives = list(front[0].objectives.keys())
        
        for obj in objectives:
            front.sort(key=lambda x: x.objectives[obj])
            
            min_val = front[0].objectives[obj]
            max_val = front[-1].objectives[obj]
            
            front[0].crowding_distance = float('inf')
            front[-1].crowding_distance = float('inf')
            
            for i in range(1, len(front) - 1):
                if max_val - min_val > 0:
                    front[i].crowding_distance += (
                        (front[i+1].objectives[obj] - front[i-1].objectives[obj]) / 
                        (max_val - min_val)
                    )
    
    def _tournament_selection(self) -> Solution:
        """锦标赛选择"""
        candidates = random.sample(self.population, min(2, len(self.population)))
        candidates.sort(key=lambda x: (x.rank, -x.crowding_distance))
        return copy.deepcopy(candidates[0])
    
    def _crossover(self, parent1: Solution, parent2: Solution) -> Tuple[Solution, Solution]:
        """交叉操作"""
        if random.random() > self.crossover_rate:
            return copy.deepcopy(parent1), copy.deepcopy(parent2)
        
        child1_params = {}
        child2_params = {}
        
        for param_name in self.param_ranges.keys():
            if random.random() < 0.5:
                child1_params[param_name] = parent1.params[param_name]
                child2_params[param_name] = parent2.params[param_name]
            else:
                child1_params[param_name] = parent2.params[param_name]
                child2_params[param_name] = parent1.params[param_name]
        
        return Solution(params=child1_params), Solution(params=child2_params)
    
    def _mutate(self, solution: Solution):
        """变异"""
        for param_name, param_range in self.param_ranges.items():
            if random.random() < self.mutation_rate:
                solution.params[param_name] = self._random_param(param_name, param_range)
    
    def _make_new_population(self) -> List[Solution]:
        """生成新种群"""
        new_population = []
        
        while len(new_population) < self.population_size:
            parent1 = self._tournament_selection()
            parent2 = self._tournament_selection()
            
            child1, child2 = self._crossover(parent1, parent2)
            
            self._mutate(child1)
            self._mutate(child2)
            
            self._evaluate_solution(child1)
            self._evaluate_solution(child2)
            
            new_population.append(child1)
            if len(new_population) < self.population_size:
                new_population.append(child2)
        
        return new_population
    
    def optimize(self) -> List[Solution]:
        """执行NSGA-II优化"""
        print(f"\n🧬 NSGA-II多目标优化: {self.strategy_name}")
        print(f"   种群大小: {self.population_size}, 迭代: {self.generations}")
        print(f"   优化目标: 收益↑, 回撤↓, 胜率↑, 夏普↑, 交易次数↑")
        
        # 初始化
        print(f"\n   初始化种群...")
        self.population = [self._create_solution() for _ in range(self.population_size)]
        for s in self.population:
            self._evaluate_solution(s)
        
        # 进化
        for generation in range(1, self.generations + 1):
            # 生成子代
            offspring = self._make_new_population()
            
            # 合并父代和子代
            combined = self.population + offspring
            
            # 非支配排序
            fronts = self._non_dominated_sort(combined)
            
            # 计算拥挤距离
            for front in fronts:
                self._calculate_crowding_distance(front)
            
            # 选择下一代
            self.population = []
            for front in fronts:
                if len(self.population) + len(front) <= self.population_size:
                    self.population.extend(front)
                else:
                    # 按拥挤距离排序，选择多样性好的
                    front.sort(key=lambda x: -x.crowding_distance)
                    remaining = self.population_size - len(self.population)
                    self.population.extend(front[:remaining])
                    break
            
            # 记录第一前沿
            self.pareto_fronts = fronts
            
            if generation % 10 == 0 or generation == 1:
                first_front_size = len(fronts[0]) if fronts else 0
                avg_return = np.mean([s.objectives['return_pct'] for s in fronts[0]]) if fronts else 0
                print(f"   第 {generation:2d} 代: 帕累托前沿大小 = {first_front_size}, 平均收益 = {avg_return:+.2f}%")
        
        return self.pareto_fronts[0] if self.pareto_fronts else []


def print_pareto_front(solutions: List[Solution], top_n: int = 10):
    """打印帕累托前沿"""
    print(f"\n📊 帕累托前沿 (共 {len(solutions)} 个解):")
    print("-" * 100)
    print(f"{'排名':<4} {'参数':<40} {'收益':<8} {'回撤':<8} {'胜率':<8} {'夏普':<8} {'交易':<6}")
    print("-" * 100)
    
    # 按收益排序显示
    sorted_solutions = sorted(solutions, key=lambda x: x.objectives['return_pct'], reverse=True)
    
    for i, s in enumerate(sorted_solutions[:top_n], 1):
        params_str = str(s.params)[:38]
        obj = s.objectives
        print(f"{i:<4} {params_str:<40} "
              f"{obj['return_pct']:>+6.2f}% {abs(obj['max_drawdown']):>6.2f}% "
              f"{obj['win_rate']:>6.1f}% {obj['sharpe']:>6.2f} {obj['trades']:>4}")


def get_param_ranges(strategy_name: str) -> Dict[str, Tuple]:
    """获取参数范围"""
    ranges = {
        'bollinger': {
            'period': (10, 30, 'int'),
            'std_dev': (1.5, 3.5, 'float')
        },
        'atr_breakout': {
            'period': (10, 30, 'int'),
            'multiplier': (1.0, 4.0, 'float')
        },
        'keltner_channel': {
            'period': (15, 30, 'int'),
            'atr_multiplier': (1.0, 3.5, 'float')
        },
    }
    return ranges.get(strategy_name, {})


def generate_test_data(days=500, seed=42):
    """生成测试数据"""
    np.random.seed(seed)
    dates = pd.date_range(start='2022-01-01', periods=days, freq='B')
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
    print("🎯 NSGA-II 多目标优化")
    print("=" * 100)
    
    # 生成数据
    print("\n📊 生成测试数据...")
    data = generate_test_data(days=500)
    
    # 优化布林带
    print(f"\n{'='*100}")
    print("🧪 优化策略: 布林带")
    
    optimizer = NSGA2Optimizer(
        strategy_name='bollinger',
        data=data,
        param_ranges=get_param_ranges('bollinger'),
        population_size=50,
        generations=30
    )
    
    pareto_front = optimizer.optimize()
    
    if pareto_front:
        print_pareto_front(pareto_front)
        
        # 输出不同偏好的解
        print(f"\n💡 根据不同偏好的推荐:")
        
        # 高收益
        high_return = max(pareto_front, key=lambda x: x.objectives['return_pct'])
        print(f"\n   📈 高收益偏好:")
        print(f"      参数: {high_return.params}")
        print(f"      收益: {high_return.objectives['return_pct']:+.2f}%")
        print(f"      回撤: {abs(high_return.objectives['max_drawdown']):.2f}%")
        
        # 低风险
        low_risk = max(pareto_front, key=lambda x: x.objectives['max_drawdown'])
        print(f"\n   🛡️ 低风险偏好:")
        print(f"      参数: {low_risk.params}")
        print(f"      收益: {low_risk.objectives['return_pct']:+.2f}%")
        print(f"      回撤: {abs(low_risk.objectives['max_drawdown']):.2f}%")
        
        # 高夏普
        high_sharpe = max(pareto_front, key=lambda x: x.objectives['sharpe'])
        print(f"\n   ⚖️ 高夏普偏好:")
        print(f"      参数: {high_sharpe.params}")
        print(f"      夏普: {high_sharpe.objectives['sharpe']:.2f}")
        print(f"      收益: {high_sharpe.objectives['return_pct']:+.2f}%")
    
    print("\n" + "=" * 100)
    print("✅ 多目标优化完成！")
    print("=" * 100)


if __name__ == "__main__":
    main()
