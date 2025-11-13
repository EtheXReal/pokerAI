"""
Multi-player Side Pot Test

测试边池逻辑在3+人游戏中的完整性
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState


class StackedPlayer(Player):
    """
    测试用玩家 - 可以预设行动序列
    """
    def __init__(self, name: str, seat: int, stack: float, actions: list = None):
        super().__init__(name, seat, stack)
        self.actions = actions or []
        self.action_index = 0

    def decide(self, game_state: GameState) -> PlayerAction:
        """按预设行动序列行动"""
        if self.action_index < len(self.actions):
            action = self.actions[self.action_index]
            self.action_index += 1
            return action
        else:
            # 默认行动：fold
            return PlayerAction('fold', 0.0)


def test_3player_simple_sidepot():
    """
    测试1: 3人游戏，简单边池场景

    所有玩家all-in，测试边池计算和分配
    """
    print("\n" + "=" * 80)
    print("Test 1: 3-player simple side pot scenario")
    print("=" * 80)

    # 创建玩家 - 注意：starting_stack会在play_hand时被config覆盖
    players = [
        StackedPlayer("Player_A", 0, 100.0, [
            PlayerAction('raise', 100.0),  # all-in
        ]),
        StackedPlayer("Player_B", 1, 100.0, [
            PlayerAction('raise', 100.0),  # all-in
        ]),
        StackedPlayer("Player_C", 2, 100.0, [
            PlayerAction('call', 0.0),     # call
        ]),
    ]

    config = GameConfig(
        num_players=3,
        starting_stack=100.0,
        small_blind=0.5,
        big_blind=1.0,
        verbose=True,
        debug=False
    )

    game = PokerGame(players, config)
    result = game.play_hand(hand_num=1, btn_seat=0, seed=42)

    print("\n[Test 1] Results:")
    print(f"  Winner seats: {result.winner_seats}")
    print(f"  Total pot: {result.pot:.1f}BB")
    print(f"  Showdown: {result.showdown}")
    print(f"  Player profits: {[f'{p:.1f}BB' for p in result.player_profits]}")
    print(f"  Player investments: {[f'{p.invested:.1f}BB' for p in players]}")

    # 验证到了showdown
    assert result.showdown, "Should reach showdown"

    # 验证总pot = 总投入
    total_invested = sum(p.invested for p in players)
    assert abs(result.pot - total_invested) < 0.1, f"Pot {result.pot:.1f}BB != total invested {total_invested:.1f}BB"

    # 验证零和游戏
    total_profit = sum(result.player_profits)
    assert abs(total_profit) < 0.1, f"Total profit should be ~0, got {total_profit:.1f}BB"

    print("\n✓ Test 1 passed")
    return result


def test_4player_cascading_allin():
    """
    测试2: 4人游戏，连锁all-in

    4人游戏座位和盲注（BTN=0）：
    - seat 0 (BTN): 无盲注
    - seat 1 (SB): posts 0.5BB
    - seat 2 (BB): posts 1.0BB
    - seat 3 (UTG): 无盲注

    Preflop行动顺序: seat 3 (UTG) -> seat 0 (BTN) -> seat 1 (SB) -> seat 2 (BB)

    测试场景：让所有玩家all-in，形成多个边池
    """
    print("\n" + "=" * 80)
    print("Test 2: 4-player cascading all-in scenario")
    print("=" * 80)

    players = [
        StackedPlayer("Player_A", 0, 20.0, [
            PlayerAction('raise', 100.0),  # all-in
        ]),
        StackedPlayer("Player_B", 1, 40.5, [
            PlayerAction('raise', 100.0),  # all-in after SB
        ]),
        StackedPlayer("Player_C", 2, 60.0, [
            PlayerAction('raise', 100.0),  # all-in after BB
        ]),
        StackedPlayer("Player_D", 3, 100.0, [
            PlayerAction('call', 0.0),     # call
        ]),
    ]

    config = GameConfig(
        num_players=4,
        starting_stack=100.0,
        small_blind=0.5,
        big_blind=1.0,
        verbose=True,
        debug=False
    )

    game = PokerGame(players, config)
    result = game.play_hand(hand_num=1, btn_seat=0, seed=123)

    print("\n[Test 2] Results:")
    print(f"  Winner seats: {result.winner_seats}")
    print(f"  Total pot: {result.pot:.1f}BB")
    print(f"  Showdown: {result.showdown}")
    print(f"  Player profits: {[f'{p:.1f}BB' for p in result.player_profits]}")
    print(f"  Player investments: {[f'{p.invested:.1f}BB' for p in players]}")

    # 验证到了showdown
    assert result.showdown, "Should reach showdown"

    # 验证总pot
    total_invested = sum(p.invested for p in players)
    assert abs(result.pot - total_invested) < 0.1, f"Pot {result.pot:.1f}BB != invested {total_invested:.1f}BB"

    print("\n✓ Test 2 passed")
    return result


def test_3player_one_folds():
    """
    测试3: 3人游戏，一人fold

    测试边池逻辑能否正确处理有人fold的情况
    """
    print("\n" + "=" * 80)
    print("Test 3: 3-player with one fold scenario")
    print("=" * 80)

    players = [
        StackedPlayer("Player_A", 0, 30.0, [
            PlayerAction('raise', 100.0),  # all-in
        ]),
        StackedPlayer("Player_B", 1, 50.5, [
            PlayerAction('raise', 100.0),  # all-in after SB
            PlayerAction('fold', 0.0),      # fold if re-raised
        ]),
        StackedPlayer("Player_C", 2, 101.0, [
            PlayerAction('raise', 100.0),   # all-in after BB
            PlayerAction('call', 0.0),      # or call
        ]),
    ]

    config = GameConfig(
        num_players=3,
        starting_stack=100.0,
        small_blind=0.5,
        big_blind=1.0,
        verbose=True,
        debug=False
    )

    game = PokerGame(players, config)
    result = game.play_hand(hand_num=1, btn_seat=0, seed=456)

    print("\n[Test 3] Results:")
    print(f"  Winner seats: {result.winner_seats}")
    print(f"  Total pot: {result.pot:.1f}BB")
    print(f"  Showdown: {result.showdown}")
    print(f"  Player profits: {[f'{p:.1f}BB' for p in result.player_profits]}")
    print(f"  Player investments: {[f'{p.invested:.1f}BB' for p in players]}")

    # 验证总pot = 总投入
    total_invested = sum(p.invested for p in players)
    assert abs(result.pot - total_invested) < 0.1, f"Pot {result.pot:.1f}BB != invested {total_invested:.1f}BB"

    # 验证有获胜者
    assert len(result.winner_seats) > 0, "Should have winner(s)"

    # 验证零和游戏
    total_profit = sum(result.player_profits)
    assert abs(total_profit) < 0.1, f"Total profit should be ~0, got {total_profit:.1f}BB"

    print("\n✓ Test 3 passed")
    return result


def test_3player_split_pot():
    """
    测试4: 3人游戏，验证平分pot逻辑

    简单场景：3人all-in相同金额，验证边池计算和分配
    """
    print("\n" + "=" * 80)
    print("Test 4: 3-player equal investment scenario")
    print("=" * 80)

    players = [
        StackedPlayer("Player_A", 0, 50.0, [
            PlayerAction('raise', 100.0),  # all-in
        ]),
        StackedPlayer("Player_B", 1, 50.5, [
            PlayerAction('call', 0.0),     # call all-in (after SB)
        ]),
        StackedPlayer("Player_C", 2, 51.0, [
            PlayerAction('call', 0.0),     # call all-in (after BB)
        ]),
    ]

    config = GameConfig(
        num_players=3,
        starting_stack=50.0,
        small_blind=0.5,
        big_blind=1.0,
        verbose=True,
        debug=False
    )

    game = PokerGame(players, config)
    result = game.play_hand(hand_num=1, btn_seat=0, seed=789)

    print("\n[Test 4] Results:")
    print(f"  Winner seats: {result.winner_seats}")
    print(f"  Total pot: {result.pot:.1f}BB")
    print(f"  Showdown: {result.showdown}")
    print(f"  Hand strengths: {result.hand_strengths}")
    print(f"  Player profits: {[f'{p:.1f}BB' for p in result.player_profits]}")
    print(f"  Player investments: {[f'{p.invested:.1f}BB' for p in players]}")

    # 验证到了showdown
    assert result.showdown, "Should reach showdown"

    # 验证有获胜者
    assert len(result.winner_seats) > 0, "Should have at least one winner"

    # 验证总盈亏为0（零和游戏）
    total_profit = sum(result.player_profits)
    assert abs(total_profit) < 0.1, f"Total profit should be ~0, got {total_profit:.1f}BB"

    # 验证总pot = 总投入
    total_invested = sum(p.invested for p in players)
    assert abs(result.pot - total_invested) < 0.1, f"Pot {result.pot:.1f}BB != invested {total_invested:.1f}BB"

    print("\n✓ Test 4 passed")
    return result


def main():
    """运行所有测试"""
    print("=" * 80)
    print("Multi-player Side Pot Integration Tests")
    print("=" * 80)

    try:
        test_3player_simple_sidepot()
        test_4player_cascading_allin()
        test_3player_one_folds()
        test_3player_split_pot()

        print("\n" + "=" * 80)
        print("All integration tests passed! ✓")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
