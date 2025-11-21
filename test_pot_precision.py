#!/usr/bin/env python
"""
测试pot精度问题

发现问题：
- Random raise to 3.0BB后，pot=4.0BB ✓
- AI call后，pot=6.1BB（应该是6.0BB）❌
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState


class DebugPlayer(Player):
    """调试用玩家 - 记录所有决策信息"""

    def __init__(self, name: str, seat: int, stack: float, actions=None):
        super().__init__(name, seat, stack)
        self.actions = actions or []
        self.action_index = 0
        self.decisions = []

    def decide(self, game_state: GameState) -> PlayerAction:
        # 详细记录决策点
        info = {
            'street': game_state.street,
            'to_call': game_state.to_call,
            'facing_bet': game_state.facing_bet,
            'hero_stack': game_state.hero_stack,
            'pot': game_state.pot,
            'player_invested': self.invested,
            'street_invested': self.street_invested,
        }
        self.decisions.append(info)

        print(f"\n[{self.name} Decision]")
        print(f"  Street: {info['street']}")
        print(f"  Pot: {info['pot']:.2f}BB")
        print(f"  To call: {info['to_call']:.2f}BB")
        print(f"  Facing bet: {info['facing_bet']:.2f}BB")
        print(f"  Stack: {info['hero_stack']:.2f}BB")
        print(f"  Total invested: {info['player_invested']:.2f}BB")
        print(f"  Street invested: {info['street_invested']:.2f}BB")

        if self.action_index < len(self.actions):
            action = self.actions[self.action_index]
            self.action_index += 1
            print(f"  Action: {action.action} {action.amount:.2f}BB")
            return action

        # 默认fold
        return PlayerAction('fold', 0.0)


def test_pot_calculation():
    """测试pot精度计算"""
    print("="*80)
    print("测试：Pot计算精度")
    print("="*80)

    # Random raise to 3BB, AI call
    p1 = DebugPlayer("Random", 0, 100.0, [
        PlayerAction('raise', 2.0),  # raise 2BB (到3BB)
    ])
    p2 = DebugPlayer("AI", 1, 100.0, [
        PlayerAction('call', 0.0),   # call
    ])

    config = GameConfig(num_players=2, starting_stack=100.0, verbose=True, debug=True)
    game = PokerGame([p1, p2], config)

    print("\n初始状态：")
    print(f"  SB (Random): {p1.stack:.2f}BB")
    print(f"  BB (AI): {p2.stack:.2f}BB")

    result = game.play_hand(hand_num=0, btn_seat=0, seed=42)

    print("\n\n" + "="*80)
    print("验证结果")
    print("="*80)

    # 检查preflop的投入
    print(f"\nPreflop投入：")
    print(f"  Random总投入: {p1.invested:.2f}BB")
    print(f"  AI总投入: {p2.invested:.2f}BB")

    # 查看actions
    print(f"\nActions记录：")
    for action in result.actions:
        if action.street == 'preflop':
            print(f"  [{action.street}] {action.player_name}: {action.action}, pot_after={action.pot_after:.2f}BB")

    # 检查pot精度
    preflop_actions = [a for a in result.actions if a.street == 'preflop']
    if len(preflop_actions) >= 2:
        final_pot = preflop_actions[-1].pot_after
        expected_pot = 6.0  # 3.0 + 3.0

        print(f"\nPot检查：")
        print(f"  预期pot: {expected_pot:.2f}BB")
        print(f"  实际pot: {final_pot:.2f}BB")
        print(f"  误差: {abs(final_pot - expected_pot):.4f}BB")

        if abs(final_pot - expected_pot) > 0.02:
            print("  ❌ Pot计算有误！")

            # 详细分析
            print("\n详细分析：")
            print(f"  Random invested: {p1.invested:.10f}BB")
            print(f"  AI invested: {p2.invested:.10f}BB")
            print(f"  Total: {p1.invested + p2.invested:.10f}BB")
        else:
            print("  ✅ Pot计算正确")


def test_sb_precision():
    """测试SB盲注精度"""
    print("\n\n" + "="*80)
    print("测试：SB盲注精度")
    print("="*80)

    from poker_env.utils import round_amount

    # 测试0.5BB的精度
    sb = 0.5
    sb_rounded = round_amount(sb)

    print(f"\nSB盲注：")
    print(f"  原始值: {sb}")
    print(f"  round_amount后: {sb_rounded:.10f}")
    print(f"  是否相等: {sb == sb_rounded}")

    # 测试累加
    total = 0.0
    total += round_amount(0.5)  # SB
    total += round_amount(1.0)  # BB
    total = round_amount(total)

    print(f"\n累加测试：")
    print(f"  0.5 + 1.0 = {total:.10f}")
    print(f"  预期: 1.5")
    print(f"  误差: {abs(total - 1.5):.10f}")


def test_raise_calculation():
    """测试raise金额计算"""
    print("\n\n" + "="*80)
    print("测试：Raise金额计算")
    print("="*80)

    from poker_env.utils import round_amount

    # 模拟Random的raise
    # SB投入0.5，要raise到3.0
    sb_invested = round_amount(0.5)
    raise_to = round_amount(3.0)
    additional = round_amount(raise_to - sb_invested)

    print(f"\nRandom raise计算：")
    print(f"  SB已投入: {sb_invested:.10f}BB")
    print(f"  Raise to: {raise_to:.10f}BB")
    print(f"  需要再投入: {additional:.10f}BB")
    print(f"  总投入: {round_amount(sb_invested + additional):.10f}BB")

    # Pot计算
    pot = round_amount(1.5)  # 初始pot
    pot = round_amount(pot + additional)

    print(f"\nPot计算：")
    print(f"  初始pot: 1.5BB")
    print(f"  加上additional: {pot:.10f}BB")
    print(f"  预期: 4.0BB")
    print(f"  误差: {abs(pot - 4.0):.10f}BB")


if __name__ == '__main__':
    test_pot_calculation()
    test_sb_precision()
    test_raise_calculation()
