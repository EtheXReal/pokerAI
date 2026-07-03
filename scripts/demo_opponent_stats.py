#!/usr/bin/env python
"""
OpponentStats 演示脚本

展示对手统计系统的实际工作流程：
1. 创建对手统计
2. 模拟多手牌数据
3. 实时更新统计
4. 分析对手类型
5. 展示序列化功能
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from advisor.modeling import (
    OpponentStats,
    create_opponent_stats,
    HandResult,
    ActionRecord,
    PlayerType,
    ActionType,
    StreetType,
    PositionType
)


def print_section(title: str):
    """打印章节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def simulate_fish_player():
    """模拟一个Fish玩家（松弱型）"""
    print_section("演示 1: 模拟 Fish 玩家 (松弱型)")

    stats = create_opponent_stats("Fish_Mike")
    print(f"\n初始状态:")
    print(stats)
    print(f"置信度: {stats.get_confidence():.0%}")

    print("\n模拟 50 手牌数据...")
    print("Fish 特征: 高VPIP (45%), 低PFR (8%), 很少弃牌")

    # 模拟50手牌
    for i in range(50):
        hand = HandResult(
            hand_id=f"h{i:03d}",
            position=PositionType.BTN if i % 2 == 0 else PositionType.BB,
            vpip=(i < 45),  # 45/50 = 90% → 但考虑有些不是自己决策，实际VPIP会低些
            pfr=(i < 4),    # 4/50 = 8% PFR
            saw_flop=(i < 40),
            went_to_showdown=(i < 25),  # 去摊牌很多
            won_at_showdown=(i < 10),   # 但赢得少
            cbet_flop=(i < 3) if (i < 4) else None,  # 很少c-bet
            fold_to_cbet=(i >= 4 and i < 10) if (i >= 4) else None,  # 对c-bet也很少弃牌
        )
        stats.update_from_hand(hand)

    print(f"\n50手后的统计:")
    print(stats.summary())

    return stats


def simulate_tag_player():
    """模拟一个TAG玩家（紧激进型）"""
    print_section("演示 2: 模拟 TAG 玩家 (紧激进型)")

    stats = create_opponent_stats("TAG_Sarah")
    print(f"\n初始状态:")
    print(stats)

    print("\n模拟 100 手牌数据...")
    print("TAG 特征: 中等VPIP (22%), 高PFR (18%), 高激进度")

    # 模拟100手牌
    for i in range(100):
        # TAG: 选择性入池，入池后激进
        vpip = (i < 22)
        pfr = (i < 18)

        actions = []
        if vpip and pfr:
            # 激进动作
            actions.append(ActionRecord(
                street=StreetType.PREFLOP,
                position=PositionType.BTN,
                action=ActionType.RAISE,
                amount=3.0,
                pot_size=1.5
            ))

        hand = HandResult(
            hand_id=f"h{i:03d}",
            position=PositionType.BTN if i % 3 == 0 else PositionType.CO,
            vpip=vpip,
            pfr=pfr,
            three_bet=(i < 8) and pfr,  # 8% 3-bet
            saw_flop=vpip,
            cbet_flop=(i < 15) if pfr else None,  # 高c-bet频率
            went_to_showdown=(i < 8) if vpip else False,  # 较少去摊牌
            won_at_showdown=(i < 6) if (i < 8) else False,  # 摊牌胜率高
            actions=actions
        )
        stats.update_from_hand(hand)

    print(f"\n100手后的统计:")
    print(stats.summary())

    return stats


def simulate_maniac_player():
    """模拟一个Maniac玩家（疯狂型）"""
    print_section("演示 3: 模拟 Maniac 玩家 (疯狂型)")

    stats = create_opponent_stats("Maniac_Tom")
    print(f"\n初始状态:")
    print(stats)

    print("\n模拟 80 手牌数据...")
    print("Maniac 特征: 极高VPIP (55%), 极高PFR (40%), 疯狂激进")

    # 模拟80手牌
    for i in range(80):
        vpip = (i < 55)
        pfr = (i < 40)

        # Maniac: 大量激进动作
        actions = []
        if vpip:
            actions.append(ActionRecord(
                street=StreetType.PREFLOP,
                position=PositionType.BTN,
                action=ActionType.RAISE,
                amount=4.0,
                pot_size=1.5
            ))
            if i % 2 == 0:  # 翻后也继续激进
                actions.append(ActionRecord(
                    street=StreetType.FLOP,
                    position=PositionType.BTN,
                    action=ActionType.BET,
                    amount=8.0,
                    pot_size=10.0
                ))

        hand = HandResult(
            hand_id=f"h{i:03d}",
            position=PositionType.BTN,
            vpip=vpip,
            pfr=pfr,
            three_bet=(i < 25) and pfr,  # 30%+ 3-bet!
            saw_flop=vpip,
            cbet_flop=(i < 35) if pfr else None,  # 极高c-bet
            went_to_showdown=(i < 20) if vpip else False,
            won_at_showdown=(i < 8) if (i < 20) else False,  # 摊牌经常输
            actions=actions
        )
        stats.update_from_hand(hand)

    print(f"\n80手后的统计:")
    print(stats.summary())

    return stats


def demo_player_comparison():
    """对比不同玩家类型"""
    print_section("演示 4: 玩家类型对比")

    # 创建三个不同类型的玩家
    fish = create_opponent_stats("Fish")
    tag = create_opponent_stats("TAG")
    maniac = create_opponent_stats("Maniac")

    # Fish: 45% VPIP, 8% PFR, AF 0.8
    fish.hands_played = 100
    fish.vpip = 0.45
    fish.pfr = 0.08
    fish.af = 0.8
    fish.three_bet_pct = 0.03
    fish.cbet_flop = 0.35
    fish.wtsd = 0.35
    fish.w_sd = 0.42

    # TAG: 22% VPIP, 18% PFR, AF 2.5
    tag.hands_played = 100
    tag.vpip = 0.22
    tag.pfr = 0.18
    tag.af = 2.5
    tag.three_bet_pct = 0.08
    tag.cbet_flop = 0.70
    tag.wtsd = 0.22
    tag.w_sd = 0.55

    # Maniac: 55% VPIP, 40% PFR, AF 4.2
    maniac.hands_played = 100
    maniac.vpip = 0.55
    maniac.pfr = 0.40
    maniac.af = 4.2
    maniac.three_bet_pct = 0.28
    maniac.cbet_flop = 0.85
    maniac.wtsd = 0.28
    maniac.w_sd = 0.38

    print("\n三种玩家类型对比:")
    print(f"\n{'指标':<20} {'Fish':<15} {'TAG':<15} {'Maniac':<15}")
    print("-" * 70)
    print(f"{'VPIP':<20} {fish.vpip:<15.1%} {tag.vpip:<15.1%} {maniac.vpip:<15.1%}")
    print(f"{'PFR':<20} {fish.pfr:<15.1%} {tag.pfr:<15.1%} {maniac.pfr:<15.1%}")
    print(f"{'激进度(AF)':<20} {fish.af:<15.1f} {tag.af:<15.1f} {maniac.af:<15.1f}")
    print(f"{'3-bet频率':<20} {fish.three_bet_pct:<15.1%} {tag.three_bet_pct:<15.1%} {maniac.three_bet_pct:<15.1%}")
    print(f"{'C-bet频率':<20} {fish.cbet_flop:<15.1%} {tag.cbet_flop:<15.1%} {maniac.cbet_flop:<15.1%}")
    print(f"{'摊牌率(WTSD)':<20} {fish.wtsd:<15.1%} {tag.wtsd:<15.1%} {maniac.wtsd:<15.1%}")
    print(f"{'摊牌胜率(W$SD)':<20} {fish.w_sd:<15.1%} {tag.w_sd:<15.1%} {maniac.w_sd:<15.1%}")
    print(f"{'置信度':<20} {fish.get_confidence():<15.0%} {tag.get_confidence():<15.0%} {maniac.get_confidence():<15.0%}")

    print("\n玩家特征分析:")
    print(f"• Fish:   松弱型 - 入池太多，激进度低，容易被价值下注")
    print(f"• TAG:    紧激进 - 选择性入池，入池后激进，难以对付")
    print(f"• Maniac: 疯狂型 - 几乎打所有牌，极度激进，但摊牌胜率低")


def demo_serialization():
    """演示序列化功能"""
    print_section("演示 5: 序列化和持久化")

    # 创建一个有数据的统计对象
    stats = create_opponent_stats("Player_001")
    stats.hands_played = 150
    stats.vpip = 0.28
    stats.pfr = 0.22
    stats.af = 2.3
    stats.three_bet_pct = 0.09
    stats.cbet_flop = 0.68
    stats.fold_to_cbet_flop = 0.45
    stats.wtsd = 0.24
    stats.w_sd = 0.52

    print("\n原始对象:")
    print(stats)

    # 转换为字典
    print("\n转换为字典 (用于数据库存储):")
    data_dict = stats.to_dict()
    print(f"Keys: {list(data_dict.keys())[:10]}...")  # 只显示前10个
    print(f"VPIP: {data_dict['vpip']}")
    print(f"PFR: {data_dict['pfr']}")
    print(f"AF: {data_dict['af']}")

    # 转换为JSON
    print("\nJSON格式 (前300字符):")
    json_str = stats.to_json()
    print(json_str[:300] + "...")

    # 从字典恢复
    print("\n从字典恢复对象:")
    restored_stats = OpponentStats.from_dict(data_dict)
    print(restored_stats)

    # 验证数据一致性
    print("\n验证数据一致性:")
    print(f"✓ VPIP 匹配: {restored_stats.vpip == stats.vpip}")
    print(f"✓ PFR 匹配: {restored_stats.pfr == stats.pfr}")
    print(f"✓ AF 匹配: {restored_stats.af == stats.af}")
    print(f"✓ 手数匹配: {restored_stats.hands_played == stats.hands_played}")


def demo_confidence_system():
    """演示置信度系统"""
    print_section("演示 6: 置信度系统")

    print("\n置信度随手数变化:")
    print(f"{'手数':<10} {'置信度':<10} {'说明':<30}")
    print("-" * 50)

    test_cases = [
        (10, "样本太少，不可靠"),
        (30, "初步印象"),
        (50, "较为可靠"),
        (100, "可靠"),
        (200, "高度可靠"),
        (500, "非常可靠"),
    ]

    for hands, description in test_cases:
        stats = create_opponent_stats("Test")
        stats.hands_played = hands
        confidence = stats.get_confidence()
        print(f"{hands:<10} {confidence:<10.0%} {description:<30}")

    print("\n建议:")
    print("• < 30手: 使用默认GTO策略，不要过度调整")
    print("• 30-50手: 可以开始识别明显的Fish或Maniac")
    print("• 50-100手: 可以根据统计做Exploitative调整")
    print("• > 100手: 统计非常可靠，可以大胆exploit")


def main():
    """主函数"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "OpponentStats 系统演示" + " " * 30 + "║")
    print("║" + " " * 15 + "Phase 2.2 - 对手建模引擎" + " " * 26 + "║")
    print("╚" + "═" * 68 + "╝")

    try:
        # 运行所有演示
        simulate_fish_player()
        input("\n按回车继续下一个演示...")

        simulate_tag_player()
        input("\n按回车继续下一个演示...")

        simulate_maniac_player()
        input("\n按回车继续下一个演示...")

        demo_player_comparison()
        input("\n按回车继续下一个演示...")

        demo_serialization()
        input("\n按回车继续下一个演示...")

        demo_confidence_system()

        # 总结
        print_section("总结")
        print("\nOpponentStats 核心功能:")
        print("✓ 20+ 统计指标自动追踪")
        print("✓ 增量更新，无需存储历史")
        print("✓ 置信度评分系统")
        print("✓ 完整的序列化支持")
        print("✓ 支持多种玩家类型识别")

        print("\n下一步:")
        print("→ Week 1 Day 3-4: 实现 tracker.py (统计追踪器)")
        print("→ Week 2: 实现 classifier.py (玩家分类器)")
        print("→ Week 3: 实现 exploits.py (Exploit策略库)")

        print("\n" + "=" * 70)
        print("演示完成！ 🎉")
        print("=" * 70 + "\n")

    except KeyboardInterrupt:
        print("\n\n演示被中断。")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
