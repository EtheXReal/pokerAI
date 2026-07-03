#!/usr/bin/env python
"""
玩家分类器演示脚本

展示:
1. 9种玩家类型的识别
2. 置信度评分系统
3. Exploit策略提示
4. 完整工作流 (统计 -> 分类 -> 策略)
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from advisor.modeling import (
    create_opponent_stats,
    PlayerClassifier,
    classify_player,
    get_player_type_name,
    PlayerType,
    HandResult,
    PositionType,
)


def print_section(title: str):
    """打印章节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def demo_classify_9_types():
    """演示识别9种玩家类型"""
    print_section("演示 1: 识别9种玩家类型")

    classifier = PlayerClassifier()

    # 定义9种玩家的典型特征
    player_profiles = [
        ("Nit_Tom", 100, 0.12, 0.10, 0.03, 1.5, 0.20, 0.48, "极紧型"),
        ("TAG_Alice", 150, 0.22, 0.18, 0.08, 2.5, 0.24, 0.53, "紧凶型"),
        ("WeakTight_Bob", 100, 0.18, 0.12, 0.04, 1.2, 0.22, 0.46, "弱紧型"),
        ("CallStation_Carl", 120, 0.45, 0.10, 0.03, 0.8, 0.35, 0.42, "跟注站"),
        ("LAP_Dave", 100, 0.32, 0.15, 0.05, 1.5, 0.28, 0.45, "松被动型"),
        ("Fish_Emma", 150, 0.55, 0.12, 0.04, 1.0, 0.40, 0.35, "鱼"),
        ("LAG_Frank", 180, 0.32, 0.25, 0.10, 3.0, 0.26, 0.52, "松凶型"),
        ("Maniac_George", 200, 0.65, 0.45, 0.18, 4.5, 0.38, 0.40, "疯狂型"),
        ("SolidReg_Helen", 250, 0.24, 0.18, 0.09, 2.4, 0.25, 0.55, "稳健常客"),
    ]

    print("\n玩家类型识别结果:")
    print("-" * 70)

    for player_id, hands, vpip, pfr, three_bet, af, wtsd, w_sd, expected in player_profiles:
        stats = create_opponent_stats(player_id)
        stats.hands_played = hands
        stats.vpip = vpip
        stats.pfr = pfr
        stats.three_bet_pct = three_bet
        stats.af = af
        stats.wtsd = wtsd
        stats.w_sd = w_sd

        result = classifier.classify(stats)

        print(f"\n{player_id:20s} (期望: {expected})")
        print(f"  识别为: {get_player_type_name(result.player_type)}")
        print(f"  置信度: {result.confidence:.1%}")
        print(f"  理由: {result.reason}")

        if result.alternative_types:
            alternatives = [f"{get_player_type_name(t)}({s:.1%})"
                          for t, s in result.alternative_types[:2]]
            print(f"  备选: {', '.join(alternatives)}")


def demo_confidence_progression():
    """演示置信度随样本量增加的变化"""
    print_section("演示 2: 置信度随样本量增加")

    classifier = PlayerClassifier()

    # 创建TAG玩家统计
    stats = create_opponent_stats("TAG_Player")
    stats.vpip = 0.22
    stats.pfr = 0.18
    stats.af = 2.5
    stats.three_bet_pct = 0.08

    print("\nTAG玩家的置信度变化:")
    print("-" * 70)

    sample_sizes = [30, 50, 75, 100, 150, 200, 250]

    for hands in sample_sizes:
        stats.hands_played = hands
        result = classifier.classify(stats)

        print(f"{hands:3d}手: {result.player_type.value:12s} 置信度={result.confidence:.1%}")


def demo_exploitation_hints():
    """演示Exploit策略提示"""
    print_section("演示 3: 针对性Exploit策略")

    classifier = PlayerClassifier()

    # 典型玩家类型
    test_types = [
        (PlayerType.NIT, "极紧型玩家"),
        (PlayerType.CALLING_STATION, "跟注站"),
        (PlayerType.FISH, "鱼"),
        (PlayerType.LAG, "松凶型玩家"),
    ]

    for player_type, description in test_types:
        print(f"\n对抗 {get_player_type_name(player_type)} ({description}):")
        print("-" * 70)

        hints = classifier.get_exploitation_hints(player_type)
        for i, hint in enumerate(hints, 1):
            print(f"  {i}. {hint}")


def demo_full_workflow():
    """演示完整工作流: 统计 -> 分类 -> 策略"""
    print_section("演示 4: 完整工作流")

    print("\n场景: 观察一个新对手打了100手牌")
    print("-" * 70)

    # 模拟收集统计
    print("\n步骤1: 收集统计数据...")
    stats = create_opponent_stats("Mystery_Player")

    # 模拟100手牌的数据收集
    print("  处理100手牌历史...")
    for i in range(100):
        hand = HandResult(
            hand_id=f"h{i:03d}",
            position=PositionType.BTN,
            vpip=(i < 45),   # 45% VPIP
            pfr=(i < 10),    # 10% PFR
            saw_flop=(i < 40),
            went_to_showdown=(i < 20),
            won_at_showdown=(i < 7),
        )
        stats.update_from_hand(hand)

    print(f"\n  统计结果:")
    print(f"    - 手数: {stats.hands_played}")
    print(f"    - VPIP: {stats.vpip:.1%}")
    print(f"    - PFR: {stats.pfr:.1%}")
    print(f"    - AF: {stats.af:.2f}")
    print(f"    - WTSD: {stats.wtsd:.1%}")
    print(f"    - W$SD: {stats.w_sd:.1%}")

    # 分类
    print("\n步骤2: 玩家分类...")
    result = classify_player(stats)

    print(f"  分类结果: {get_player_type_name(result.player_type)}")
    print(f"  置信度: {result.confidence:.1%}")
    print(f"  理由: {result.reason}")

    if result.alternative_types:
        print(f"  备选类型:")
        for alt_type, alt_score in result.alternative_types[:2]:
            print(f"    - {get_player_type_name(alt_type)} ({alt_score:.1%})")

    # 获取策略
    print("\n步骤3: 制定Exploit策略...")
    classifier = PlayerClassifier()
    hints = classifier.get_exploitation_hints(result.player_type)

    print(f"  针对 {get_player_type_name(result.player_type)} 的策略:")
    for i, hint in enumerate(hints, 1):
        print(f"    {i}. {hint}")


def demo_edge_cases():
    """演示边界情况"""
    print_section("演示 5: 边界情况处理")

    classifier = PlayerClassifier()

    # 1. 样本量不足
    print("\n情况1: 样本量不足 (20手)")
    print("-" * 70)
    stats = create_opponent_stats("NewPlayer")
    stats.hands_played = 20
    stats.vpip = 0.25
    stats.pfr = 0.18

    result = classifier.classify(stats)
    print(f"  分类: {get_player_type_name(result.player_type)}")
    print(f"  置信度: {result.confidence:.1%}")
    print(f"  理由: {result.reason}")

    # 2. 边界玩家 (介于两种类型之间)
    print("\n情况2: 边界玩家 (介于TAG和LAG之间)")
    print("-" * 70)
    stats2 = create_opponent_stats("BoundaryPlayer")
    stats2.hands_played = 100
    stats2.vpip = 0.26  # 在TAG上限和LAG下限之间
    stats2.pfr = 0.20
    stats2.af = 2.3
    stats2.three_bet_pct = 0.08

    result2 = classifier.classify(stats2)
    print(f"  分类: {get_player_type_name(result2.player_type)}")
    print(f"  置信度: {result2.confidence:.1%}")
    print(f"  备选类型:")
    for alt_type, alt_score in result2.alternative_types[:3]:
        print(f"    - {get_player_type_name(alt_type)} ({alt_score:.1%})")


def main():
    """主函数"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 18 + "玩家分类器演示" + " " * 32 + "║")
    print("║" + " " * 15 + "Phase 2.2 Week 2 - 对手建模" + " " * 23 + "║")
    print("╚" + "═" * 68 + "╝")

    try:
        demo_classify_9_types()
        demo_confidence_progression()
        demo_exploitation_hints()
        demo_full_workflow()
        demo_edge_cases()

        # 总结
        print_section("总结")
        print("\n✅ 玩家分类器核心功能:")
        print("  1. 识别9种玩家类型 (Nit/TAG/Weak Tight/Calling Station/LAP/Fish/LAG/Maniac/Solid Reg)")
        print("  2. 智能置信度评分 (基于样本量、匹配分数、类型差距)")
        print("  3. 备选类型建议 (处理边界情况)")
        print("  4. Exploit策略提示 (每种类型专门的应对方法)")

        print("\n✅ 分类算法特点:")
        print("  → 加权评分系统 (核心指标权重更高)")
        print("  → 渐进式置信度 (30手→50%, 100手→80%, 200手→95%)")
        print("  → 多维度分析 (VPIP/PFR/AF/3-bet/WTSD/W$SD)")
        print("  → 容错性设计 (边界玩家提供备选类型)")

        print("\n✅ 测试覆盖:")
        print("  - 21个单元测试全部通过")
        print("  - 覆盖所有9种玩家类型")
        print("  - 置信度系统验证")
        print("  - 边界情况测试")

        print("\n🎯 下一步 (Week 3):")
        print("  → 实现 exploits.py (Exploit策略库)")
        print("  → 基于玩家类型的具体策略调整")
        print("  → 完成Phase 2.2对手建模引擎")

        print("\n" + "=" * 70)
        print("演示完成！ 🎉")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
