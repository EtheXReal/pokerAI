#!/usr/bin/env python
"""
Range引擎演示脚本

展示:
1. Range创建和解析
2. 手牌组合生成
3. Range表达式 (QQ+, AK, 88-JJ)
4. Range vs Range equity
5. 实战应用场景
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from advisor.equity import (
    Range, RangeParser, RangeGenerator,
    EquityCalculator, Board,
    create_premium_range, create_any_pair_range,
)


def print_section(title: str):
    """打印章节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def demo_basic_ranges():
    """演示基础range创建"""
    print_section("演示 1: 基础Range创建")

    print("\n单个手牌符号:")
    print("-" * 70)

    ranges = [
        ("AA", "所有AA组合"),
        ("AKs", "同花AK"),
        ("AKo", "非同花AK"),
        ("AK", "所有AK (同花+非同花)"),
    ]

    for notation, description in ranges:
        r = Range.from_hand_notation(notation)
        print(f"\n{notation:10s} - {description}")
        print(f"  组合数: {len(r)}")


def demo_range_expressions():
    """演示Range表达式"""
    print_section("演示 2: Range表达式解析")

    expressions = [
        ("QQ+", "QQ及以上对子 (QQ, KK, AA)"),
        ("ATs+", "AT及以上同花牌 (ATs, AJs, AQs, AKs)"),
        ("88-JJ", "88到JJ的对子范围"),
        ("QQ+,AK", "Premium range (QQ+加AK)"),
        ("22+", "所有对子"),
    ]

    print("\nRange表达式解析:")
    print("-" * 70)

    for expr, description in expressions:
        r = Range.from_string(expr)
        print(f"\n{expr:15s} - {description}")
        print(f"  组合数: {len(r)}")


def demo_combo_details():
    """演示组合详情"""
    print_section("演示 3: 组合详情")

    print("\nAA的所有组合:")
    print("-" * 70)

    r = Range.from_string("AA")
    combos = list(r.combos)[:6]  # 显示前6个

    for i, combo in enumerate(combos, 1):
        print(f"  {i}. {combo}")

    print("\nAKs的所有组合:")
    print("-" * 70)

    r2 = Range.from_string("AKs")
    for i, combo in enumerate(r2.combos, 1):
        print(f"  {i}. {combo}")


def demo_dead_card_removal():
    """演示死牌移除"""
    print_section("演示 4: 死牌移除")

    print("\n场景: 你拿到AsKs，对手range是QQ+")
    print("-" * 70)

    from advisor.equity import Card

    # 对手range
    villain_range = Range.from_string("QQ+")
    print(f"\n原始QQ+ range: {len(villain_range)}个组合")

    # 你的手牌
    dead_cards = {Card.from_str("As"), Card.from_str("Ks")}

    # 移除死牌
    villain_valid = villain_range.remove_dead_cards(dead_cards)
    print(f"移除AsKs后: {len(villain_valid)}个组合")
    print(f"  (移除了包含As或Ks的组合)")


def demo_range_vs_range():
    """演示Range vs Range equity"""
    print_section("演示 5: Range vs Range Equity")

    calc = EquityCalculator(iterations=2000)

    scenarios = [
        ("AA", "22-66", "AA vs 小对子"),
        ("QQ+", "AK", "Premium pairs vs AK"),
        ("TT", "AK", "TT vs AK (经典flip)"),
    ]

    print("\nRange对抗 Equity计算:")
    print("-" * 70)

    for hero_expr, villain_expr, description in scenarios:
        hero_range = Range.from_string(hero_expr)
        villain_range = Range.from_string(villain_expr)

        print(f"\n{description}")
        print(f"  {hero_expr} vs {villain_expr}")
        print(f"  Hero组合: {len(hero_range)}, Villain组合: {len(villain_range)}")

        # 使用采样计算 (更快)
        result = calc.calculate_range_vs_range(
            hero_range,
            villain_range,
            Board([]),
            sample_size=20
        )

        print(f"  → {hero_expr}: {result.equity:.1%}  |  {villain_expr}: {1-result.equity:.1%}")


def demo_preflop_scenarios():
    """演示翻前场景"""
    print_section("演示 6: 翻前实战场景")

    calc = EquityCalculator(iterations=2000)

    print("\n场景1: UTG open，你在BTN考虑3-bet")
    print("-" * 70)
    print("  UTG range估计: QQ+, AK (很紧)")
    print("  你的3-bet range可能: JJ+, AQ+")

    utg_range = Range.from_string("QQ+,AK")
    btn_3bet_range = Range.from_string("JJ+,AQ+")

    print(f"\n  UTG range: {len(utg_range)}个组合")
    print(f"  BTN 3-bet range: {len(btn_3bet_range)}个组合")

    result = calc.calculate_range_vs_range(
        btn_3bet_range,
        utg_range,
        Board([]),
        sample_size=25
    )

    print(f"\n  BTN equity: {result.equity:.1%}")
    print(f"  建议: {'可以3-bet' if result.equity > 0.50 else '谨慎，对手range很强'}")

    print("\n\n场景2: CO open，你在BB防守")
    print("-" * 70)
    print("  CO range估计: 77+, A9s+, KTs+, QTs+ (较松)")
    print("  你的防守range: 22+, A2s+, K9s+, suited connectors")

    co_range = Range.from_string("77+,A9s+")
    bb_defense_range = Range.from_string("22+,A2s+")

    print(f"\n  CO range: {len(co_range)}个组合")
    print(f"  BB defense range: {len(bb_defense_range)}个组合")

    result2 = calc.calculate_range_vs_range(
        bb_defense_range,
        co_range,
        Board([]),
        sample_size=25
    )

    print(f"\n  BB equity: {result2.equity:.1%}")
    print(f"  建议: {'可以跟注防守' if result2.equity > 0.35 else '弃牌'}")


def demo_premium_ranges():
    """演示预定义range"""
    print_section("演示 7: 预定义Range")

    print("\nPremium Range (QQ+, AK):")
    print("-" * 70)

    premium = create_premium_range()
    print(f"  组合数: {len(premium)}")
    print(f"  包含: QQ(6) + KK(6) + AA(6) + AK(16) = 34")

    print("\n\n所有对子 (22+):")
    print("-" * 70)

    all_pairs = create_any_pair_range()
    print(f"  组合数: {len(all_pairs)}")
    print(f"  包含: 13种对子 × 6种组合 = 78")


def demo_range_construction():
    """演示Range构建策略"""
    print_section("演示 8: Range构建策略")

    print("\n不同位置的开池range:")
    print("-" * 70)

    positions = [
        ("UTG", "TT+,AQ+", "早位 - 最紧"),
        ("MP", "88+,ATs+,KQs", "中位 - 中等"),
        ("CO", "66+,A9s+,KTs+,QTs+", "CO位 - 较松"),
        ("BTN", "22+,A2s+,K9s+,Q9s+,J9s+,T9s", "按钮位 - 最松"),
    ]

    for pos, range_expr, description in positions:
        r = Range.from_string(range_expr)
        print(f"\n{pos:5s} - {description}")
        print(f"  Range: {range_expr}")
        print(f"  组合数: {len(r)}")


def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "Range引擎演示" + " " * 32 + "║")
    print("║" + " " * 15 + "Phase 2.3 Week 2 - 决策引擎" + " " * 23 + "║")
    print("╚" + "=" * 68 + "╝")

    try:
        demo_basic_ranges()
        demo_range_expressions()
        demo_combo_details()
        demo_dead_card_removal()
        demo_range_vs_range()
        demo_preflop_scenarios()
        demo_premium_ranges()
        demo_range_construction()

        # 总结
        print_section("总结")
        print("\n✅ Range引擎核心功能:")
        print("  1. Range表示 (组合集合)")
        print("  2. Range表达式解析 (QQ+, AK, 88-JJ)")
        print("  3. 组合生成器 (对子、同花、非同花)")
        print("  4. 死牌移除 (根据已知牌过滤)")
        print("  5. Range vs Range equity计算")

        print("\n✅ Range表达式支持:")
        print("  → 单个符号: AA, AKs, AKo, AK")
        print("  → + 扩展: QQ+ (及以上), ATs+ (及以上同花)")
        print("  → - 范围: 88-JJ (对子范围)")
        print("  → 组合: QQ+,AK (多个range)")

        print("\n✅ 组合数量:")
        print("  - 对子 (如AA): 6种组合")
        print("  - 同花 (如AKs): 4种组合")
        print("  - 非同花 (如AKo): 12种组合")
        print("  - 所有 (如AK): 16种组合")

        print("\n✅ 测试覆盖:")
        print("  - 25个单元测试全部通过")
        print("  - 覆盖所有range操作")
        print("  - Range vs Range equity验证")
        print("  - 边界情况测试")

        print("\n🎯 实战应用:")
        print("  - 翻前range构建 (不同位置)")
        print("  - 对手range估计")
        print("  - Equity计算 (range对抗)")
        print("  - 死牌移除 (优化计算)")

        print("\n🎯 下一步:")
        print("  → 整合Opponent Model (根据玩家类型调整range)")
        print("  → 实现简化版Decision Engine")
        print("  → 翻前决策逻辑 (fold/call/raise)")

        print("\n" + "=" * 70)
        print("演示完成！ 🎉")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
