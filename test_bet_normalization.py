#!/usr/bin/env python
"""
测试bet/raise金额规范化到0.5BB整数倍

验证：
1. Bet 1.32BB -> 1.5BB
2. Bet 9.35BB -> 9.5BB
3. Raise to 19.97BB -> 20.0BB
4. Raise to 32.88BB -> 33.0BB
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState


class BetTestPlayer(Player):
    """测试用玩家 - 返回指定的bet/raise金额"""

    def __init__(self, name: str, seat: int, stack: float, actions=None):
        super().__init__(name, seat, stack)
        self.actions = actions or []
        self.action_index = 0

    def decide(self, game_state: GameState) -> PlayerAction:
        if self.action_index < len(self.actions):
            action = self.actions[self.action_index]
            self.action_index += 1
            return action

        # 默认fold
        return PlayerAction('fold', 0.0)


def test_bet_normalization():
    """测试bet金额规范化"""
    print("="*80)
    print("测试：Bet金额规范化")
    print("="*80)

    # SB试图bet 1.32BB（应该被规范化为1.5BB）
    p1 = BetTestPlayer("SB", 0, 100.0, [
        PlayerAction('call', 0.0),    # Preflop: call
        PlayerAction('bet', 1.32),    # Flop: bet 1.32BB -> 应该变成1.5BB
    ])
    p2 = BetTestPlayer("BB", 1, 100.0, [
        PlayerAction('check', 0.0),   # Preflop: check
        PlayerAction('fold', 0.0),    # Flop: fold
    ])

    config = GameConfig(num_players=2, starting_stack=100.0, verbose=True)
    game = PokerGame([p1, p2], config)

    result = game.play_hand(hand_num=0, btn_seat=0, seed=42)

    # 验证bet金额
    bet_actions = [a for a in result.actions if 'bet' in a.action and a.street == 'flop']
    print(f"\n验证结果：")
    if len(bet_actions) > 0:
        bet_action = bet_actions[0]
        print(f"  原始请求: bet 1.32BB")
        print(f"  实际执行: {bet_action.action}")
        print(f"  实际金额: {bet_action.amount:.2f}BB")

        # 应该是1.0BB（1.32四舍五入到最近的整数BB）
        expected = 1.0
        if abs(bet_action.amount - expected) < 0.01:
            print(f"  ✅ 金额正确规范化为 {expected:.1f}BB")
        else:
            print(f"  ❌ 金额错误：期望{expected:.1f}BB，实际{bet_action.amount:.2f}BB")
    else:
        print("  ❌ 未找到bet动作")


def test_bet_normalization_2():
    """测试bet 9.35BB规范化"""
    print("\n" + "="*80)
    print("测试：Bet 9.35BB规范化")
    print("="*80)

    # SB试图bet 9.35BB（应该被规范化为9.5BB）
    p1 = BetTestPlayer("SB", 0, 100.0, [
        PlayerAction('call', 0.0),    # Preflop: call
        PlayerAction('bet', 9.35),    # Flop: bet 9.35BB -> 应该变成9.5BB
    ])
    p2 = BetTestPlayer("BB", 1, 100.0, [
        PlayerAction('check', 0.0),   # Preflop: check
        PlayerAction('fold', 0.0),    # Flop: fold
    ])

    config = GameConfig(num_players=2, starting_stack=100.0, verbose=True)
    game = PokerGame([p1, p2], config)

    result = game.play_hand(hand_num=0, btn_seat=0, seed=43)

    # 验证bet金额
    bet_actions = [a for a in result.actions if 'bet' in a.action and a.street == 'flop']
    print(f"\n验证结果：")
    if len(bet_actions) > 0:
        bet_action = bet_actions[0]
        print(f"  原始请求: bet 9.35BB")
        print(f"  实际执行: {bet_action.action}")
        print(f"  实际金额: {bet_action.amount:.2f}BB")

        expected = 9.0
        if abs(bet_action.amount - expected) < 0.01:
            print(f"  ✅ 金额正确规范化为 {expected:.1f}BB")
        else:
            print(f"  ❌ 金额错误：期望{expected:.1f}BB，实际{bet_action.amount:.2f}BB")
    else:
        print("  ❌ 未找到bet动作")


def test_raise_normalization():
    """测试raise金额规范化"""
    print("\n" + "="*80)
    print("测试：Raise金额规范化")
    print("="*80)

    # SB bet 2BB, BB试图raise 3.97BB（总共raise to 5.97BB -> 应该变成6.0BB）
    p1 = BetTestPlayer("SB", 0, 100.0, [
        PlayerAction('call', 0.0),    # Preflop: call
        PlayerAction('bet', 2.0),     # Flop: bet 2BB
        PlayerAction('fold', 0.0),    # Flop: fold after raise
    ])
    p2 = BetTestPlayer("BB", 1, 100.0, [
        PlayerAction('check', 0.0),   # Preflop: check
        PlayerAction('raise', 3.97),  # Flop: raise 3.97BB -> 应该变成4.0BB
    ])

    config = GameConfig(num_players=2, starting_stack=100.0, verbose=True)
    game = PokerGame([p1, p2], config)

    result = game.play_hand(hand_num=0, btn_seat=0, seed=44)

    # 验证raise金额
    raise_actions = [a for a in result.actions if 'raise' in a.action and a.street == 'flop']
    print(f"\n验证结果：")
    if len(raise_actions) > 0:
        raise_action = raise_actions[0]
        print(f"  实际执行: {raise_action.action}")

        # 从action字符串中提取raise to的金额
        if 'to' in raise_action.action:
            parts = raise_action.action.split()
            if len(parts) >= 3:
                raise_to_amount = float(parts[2].replace('BB', ''))
                print(f"  Raise to: {raise_to_amount:.2f}BB")

                # 检查是否是整数BB
                remainder = raise_to_amount % 1
                if remainder < 0.01:
                    print(f"  ✅ 金额是整数BB")
                else:
                    print(f"  ❌ 金额不是整数BB（有小数：{remainder:.2f}）")
    else:
        print("  ❌ 未找到raise动作")


def test_utils_round_function():
    """测试utils中的round_bet_amount函数"""
    print("\n" + "="*80)
    print("测试：round_bet_amount函数")
    print("="*80)

    from poker_env.utils import round_bet_amount

    test_cases = [
        (1.32, 1.0),
        (1.87, 2.0),
        (9.35, 9.0),
        (2.24, 2.0),
        (19.97, 20.0),
        (32.88, 33.0),
        (23.50, 24.0),  # 不允许0.5
        (0.5, 0.0),     # 四舍五入到0 (banker's rounding)
        (1.0, 1.0),
        (1.49, 1.0),
        (1.50, 2.0),
        (1.74, 2.0),
        (2.26, 2.0),
    ]

    all_passed = True
    for input_val, expected in test_cases:
        result = round_bet_amount(input_val)
        status = "✅" if abs(result - expected) < 0.01 else "❌"
        print(f"  {status} round_bet_amount({input_val:.2f}) = {result:.2f} (期望 {expected:.2f})")
        if abs(result - expected) >= 0.01:
            all_passed = False

    if all_passed:
        print("\n  ✅ 所有测试用例通过")
    else:
        print("\n  ❌ 部分测试用例失败")


if __name__ == '__main__':
    print("\n" + "="*80)
    print("🧪 Bet/Raise金额规范化测试")
    print("="*80)

    test_utils_round_function()
    test_bet_normalization()
    test_bet_normalization_2()
    test_raise_normalization()

    print("\n" + "="*80)
    print("✅ 所有测试完成")
    print("="*80)
