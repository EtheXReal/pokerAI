#!/usr/bin/env python3
"""
测试betting round的多轮加注逻辑

重现问题：Random_1 raise后，没有机会对后续加注做出反应
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState
import random


class ScriptedPlayer(Player):
    """按脚本行动的玩家"""

    def __init__(self, name: str, seat: int, stack: float, script: list):
        super().__init__(name, seat, stack)
        self.script = script  # [(action, amount), ...]
        self.action_count = 0

    def decide(self, game_state: GameState) -> PlayerAction:
        if self.action_count < len(self.script):
            action, amount = self.script[self.action_count]
            self.action_count += 1
            print(f"  [Script] {self.name} action #{self.action_count}: {action} {amount}BB (stack={self.stack:.1f}BB, to_call={game_state.to_call:.1f}BB)")
            return PlayerAction(action=action, amount=amount)
        else:
            # 默认fold
            print(f"  [Script] {self.name} ran out of script, folding")
            return PlayerAction(action='fold', amount=0)


def test_multi_raise_scenario():
    """测试多轮加注场景"""

    print("=" * 80)
    print("测试场景：Random_1 raise后，应该有机会对后续加注做出反应")
    print("=" * 80)

    # 设置玩家脚本
    # BTN=0 (AI), SB=1 (Random_1, 80BB), BB=2 (Random_2, 150BB)
    # 翻前顺序：AI(BTN) → Random_1(SB) → Random_2(BB)

    players = [
        ScriptedPlayer("AI", 0, 100.0, [
            ('raise', 4.0),      # 第1次行动：raise to 4BB
            ('raise', 100.0),    # 第2次行动：re-raise to 100BB all-in
        ]),
        ScriptedPlayer("Random_1", 1, 80.0, [
            ('raise', 24.0),     # 第1次行动：raise to 24BB
            ('call', 56.0),      # 第2次行动：应该有机会call all-in 80BB
        ]),
        ScriptedPlayer("Random_2", 2, 150.0, [
            ('raise', 100.0),    # 第1次行动：raise to 100BB
        ]),
    ]

    config = GameConfig(
        num_players=3,
        starting_stack=100.0,
        small_blind=0.5,
        big_blind=1.0,
        verbose=True,
        debug=True
    )

    game = PokerGame(players, config)

    print("\n初始筹码：")
    print("  AI (BTN, seat 0): 100BB")
    print("  Random_1 (SB, seat 1): 80BB")
    print("  Random_2 (BB, seat 2): 150BB")
    print()
    print("预期行动顺序：")
    print("  1. AI raises to 4BB")
    print("  2. Random_1 raises to 24BB")
    print("  3. Random_2 raises to 100BB")
    print("  4. AI raises to 100BB all-in")
    print("  5. Random_1 应该有机会call (需要再投入56BB，总共80BB all-in)")
    print()

    result = game.play_hand(hand_num=1, btn_seat=0, seed=42)

    print("\n" + "=" * 80)
    print("投入情况：")
    for i, player in enumerate(players):
        print(f"  {player.name}: invested={players[i].invested:.1f}BB")

    print("\n预期投入：")
    print("  AI: 100BB (all-in)")
    print("  Random_1: 80BB (all-in)")
    print("  Random_2: 100BB")

    print("\n如果Random_1只投入了24BB，说明他没有机会对后续加注做出反应！")
    print("=" * 80)


if __name__ == "__main__":
    test_multi_raise_scenario()
