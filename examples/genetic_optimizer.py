#!/usr/bin/env python3
"""
遗传算法参数优化器

使用遗传算法(GA)自动搜索最优策略参数
优势:
1. 不需要遍历所有参数组合，效率更高
2. 可以跳出局部最优
3. 适合高维参数空间
4. 支持多目标优化
"""
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any, Callable
from dataclasses import dataclass, field
import random
import copy
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.strategies.lib import generate_strategy
from brain.backtest import BacktestEngine


@dataclass
class Individual:
    """遗传算法个体"""
    params: Dict[str, Any]
    fitness: float = 0.0
    return_pct: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    sharpe: float = 0.0
    trades: int = 0
    generation: int = 0
    
    def __lt__(self, other):
        return self.fitness < other.fitness


class GeneticOptimizer:
    """遗传算法优化器"""
    
    def __init__(
        self,
        strategy_name: str,
        data: pd.DataFrame,
        param_ranges: Dict[str, Tuple],
        population_size: int = 50,
        generations: int = 30,
        crossover_rate: float = 0.8,
        mutation_rate: float = 0.2,
        elitism: int = 5,
        multi_objective: bool = False,
        n_jobs: int = 4
    ):
        """
        初始化遗传算法优化器
        
        Args:
            strategy_name: 策略名称
            data: 回测数据
            param_ranges: 参数范围字典 {param: (min, max, type)}
            population_size: 种群大小
            generations: 迭代代数
            crossover_rate: 交叉概率
            mutation_rate: 变异概率
            elitism: 保留精英数量
            multi_objective: 是否多目标优化
            n_jobs: 并行线程数
        """
        self.strategy_name = strategy_name
        self.data = data
        self.param_ranges = param_ranges
        self.population_size = population_size
        self.generations = generations
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.elitism = elitism
        self.multi_objective = multi_objective
        self.n_jobs = n_jobs
        
        self.population: List[Individual] = []
        self.best_individual: Individual = None
        self.fitness_history: List[float] = []
        self.diversity_history: List[float] = []
        
    def _random_param(self, param_name: str, param_range: Tuple) -> Any:
        """生成随机参数值"""
        min_val, max_val, param_type = param_range
        
        if param_type == 'int':
            return random.randint(int(min_val), int(max_val))
        elif param_type == 'float':
            return round(random.uniform(min_val, max_val), 4)
        elif param_type == 'choice':
            return random.choice(param_range[0])  # 第一个元素是选项列表
        else:
            raise ValueError(f"Unknown param type: {param_type}")
    
    def _create_individual(self) -> Individual:
        """创建随机个体"""
        params = {}
        for param_name, param_range in self.param_ranges.items():
            params[param_name] = self._random_param(param_name, param_range)
        return Individual(params=params)
    
    def _initialize_population(self):
        """初始化种群"""
        print(f"   初始化种群 ({self.population_size} 个体)...")
        self.population = [self._create_individual() for _ in range(self.population_size)]
    
    def _evaluate_individual(self, individual: Individual) -> Individual:
        """评估单个个体"""
        try:
            signals = generate_strategy(self.data, self.strategy_name, **individual.params)
            
            if signals.abs().sum() == 0:
                individual.fitness = -999
                return individual
            
            engine = BacktestEngine(
                initial_cash=100000,
                commission_rate=0.00025,
                engine_type="ashare"
            )
            
            result = engine.run(self.data, signals, symbol="TEST")
            
            individual.return_pct = result['return_pct']
            individual.max_drawdown = result['max_drawdown']
            individual.win_rate = result['win_rate']
            individual.trades = result['total_trades']
            
            # 计算夏普比率
            if individual.max_drawdown != 0:
                individual.sharpe = individual.return_pct / abs(individual.max_drawdown)
            else:
                individual.sharpe = 0
            
            # 适应度函数
            if self.multi_objective:
                # 多目标: 收益、回撤、胜率、夏普
                individual.fitness = (
                    individual.return_pct * 0.35 +
                    individual.sharpe * 30 +
                    individual.win_rate * 0.25 +
                    min(individual.trades / 30, 1.0) * 5
                )
            else:
                # 单目标: 综合得分
                individual.fitness = (
                    individual.return_pct * 0.4 +
                    individual.sharpe * 25 +
                    individual.win_rate * 0.2 +
                    (100 - min(individual.trades / 50, 1.0) * 10) * 0.1
                )
            
        except Exception as e:
            individual.fitness = -999
        
        return individual
    
    def _evaluate_population(self):
        """评估整个种群"""
        print(f"   评估种群适应度...")
        
        if self.n_jobs > 1:
            # 并行评估
            with ProcessPoolExecutor(max_workers=self.n_jobs) as executor:
                futures = {executor.submit(self._evaluate_individual, ind): i 
                          for i, ind in enumerate(self.population)}
                
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        self.population[idx] = future.result()
                    except:
                        pass
        else:
            # 串行评估
            for i, individual in enumerate(self.population):
                self.population[i] = self._evaluate_individual(individual)
                if (i + 1) % 10 == 0:
                    print(f"     已评估 {i+1}/{self.population_size}")
    
    def _select_parent(self) -> Individual:
        """锦标赛选择"""
        tournament_size = 3
        tournament = random.sample(self.population, min(tournament_size, len(self.population)))
        return max(tournament, key=lambda x: x.fitness)
    
    def _crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
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
        
        child1 = Individual(params=child1_params)
        child2 = Individual(params=child2_params)
        
        return child1, child2
    
    def _mutate(self, individual: Individual) -> Individual:
        """变异操作"""
        mutated = False
        
        for param_name, param_range in self.param_ranges.items():
            if random.random() < self.mutation_rate:
                # 变异: 生成新值或在当前值附近扰动
                if random.random() < 0.5:
                    # 完全随机新值
                    individual.params[param_name] = self._random_param(param_name, param_range)
                else:
                    # 在当前值附近扰动
                    current = individual.params[param_name]
                    min_val, max_val, param_type = param_range
                    
                    if param_type == 'int':
                        perturbation = random.randint(-3, 3)
                        individual.params[param_name] = max(min_val, min(max_val, current + perturbation))
                    elif param_type == 'float':
                        perturbation = random.uniform(-0.1, 0.1) * (max_val - min_val)
                        individual.params[param_name] = round(max(min_val, min(max_val, current + perturbation)), 4)
                
                mutated = True
        
        return individual
    
    def _calculate_diversity(self) -> float:
        """计算种群多样性"""
        if len(self.population) < 2:
            return 0.0
        
        # 计算参数的标准差作为多样性指标
        diversities = []
        for param_name in self.param_ranges.keys():
            values = [ind.params[param_name] for ind in self.population]
            if all(isinstance(v, (int, float)) for v in values):
                diversities.append(np.std(values))
        
        return np.mean(diversities) if diversities else 0.0
    
    def _evolve_generation(self, generation: int):
        """进化一代"""
        # 评估
        self._evaluate_population()
        
        # 排序
        self.population.sort(reverse=True)
        
        # 记录最佳
        current_best = self.population[0]
        if self.best_individual is None or current_best.fitness > self.best_individual.fitness:
            self.best_individual = copy.deepcopy(current_best)
        
        self.fitness_history.append(current_best.fitness)
        self.diversity_history.append(self._calculate_diversity())
        
        print(f"   第 {generation:2d} 代: 最佳适应度 = {current_best.fitness:.2f}, "
              f"收益 = {current_best.return_pct:+.2f}%, "
              f"夏普 = {current_best.sharpe:.2f}")
        
        # 精英保留
        new_population = self.population[:self.elitism]
        
        # 生成新个体
        while len(new_population) < self.population_size:
            parent1 = self._select_parent()
            parent2 = self._select_parent()
            
            child1, child2 = self._crossover(parent1, parent2)
            
            child1 = self._mutate(child1)
            child2 = self._mutate(child2)
            
            new_population.append(child1)
            if len(new_population) < self.population_size:
                new_population.append(child2)
        
        self.population = new_population
    
    def optimize(self) -> Individual:
        """执行优化"""
        print(f"\n🧬 遗传算法优化: {self.strategy_name}")
        print(f"   参数范围: {list(self.param_ranges.keys())}")
        print(f"   种群大小: {self.population_size}, 迭代: {self.generations}")
        
        # 初始化
        self._initialize_population()
        
        # 进化
        for generation in range(1, self.generations + 1):
            self._evolve_generation(generation)
        
        # 最终评估
        self._evaluate_population()
        self.population.sort(reverse=True)
        
        return self.best_individual
    
    def plot_convergence(self):
        """绘制收敛曲线"""
        try:
            import matplotlib.pyplot as plt
            
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
            
            # 适应度曲线
            ax1.plot(self.fitness_history, 'b-', linewidth=2, label='Best Fitness')
            ax1.set_xlabel('Generation')
            ax1.set_ylabel('Fitness')
            ax1.set_title(f'GA Convergence: {self.strategy_name}')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # 多样性曲线
            ax2.plot(self.diversity_history, 'r-', linewidth=2, label='Population Diversity')
            ax2.set_xlabel('Generation')
            ax2.set_ylabel('Diversity')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            plt.savefig(f'ga_convergence_{self.strategy_name}.png', dpi=150)
            print(f"   收敛图已保存: ga_convergence_{self.strategy_name}.png")
        except Exception as e:
            print(f"   绘图失败: {e}")


# ============================================================
# 策略参数范围定义
# ============================================================

def get_param_ranges(strategy_name: str) -> Dict[str, Tuple]:
    """获取策略的参数范围"""
    
    ranges = {
        'dual_ma': {
            'fast': (3, 20, 'int'),
            'slow': (15, 60, 'int'),
            'ma_type': (['sma', 'ema'], None, 'choice')
        },
        'macd': {
            'fast': (5, 20, 'int'),
            'slow': (20, 50, 'int'),
            'signal': (5, 15, 'int')
        },
        'rsi': {
            'period': (5, 30, 'int'),
            'overbought': (65, 85, 'int'),
            'oversold': (15, 35, 'int')
        },
        'bollinger': {
            'period': (10, 30, 'int'),
            'std_dev': (1.5, 3.5, 'float')
        },
        'momentum': {
            'period': (10, 60, 'int')
        },
        'atr_breakout': {
            'period': (10, 30, 'int'),
            'multiplier': (1.0, 4.0, 'float')
        },
        'donchian': {
            'period': (15, 100, 'int')
        },
        'supertrend': {
            'period': (7, 21, 'int'),
            'multiplier': (1.0, 4.0, 'float')
        },
        'awesome_oscillator': {
            'short_period': (3, 10, 'int'),
            'long_period': (20, 50, 'int')
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
    print("🧬 遗传算法策略参数优化")
    print("=" * 100)
    
    # 生成数据
    print("\n📊 生成测试数据...")
    data = generate_test_data(days=500)
    
    # 选择要优化的策略
    strategies_to_optimize = [
        'bollinger',
        'atr_breakout',
        'awesome_oscillator',
        'keltner_channel',
        'rsi',
    ]
    
    results = []
    
    for strategy_name in strategies_to_optimize:
        param_ranges = get_param_ranges(strategy_name)
        
        if not param_ranges:
            print(f"\n⚠️  {strategy_name}: 未定义参数范围，跳过")
            continue
        
        print(f"\n{'='*80}")
        
        # 创建优化器
        optimizer = GeneticOptimizer(
            strategy_name=strategy_name,
            data=data,
            param_ranges=param_ranges,
            population_size=30,
            generations=20,
            crossover_rate=0.8,
            mutation_rate=0.25,
            elitism=3,
            multi_objective=True,
            n_jobs=1  # 先单线程测试
        )
        
        # 执行优化
        best = optimizer.optimize()
        
        if best and best.fitness > -900:
            results.append({
                'strategy': strategy_name,
                'params': best.params,
                'fitness': best.fitness,
                'return_pct': best.return_pct,
                'max_drawdown': best.max_drawdown,
                'win_rate': best.win_rate,
                'sharpe': best.sharpe,
                'trades': best.trades
            })
            
            print(f"\n   ✅ 最佳参数: {best.params}")
            print(f"      适应度: {best.fitness:.2f}")
            print(f"      收益: {best.return_pct:+.2f}%")
            print(f"      回撤: {best.max_drawdown:.2f}%")
            print(f"      胜率: {best.win_rate:.1f}%")
            print(f"      夏普: {best.sharpe:.2f}")
            print(f"      交易: {best.trades}")
            
            # 尝试绘图
            try:
                optimizer.plot_convergence()
            except:
                pass
    
    # 汇总报告
    print("\n" + "=" * 100)
    print("📊 遗传算法优化结果汇总")
    print("=" * 100)
    
    if results:
        results.sort(key=lambda x: x['fitness'], reverse=True)
        
        print(f"\n{'排名':<4} {'策略':<20} {'最佳参数':<30} {'适应度':<8} {'收益':<10} {'夏普':<8}")
        print("-" * 100)
        
        for i, r in enumerate(results, 1):
            params_str = str(r['params'])[:28]
            print(f"{i:<4} {r['strategy']:<18} {params_str:<30} "
                  f"{r['fitness']:>7.2f} {r['return_pct']:>+8.2f}% {r['sharpe']:>7.2f}")
        
        # 生成Python代码
        print("\n" + "=" * 100)
        print("💡 遗传算法优化后的最佳参数")
        print("=" * 100)
        print("\n```python")
        print("# 遗传算法优化参数 (GA Optimized)")
        print("GA_BEST_PARAMS = {")
        for r in results:
            print(f"    '{r['strategy']}': {r['params']},")
        print("}")
        print("```")
    else:
        print("\n⚠️  无有效优化结果")
    
    print("\n" + "=" * 100)
    print("✅ 遗传算法优化完成！")
    print("=" * 100)


if __name__ == "__main__":
    main()
