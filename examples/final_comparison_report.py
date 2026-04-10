#!/usr/bin/env python3
"""
最终对比报告 - ASCII图表展示
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def print_banner():
    print("=" * 90)
    print("""
    ██████╗ ██████╗  █████╗ ██╗███╗   ██╗    ██╗   ██╗███████╗    ██████╗ ██████╗  █████╗ ██╗███╗   ██╗
    ██╔══██╗██╔══██╗██╔══██╗██║████╗  ██║    ██║   ██║██╔════╝    ██╔══██╗██╔══██╗██╔══██╗██║████╗  ██║
    ██████╔╝██████╔╝███████║██║██╔██╗ ██║    ██║   ██║███████╗    ██████╔╝██████╔╝███████║██║██╔██╗ ██║
    ██╔══██╗██╔══██╗██╔══██║██║██║╚██╗██║    ╚██╗ ██╔╝╚════██║    ██╔══██╗██╔══██╗██╔══██║██║██║╚██╗██║
    ██████╔╝██║  ██║██║  ██║██║██║ ╚████║     ╚████╔╝ ███████║    ██████╔╝██║  ██║██║  ██║██║██║ ╚████║
    ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝      ╚═══╝  ╚══════╝    ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝
    """)
    print("=" * 90)


def print_ascii_bar_chart():
    """打印ASCII条形图"""
    print("\n📊 收益率对比")
    print("-" * 90)
    
    strategies = [
        ('RSI', 0.74, -3.17),
        ('MACD', -8.14, -5.01),
        ('Bollinger', 2.02, -4.18),
        ('Dual MA', -2.19, -2.19),
        ('Donchian', 17.89, 15.93),
    ]
    
    print(f"{'策略':<12} {'Jarvis':<10} {'Brain':<10} {'差异':<10} {'可视化'}")
    print("-" * 90)
    
    for name, jarvis, brain in strategies:
        diff = brain - jarvis
        diff_str = f"{diff:+.2f}%"
        
        # ASCII条形
        jarvis_bar = "█" * int(abs(jarvis) / 2) if jarvis != 0 else ""
        brain_bar = "░" * int(abs(brain) / 2) if brain != 0 else ""
        
        if jarvis >= 0:
            jarvis_display = f"🟢 {jarvis:+.2f}%"
        else:
            jarvis_display = f"🔴 {jarvis:+.2f}%"
            
        if brain >= 0:
            brain_display = f"🟢 {brain:+.2f}%"
        else:
            brain_display = f"🔴 {brain:+.2f}%"
        
        print(f"{name:<12} {jarvis_display:<10} {brain_display:<10} {diff_str:<10} J:{jarvis_bar} B:{brain_bar}")
    
    print("-" * 90)
    print("图例: █=Jarvis  ░=Brain  🟢=盈利  🔴=亏损")


def print_signal_analysis():
    """打印信号分析"""
    print("\n📡 信号生成差异分析")
    print("-" * 90)
    
    analysis = [
        ('RSI', 79, 'Jarvis连续信号多', 'Jarvis: RSI<30每天买入; Brain: 只在上穿时买入'),
        ('MACD', 6, '差异小', '两者实现类似'),
        ('Bollinger', 230, '卖出逻辑不同', 'Jarvis: 中轨卖出; Brain: 上轨卖出'),
        ('Dual MA', 0, '完全一致', '实现方式相同'),
        ('Donchian', 38, '延迟确认差异', 'Jarvis提前1bar突破'),
    ]
    
    print(f"{'策略':<12} {'差异Bar':<10} {'主要原因':<20} {'详细说明'}")
    print("-" * 90)
    
    for strategy, diff, reason, detail in analysis:
        print(f"{strategy:<12} {diff:>8}   {reason:<20} {detail}")
    
    print("-" * 90)


def print_pros_cons():
    """打印优缺点对比"""
    print("\n⚖️  优缺点对比")
    print("-" * 90)
    
    print("\n┌" + "─" * 40 + "┬" + "─" * 45 + "┐")
    print("│" + " Jarvis 风格 ".center(40) + "│" + " Brain 风格 ".center(45) + "│")
    print("├" + "─" * 40 + "┼" + "─" * 45 + "┤")
    print("│ ✅ 回测收益虚高 (但不可信)          │ ✅ 回测收益保守 (更接近实盘)        │")
    print("│ ✅ 代码简单直观                    │ ✅ 信号可复用、可批量测试           │")
    print("│ ✅ 支持Backtesting.py生态          │ ✅ 内置A股规则 (T+1/涨跌停/100股)  │")
    print("│                                     │ ✅ 向量化计算，速度快50-100x        │")
    print("├" + "─" * 40 + "┼" + "─" * 45 + "┤")
    print("│ ❌ 有未来函数嫌疑 (当日执行)        │ ❌ 收益偏低 (延迟导致错过部分行情)  │")
    print("│ ❌ 可能重复交易 (连续信号)          │ ❌ 实现稍复杂 (需要理解shift)       │")
    print("│ ❌ 无A股规则支持                    │ ❌ 不支持做空 (A股规则限制)         │")
    print("│ ❌ 性能较差 (循环计算)              │                                     │")
    print("└" + "─" * 40 + "┴" + "─" * 45 + "┘")


def print_key_findings():
    """打印关键发现"""
    print("\n🔍 关键发现")
    print("-" * 90)
    
    findings = [
        ("1. 收益差异", "Brain平均比Jarvis低1.79%，但更可靠"),
        ("2. 最大差异策略", "Bollinger (-6.20%)，因卖出逻辑不同"),
        ("3. 信号差异最大", "Bollinger (230 bar)，Jarvis频繁卖出"),
        ("4. 最一致策略", "Dual MA (0 bar差异)"),
        ("5. 最佳策略", "Donchian: Jarvis +17.89% vs Brain +15.93%"),
        ("6. 回撤控制", "Brain回撤普遍更小 (Donchian -3.88% vs -5.72%)"),
        ("7. 交易频率", "Jarvis Bollinger卖出237次 vs Brain 16次"),
    ]
    
    for title, desc in findings:
        print(f"   📌 {title}: {desc}")


def print_recommendations():
    """打印建议"""
    print("\n💡 优化建议")
    print("-" * 90)
    
    print("\n给 Jarvis 的建议:")
    print("   1. 修复 Supertrend 的 close.class() Bug")
    print("   2. 添加信号延迟: signals.shift(1) 避免未来函数")
    print("   3. 避免连续信号: 只在状态改变时交易")
    print("   4. 使用向量化计算替代循环")
    print("   5. 添加A股规则支持")
    
    print("\n给 Brain 的建议:")
    print("   1. 可添加参数控制是否延迟执行 (灵活配置)")
    print("   2. 添加 Bollinger 中轨止盈选项")
    print("   3. 优化 RSI 参数，提高胜率")
    
    print("\n联合优化方向:")
    print("   1. 两者都添加参数优化功能 (网格搜索)")
    print("   2. 都支持多因子组合策略")
    print("   3. 都添加实时模拟交易功能")


def print_summary():
    """打印总结"""
    print("\n" + "=" * 90)
    print("📊 总结")
    print("=" * 90)
    
    print("""
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                                                                             │
    │  🏆 结论: Brain 策略库更适合实盘交易                                         │
    │                                                                             │
    │  虽然 Jarvis 风格回测收益更高 (+2.06% vs +0.27%)，但存在以下问题:            │
    │                                                                             │
    │  1. 可能使用未来信息 (当日执行)                                               │
    │  2. 频繁交易导致手续费侵蚀收益 (Bollinger 237次卖出)                          │
    │  3. 无A股规则支持，实盘无法直接应用                                           │
    │                                                                             │
    │  Brain 优势:                                                                 │
    │  1. ✅ 信号延迟，避免未来函数                                                 │
    │  2. ✅ 内置A股规则 (T+1/涨跌停/100股)                                        │
    │  3. ✅ 向量化计算，速度快50-100倍                                            │
    │  4. ✅ 回撤控制更好 (平均回撤 -6.36% vs -5.57%)                              │
    │                                                                             │
    │  建议: 实盘使用 Brain，研究可使用 Jarvis (但需理解其局限性)                   │
    │                                                                             │
    └─────────────────────────────────────────────────────────────────────────────┘
    """)


def main():
    print_banner()
    print_ascii_bar_chart()
    print_signal_analysis()
    print_pros_cons()
    print_key_findings()
    print_recommendations()
    print_summary()
    
    print("\n" + "=" * 90)
    print("📁 相关文件:")
    print("   • examples/compare_jarvis_brain.py      - 首次对比 (含Bug)")
    print("   • examples/accurate_comparison.py       - 修正对比 (推荐)")
    print("   • Jarvis对比优化报告.md                 - 详细文档")
    print("   • GitHub: https://github.com/AlexJCD2025/brain")
    print("=" * 90)


if __name__ == "__main__":
    main()
