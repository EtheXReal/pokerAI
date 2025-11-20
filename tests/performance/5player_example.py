"""
5-Player Game Example

演示如何创建和运行5人德州扑克游戏
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState
import random


class RandomPlayer(Player):
    """随机玩家 - 用于测试"""
    def __init__(self, name: str, seat: int, stack: float,
                 fold_prob: float = 0.3, raise_prob: float = 0.2):
        super().__init__(name, seat, stack)
        self.fold_prob = fold_prob
        self.raise_prob = raise_prob

    def decide(self, game_state: GameState) -> PlayerAction:
        """简单随机策略"""
        # 如果不需要跟注，check或bet
        if game_state.to_call < 0.01:
            if random.random() < self.raise_prob:
                bet_size = game_state.pot * random.choice([0.5, 0.75, 1.0])
                return PlayerAction('bet', bet_size)
            else:
                return PlayerAction('check', 0.0)

        # 需要跟注
        if random.random() < self.fold_prob:
            return PlayerAction('fold', 0.0)
        elif random.random() < self.raise_prob / (1 - self.fold_prob):
            raise_size = game_state.pot * random.choice([0.5, 1.0, 1.5])
            return PlayerAction('raise', raise_size)
        else:
            return PlayerAction('call', 0.0)


def main():
    """运行5人游戏示例"""
    print("=" * 80)
    print("5-Player Texas Hold'em Game Example")
    print("=" * 80)

    # 创建5个玩家
    players = [
        RandomPlayer("Alice", 0, 100.0, fold_prob=0.35, raise_prob=0.15),
        RandomPlayer("Bob", 1, 100.0, fold_prob=0.40, raise_prob=0.20),
        RandomPlayer("Charlie", 2, 100.0, fold_prob=0.30, raise_prob=0.25),
        RandomPlayer("Diana", 3, 100.0, fold_prob=0.45, raise_prob=0.15),
        RandomPlayer("Eve", 4, 100.0, fold_prob=0.35, raise_prob=0.20),
    ]

    # 游戏配置
    config = GameConfig(
        num_players=5,
        starting_stack=100.0,
        small_blind=0.5,
        big_blind=1.0,
        verbose=True,  # 打印详细过程
        debug=False
    )

    # 创建游戏
    game = PokerGame(players, config)

    # 玩3手牌
    print("\n" + "=" * 80)
    print("Playing 3 hands...")
    print("=" * 80)

    results = []
    for hand_num in range(3):
        btn_seat = hand_num % 5  # BTN轮换

        print("\n" + "=" * 80)
        print(f"Hand #{hand_num + 1} - BTN: {players[btn_seat].name} (seat {btn_seat})")
        print("=" * 80)

        # 打印座位和位置信息
        from poker_env.utils import get_position_name
        print("\n座位和位置:")
        for i, player in enumerate(players):
            pos_name = get_position_name(i, btn_seat, 5)
            print(f"  Seat {i}: {player.name} ({pos_name})")

        # 玩一手牌
        result = game.play_hand(hand_num=hand_num+1, btn_seat=btn_seat, seed=42+hand_num)
        results.append(result)

        # 打印结果
        print("\n" + "-" * 80)
        print("Hand Result:")
        print("-" * 80)
        print(f"  Winner(s): {', '.join([players[s].name for s in result.winner_seats])}")
        print(f"  Total Pot: {result.pot:.1f}BB")
        print(f"  Showdown: {'Yes' if result.showdown else 'No (fold win)'}")

        if result.showdown:
            print(f"\n  Final Board: {' '.join(result.flop)} {result.turn} {result.river}")
            print(f"\n  Hand Strengths:")
            for i, player in enumerate(players):
                if result.hand_strengths[i] != "FOLDED":
                    print(f"    {player.name}: {result.player_hands[i]} - {result.hand_strengths[i]}")

        print(f"\n  Player Profits:")
        for i, player in enumerate(players):
            profit = result.player_profits[i]
            sign = "+" if profit >= 0 else ""
            print(f"    {player.name}: {sign}{profit:.1f}BB (invested: {players[i].invested:.1f}BB)")

        # 重置筹码为下一手牌
        for i, player in enumerate(players):
            # 根据盈亏调整筹码
            player.stack = config.starting_stack + result.player_profits[i]

    # 最终统计
    print("\n" + "=" * 80)
    print("Final Statistics (after 3 hands)")
    print("=" * 80)

    # 计算每个玩家的总盈亏
    total_profits = [0.0] * 5
    for result in results:
        for i in range(5):
            total_profits[i] += result.player_profits[i]

    print("\nTotal Profits:")
    for i, player in enumerate(players):
        profit = total_profits[i]
        sign = "+" if profit >= 0 else ""
        print(f"  {player.name}: {sign}{profit:.1f}BB")

    # 验证零和游戏
    total = sum(total_profits)
    print(f"\nSum of all profits: {total:.2f}BB (should be ~0)")
    assert abs(total) < 0.1, "Not a zero-sum game!"

    print("\n" + "=" * 80)
    print("✓ All hands completed successfully!")
    print("=" * 80)


if __name__ == '__main__':
    main()
