#!/usr/bin/env python
"""
交互式范围引擎测试工具
允许手动输入场景，查看AI的范围分析和equity计算
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from advisor.range_engine import (
    Range, parse_range_dict, EquityCalculator, BoardTexture,
    get_open_range, get_3bet_range, merge_range_dicts
)
from treys import Card


def test_scenario_1():
    """
    场景 1: 翻前 - BTN open vs BB
    你在BB位置，拿到AKo，BTN开池2.5BB
    """
    print("=" * 60)
    print("场景 1: 翻前决策")
    print("=" * 60)
    print("位置: BB")
    print("手牌: AKo (红心A + 方块K)")
    print("行动: BTN open 2.5BB")
    print("问题: BB应该跟注还是3-bet？")
    print()

    # 1. 估计BTN开池范围
    btn_range = parse_range_dict(get_open_range('BTN', 'normal'))
    print(f"BTN开池范围 (normal): {btn_range.size()} combos (~46.8% VPIP)")

    # 2. BB的3-bet范围
    bb_3bet_dict = get_3bet_range('BB', 'BTN')
    bb_3bet = merge_range_dicts(bb_3bet_dict['value'], bb_3bet_dict['bluff'])
    print(f"BB 3-bet范围: {bb_3bet.size()} combos")
    print(f"  - Value: {parse_range_dict(bb_3bet_dict['value']).size()} combos")
    print(f"  - Bluff: {parse_range_dict(bb_3bet_dict['bluff']).size()} combos")

    # 3. AKo vs BTN范围的equity
    hero_hand = [Card.new('Ah'), Card.new('Kd')]
    calc = EquityCalculator()

    equity_vs_btn = calc.hand_vs_range(hero_hand, btn_range, [], nsamples=1000)
    print(f"\nAKo vs BTN开池范围 equity: {equity_vs_btn:.1%}")

    # 4. 建议
    print("\n💡 AI建议:")
    if equity_vs_btn > 0.60:
        print("✅ 3-bet！AKo在BB vs BTN有明显优势")
    elif equity_vs_btn > 0.52:
        print("✅ 3-bet或跟注都可以，倾向3-bet")
    else:
        print("⚠️  跟注观察翻后")

    print()


def test_scenario_2():
    """
    场景 2: 翻牌圈 - 干燥高牌面
    """
    print("=" * 60)
    print("场景 2: 翻牌圈 C-bet决策")
    print("=" * 60)
    print("手牌: AKo (红心A + 方块K)")
    print("翻牌: Ah 7h 2d")
    print("情况: 你翻前在BTN open，BB跟注，现在BB check")
    print("底池: 6BB")
    print("问题: 是否C-bet？下注多少？")
    print()

    # 1. 分析牌面
    board = [Card.new('Ah'), Card.new('7h'), Card.new('2d')]
    texture = BoardTexture(board)

    print(f"牌面分析:")
    print(f"  - 湿度: {texture.wetness}")
    print(f"  - 连接性: {texture.connectivity}")
    print(f"  - 同花听牌: {texture.flush_draw_possible}")
    print(f"  - 顺子听牌: {texture.straight_draw_possible}")
    print(f"  - 有利于: {texture.favors_caller_or_raiser()}")

    # 2. 建议的C-bet尺寸
    pot = 6
    suggested_size = texture.suggested_cbet_size(pot)
    print(f"\n建议C-bet尺寸: {suggested_size * pot:.1f}BB ({suggested_size:.0%} pot)")

    # 3. 手牌强度
    hero_hand = [Card.new('Ah'), Card.new('Kd')]
    calc = EquityCalculator()

    # 假设BB跟注范围较宽
    bb_call_range = Range("22+,A2s+,K5s+,Q7s+,J7s+,T7s+,97s+,87s,76s,A5o+,K8o+,Q9o+,J9o+,T9o")
    bb_call_range.remove_dead_cards(["Ah", "Kd", "Ah", "7h", "2d"])

    equity = calc.hand_vs_range(hero_hand, bb_call_range, board, nsamples=500)
    print(f"\nAKo (top pair top kicker) vs BB跟注范围: {equity:.1%}")

    # 4. 建议
    print("\n💡 AI建议:")
    print(f"✅ C-bet {suggested_size * pot:.1f}BB")
    print(f"   理由: 干燥面 + TPTK + 高equity → 小注保护 + 价值下注")
    print()


def test_scenario_3():
    """
    场景 3: 翻牌圈 - 湿润连接面
    """
    print("=" * 60)
    print("场景 3: 翻牌圈 湿润面决策")
    print("=" * 60)
    print("手牌: QQ (黑桃Q + 红心Q)")
    print("翻牌: Ts 9s 8h")
    print("情况: 你翻前在CO open，BTN跟注，现在你先行动")
    print("底池: 7BB")
    print("问题: 是否C-bet？")
    print()

    # 1. 分析牌面
    board = [Card.new('Ts'), Card.new('9s'), Card.new('8h')]
    texture = BoardTexture(board)

    print(f"牌面分析:")
    print(f"  - 湿度: {texture.wetness} ⚠️  非常湿润")
    print(f"  - 连接性: {texture.connectivity}")
    print(f"  - 同花听牌: {texture.flush_draw_possible} ✓")
    print(f"  - 顺子听牌: {texture.straight_draw_possible} ✓")
    print(f"  - 有利于: {texture.favors_caller_or_raiser()}")

    # 2. 手牌强度
    hero_hand = [Card.new('Qs'), Card.new('Qh')]
    calc = EquityCalculator()

    # BTN跟注范围
    btn_call_range = Range("22+,A2s+,K6s+,Q7s+,J7s+,T7s+,97s+,86s+,76s,65s,A7o+,K8o+,Q9o+,J9o+,T9o,98o")
    btn_call_range.remove_dead_cards(["Qs", "Qh", "Ts", "9s", "8h"])

    equity = calc.hand_vs_range(hero_hand, btn_call_range, board, nsamples=500)
    print(f"\nQQ (overpair) vs BTN跟注范围: {equity:.1%}")

    # 3. 建议的C-bet尺寸
    pot = 7
    suggested_size = texture.suggested_cbet_size(pot)
    print(f"\n建议C-bet尺寸: {suggested_size * pot:.1f}BB ({suggested_size:.0%} pot)")

    # 4. 建议
    print("\n💡 AI建议:")
    print(f"✅ C-bet {suggested_size * pot:.1f}BB (大注)")
    print(f"   理由: 湿润面 + 很多听牌 → 大注保护，不给对手好价格")
    print(f"   风险: 对手可能有顺子/两对，如果遇到加注需谨慎")
    print()


def test_scenario_4():
    """
    场景 4: 多人底池
    """
    print("=" * 60)
    print("场景 4: 多人底池 equity 计算")
    print("=" * 60)
    print("手牌: AA (黑桃A + 红心A)")
    print("情况: 翻前你在UTG open，MP和CO都跟注 (3人底池)")
    print("问题: AA在多人底池的equity是多少？")
    print()

    hero_hand = [Card.new('As'), Card.new('Ah')]

    # 估计两个对手的范围
    mp_call_range = Range("55+,A9s+,KTs+,QTs+,JTs,ATo+,KJo+")
    co_call_range = Range("44+,A7s+,K9s+,Q9s+,J9s+,T9s,98s,A9o+,KTo+,QJo")

    print(f"MP跟注范围: {mp_call_range.size()} combos")
    print(f"CO跟注范围: {co_call_range.size()} combos")

    # 计算多人equity
    calc = EquityCalculator()
    equity_3way = calc.multiway_equity(hero_hand, [mp_call_range, co_call_range], [], nsamples=500)

    # 对比单挑equity
    equity_hu = calc.hand_vs_range(hero_hand, mp_call_range, [], nsamples=500)

    print(f"\nAA vs MP (单挑): {equity_hu:.1%}")
    print(f"AA vs MP + CO (3人): {equity_3way:.1%}")
    print(f"Equity下降: {equity_hu - equity_3way:.1%}")

    print("\n💡 重要启示:")
    print("✅ 多人底池中，即使AA这样的强牌equity也会显著下降")
    print("✅ 3人底池需要更保守，不能过度激进")
    print()


def interactive_mode():
    """交互式测试模式"""
    print("\n" + "=" * 60)
    print("交互式范围测试")
    print("=" * 60)
    print("输入你自己的场景进行测试\n")

    # 1. 输入手牌
    print("输入你的手牌 (例如: As Kd):")
    try:
        hand_input = input("> ").strip().split()
        if len(hand_input) != 2:
            print("❌ 格式错误")
            return

        hero_hand = [Card.new(hand_input[0]), Card.new(hand_input[1])]
        print(f"✅ 手牌: {Card.int_to_str(hero_hand[0])} {Card.int_to_str(hero_hand[1])}")
    except:
        print("❌ 无效的牌面")
        return

    # 2. 输入对手范围
    print("\n输入对手范围 (例如: AA,KK,QQ,AKs 或者使用预设范围如 BTN_normal):")
    range_input = input("> ").strip()

    if range_input.upper() == "BTN_NORMAL":
        villain_range = parse_range_dict(get_open_range('BTN', 'normal'))
        print(f"✅ 使用BTN normal开池范围: {villain_range.size()} combos")
    elif range_input.upper() == "UTG_NORMAL":
        villain_range = parse_range_dict(get_open_range('UTG', 'normal'))
        print(f"✅ 使用UTG normal开池范围: {villain_range.size()} combos")
    else:
        try:
            villain_range = Range(range_input)
            print(f"✅ 对手范围: {villain_range.size()} combos")
        except:
            print("❌ 范围格式错误")
            return

    # 3. 输入公共牌
    print("\n输入公共牌 (例如: Ah Ts 3c, 或者直接回车表示翻前):")
    board_input = input("> ").strip()

    if board_input:
        try:
            board_cards = board_input.split()
            board = [Card.new(c) for c in board_cards]
            board_str = ' '.join([Card.int_to_str(c) for c in board])
            print(f"✅ 公共牌: {board_str}")

            # 分析牌面
            texture = BoardTexture(board)
            print(f"\n牌面分析:")
            print(f"  湿度: {texture.wetness}")
            print(f"  有利于: {texture.favors_caller_or_raiser()}")
        except:
            print("❌ 公共牌格式错误")
            return
    else:
        board = []
        print("✅ 翻前场景")

    # 4. 计算equity
    print("\n⏳ 计算equity中...")
    calc = EquityCalculator()
    equity = calc.hand_vs_range(hero_hand, villain_range, board, nsamples=1000)

    print(f"\n📊 结果:")
    print(f"Equity: {equity:.1%}")

    if equity > 0.65:
        print("💪 强势领先！")
    elif equity > 0.55:
        print("👍 稍微领先")
    elif equity > 0.45:
        print("🤝 接近对半")
    else:
        print("⚠️  处于劣势")
    print()


def main():
    """主菜单"""
    print("\n" + "=" * 60)
    print("Range Engine 交互式测试工具")
    print("=" * 60)
    print("\n选择测试场景:")
    print("1. 场景1: 翻前BTN open vs BB (AKo决策)")
    print("2. 场景2: 翻牌圈干燥面C-bet (Ah7h2d)")
    print("3. 场景3: 翻牌圈湿润面决策 (Ts9s8h)")
    print("4. 场景4: 多人底池equity计算")
    print("5. 自定义场景 (交互式)")
    print("0. 全部运行")
    print()

    choice = input("请选择 (0-5): ").strip()

    if choice == '1':
        test_scenario_1()
    elif choice == '2':
        test_scenario_2()
    elif choice == '3':
        test_scenario_3()
    elif choice == '4':
        test_scenario_4()
    elif choice == '5':
        interactive_mode()
    elif choice == '0':
        test_scenario_1()
        test_scenario_2()
        test_scenario_3()
        test_scenario_4()
    else:
        print("❌ 无效选择")


if __name__ == '__main__':
    main()
