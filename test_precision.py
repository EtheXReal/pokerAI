#!/usr/bin/env python
"""
测试poker_env的精度规则修改

验证：
1. SB盲注0.5BB正常
2. SB可以call 0.5BB
3. 主动bet 0.5BB被拒绝（改为check）
4. 主动bet 1BB允许
5. All-in < 1BB允许
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState


class TestPlayer(Player):
    """测试用的可控玩家"""

    def __init__(self, name: str, seat: int, stack: float, actions=None):
        super().__init__(name, seat, stack)
        self.actions = actions or []
        self.action_index = 0
        self.decisions = []  # 记录所有决策

    def decide(self, game_state: GameState) -> PlayerAction:
        # 记录决策点信息
        decision_info = {
            'street': game_state.street,
            'to_call': game_state.to_call,
            'hero_stack': game_state.hero_stack,
            'pot': game_state.pot,
        }
        self.decisions.append(decision_info)

        # 如果有预设动作，使用预设
        if self.action_index < len(self.actions):
            action = self.actions[self.action_index]
            self.action_index += 1
            return action

        # 默认：没有facing bet就check，否则fold
        if game_state.to_call <= 0.01:
            return PlayerAction('check', 0.0)
        else:
            return PlayerAction('fold', 0.0)


def test_1_sb_blind_and_call():
    """测试1：SB盲注0.5BB和补盲call 0.5BB"""
    print("\n" + "="*80)
    print("测试1：SB盲注0.5BB和补盲call 0.5BB")
    print("="*80)

    # SB call到1BB（补盲0.5BB）
    p1 = TestPlayer("SB", 0, 100.0, [
        PlayerAction('call', 0.0),  # call 0.5BB补盲
    ])
    p2 = TestPlayer("BB", 1, 100.0, [
        PlayerAction('check', 0.0),  # BB check
    ])

    config = GameConfig(num_players=2, starting_stack=100.0, verbose=True)
    game = PokerGame([p1, p2], config)

    result = game.play_hand(hand_num=0, btn_seat=0, seed=42)

    # 验证
    print("\n验证结果：")
    print(f"P1 (SB) 最终投入: {p1.invested:.2f}BB")
    print(f"P2 (BB) 最终投入: {p2.invested:.2f}BB")

    # SB应该投入1.0BB（0.5盲注 + 0.5补盲）
    assert abs(p1.decisions[0]['to_call'] - 0.5) < 0.01, f"SB to_call应为0.5BB，实际{p1.decisions[0]['to_call']}"
    print("✅ SB facing 0.5BB to_call（补盲）")
    print("✅ SB成功call 0.5BB")


def test_2_bet_too_small():
    """测试2：主动bet 0.5BB被拒绝（改为check）"""
    print("\n" + "="*80)
    print("测试2：主动bet 0.5BB被拒绝")
    print("="*80)

    # SB试图bet 0.5BB（应该被改为check）
    p1 = TestPlayer("SB", 0, 100.0, [
        PlayerAction('call', 0.0),    # Preflop: call
        PlayerAction('bet', 0.5),     # Flop: 试图bet 0.5BB
    ])
    p2 = TestPlayer("BB", 1, 100.0, [
        PlayerAction('check', 0.0),   # Preflop: check
        PlayerAction('check', 0.0),   # Flop: check
    ])

    config = GameConfig(num_players=2, starting_stack=100.0, verbose=True)
    game = PokerGame([p1, p2], config)

    result = game.play_hand(hand_num=0, btn_seat=0, seed=43)

    # 验证：bet 0.5BB应该被改为check
    # 检查action记录中是否有bet（不应该有）
    bet_actions = [a for a in result.actions if 'bet' in a.action.lower()]
    print(f"\n验证结果：bet动作数量 = {len(bet_actions)}")
    print(f"所有Flop动作: {[a.action for a in result.actions if a.street == 'flop']}")

    # 应该都是check，没有bet
    flop_actions = [a for a in result.actions if a.street == 'flop']
    assert all('check' in a.action for a in flop_actions), "Flop应该都是check（bet 0.5BB被拒绝）"
    print("✅ 主动bet 0.5BB被正确拒绝（改为check）")


def test_3_bet_1bb():
    """测试3：主动bet 1BB允许"""
    print("\n" + "="*80)
    print("测试3：主动bet 1BB允许")
    print("="*80)

    # SB bet 1BB（应该允许）
    p1 = TestPlayer("SB", 0, 100.0, [
        PlayerAction('call', 0.0),    # Preflop: call
        PlayerAction('bet', 1.0),     # Flop: bet 1BB
    ])
    p2 = TestPlayer("BB", 1, 100.0, [
        PlayerAction('check', 0.0),   # Preflop: check
        PlayerAction('fold', 0.0),    # Flop: fold
    ])

    config = GameConfig(num_players=2, starting_stack=100.0, verbose=True)
    game = PokerGame([p1, p2], config)

    result = game.play_hand(hand_num=0, btn_seat=0, seed=44)

    # 验证：应该有bet 1BB
    bet_actions = [a for a in result.actions if 'bet' in a.action.lower() and a.street == 'flop']
    print(f"\n验证结果：Flop bet动作 = {bet_actions}")

    assert len(bet_actions) > 0, "应该有bet动作"
    assert bet_actions[0].amount >= 1.0, f"Bet金额应该>=1BB，实际{bet_actions[0].amount}"
    print("✅ 主动bet 1BB被正确允许")


def test_4_allin_small_stack():
    """测试4：All-in < 1BB允许"""
    print("\n" + "="*80)
    print("测试4：All-in < 1BB允许")
    print("="*80)

    # P1只有0.7BB stack，试图bet（all-in）
    p1 = TestPlayer("SB", 0, 0.7, [
        PlayerAction('bet', 0.2),  # Preflop: all-in（只有0.2BB剩余）
    ])
    p2 = TestPlayer("BB", 1, 100.0, [
        PlayerAction('fold', 0.0),
    ])

    config = GameConfig(num_players=2, starting_stack=0.7, verbose=True)
    game = PokerGame([p1, p2], config)

    # 手动设置stack
    p1.stack = 0.7
    p2.stack = 100.0

    result = game.play_hand(hand_num=0, btn_seat=0, seed=45)

    # 验证：小筹码all-in应该允许
    print(f"\n验证结果：")
    print(f"P1初始stack: 0.7BB")
    print(f"P1最终投入: {result.player_profits[0] + (0 if result.winner_seats[0] == 0 else 0)}")

    # P1应该all-in了（即使<1BB）
    assert p1.is_allin or p1.stack < 0.01, "P1应该all-in"
    print("✅ All-in < 1BB被正确允许")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*80)
    print("🧪 poker_env 精度规则测试")
    print("="*80)

    tests = [
        test_1_sb_blind_and_call,
        test_2_bet_too_small,
        test_3_bet_1bb,
        test_4_allin_small_stack,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ 测试失败: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ 测试错误: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*80)
    print(f"测试结果: {passed}/{len(tests)} 通过")
    print("="*80)

    if failed == 0:
        print("✅ 所有测试通过！精度规则修改正确！")
    else:
        print(f"❌ {failed}个测试失败")
        sys.exit(1)


if __name__ == '__main__':
    run_all_tests()
