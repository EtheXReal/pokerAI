"""
3-Player Game with AI Players

演示如何在3人游戏中使用AdvisorV2 AI玩家
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState
from advisor_v2.analysis.range_engine import RangeEngine
from advisor_v2.analysis.equity_engine import EquityEngine
from advisor_v2.analysis.board_analyzer import BoardAnalyzer
from advisor_v2.strategy.gto_strategy import GTOStrategy
from advisor_v2.integration.decision_integrator import DecisionIntegrator
import random


class AdvisorV2Player(Player):
    """使用AdvisorV2的AI玩家"""

    def __init__(self, name: str, seat: int, stack: float):
        super().__init__(name, seat, stack)

        # 初始化advisor_v2组件
        self.range_engine = RangeEngine()
        self.equity_engine = EquityEngine()
        self.board_analyzer = BoardAnalyzer()
        self.gto_strategy = GTOStrategy()

        self.integrator = DecisionIntegrator(
            range_engine=self.range_engine,
            equity_engine=self.equity_engine,
            board_analyzer=self.board_analyzer,
            strategy=self.gto_strategy
        )

    def decide(self, game_state: GameState) -> PlayerAction:
        """使用advisor_v2做决策"""
        try:
            # 转换为advisor格式
            from advisor.strategy_engine import GameState as AdvisorGameState
            from advisor.strategy_engine import Position, Street

            # 位置映射
            position_map = {
                'BTN': Position.BTN,
                'BTN/SB': Position.BTN,  # 2人游戏
                'SB': Position.BTN,       # SB在3+人游戏中也算后位
                'BB': Position.BB,
                'UTG': Position.UTG,
                'MP': Position.MP,
                'CO': Position.CO,
            }
            position = position_map.get(game_state.position, Position.MP)

            # 街道映射
            street_map = {
                'preflop': Street.PREFLOP,
                'flop': Street.FLOP,
                'turn': Street.TURN,
                'river': Street.RIVER,
            }
            street = street_map.get(game_state.street, Street.PREFLOP)

            # 构建advisor game state
            advisor_game_state = AdvisorGameState(
                street=street,
                position=position,
                hand=game_state.hand,
                board=game_state.board,
                pot=game_state.pot,
                effective_stack=game_state.effective_stack,
                hero_stack=game_state.hero_stack,
                facing_bet=game_state.facing_bet,
                num_players=game_state.num_active_players,
                is_in_position=game_state.is_in_position
            )

            # 使用integrator做决策
            decision = self.integrator.decide(advisor_game_state)

            # 转换回poker_env格式
            action_type = decision.action

            # 计算实际金额
            if action_type in ['bet', 'raise']:
                # decision.amount是pot的倍数
                amount = decision.amount * game_state.pot
                # 限制在筹码范围内
                amount = min(amount, game_state.hero_stack)
            else:
                amount = 0.0

            return PlayerAction(action_type, amount)

        except Exception as e:
            # 出错时采用保守策略
            print(f"  [Error in AI decision: {e}]")
            if game_state.to_call > 0:
                if game_state.to_call < game_state.pot * 0.3:
                    return PlayerAction('call', 0.0)
                else:
                    return PlayerAction('fold', 0.0)
            else:
                return PlayerAction('check', 0.0)


class RandomPlayer(Player):
    """简单随机玩家"""

    def __init__(self, name: str, seat: int, stack: float,
                 fold_prob: float = 0.4, raise_prob: float = 0.2):
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
            raise_size = game_state.pot * random.choice([0.5, 1.0])
            return PlayerAction('raise', raise_size)
        else:
            return PlayerAction('call', 0.0)


def main():
    """运行3人AI游戏测试"""
    import argparse

    parser = argparse.ArgumentParser(description='3-player game with AI')
    parser.add_argument('--hands', type=int, default=10, help='手牌数量')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    args = parser.parse_args()

    random.seed(args.seed)

    print("=" * 80)
    print("3-Player Texas Hold'em - AI vs Random Players")
    print("=" * 80)

    # 创建玩家：1个AI + 2个随机玩家
    players = [
        AdvisorV2Player("AI", 0, 100.0),
        RandomPlayer("Random_1", 1, 100.0, fold_prob=0.35, raise_prob=0.2),
        RandomPlayer("Random_2", 2, 100.0, fold_prob=0.40, raise_prob=0.15),
    ]

    # 游戏配置
    config = GameConfig(
        num_players=3,
        starting_stack=100.0,
        small_blind=0.5,
        big_blind=1.0,
        verbose=args.verbose,
        debug=False
    )

    # 创建游戏
    game = PokerGame(players, config)

    # 统计数据
    player_total_profits = [0.0, 0.0, 0.0]
    player_hands_played = [0, 0, 0]
    player_showdowns = [0, 0, 0]
    player_wins = [0, 0, 0]

    print(f"\nPlaying {args.hands} hands...")
    print("=" * 80)

    # 玩多手牌
    for hand_num in range(args.hands):
        btn_seat = hand_num % 3

        if not args.verbose:
            # 简洁输出
            print(f"\nHand #{hand_num + 1} - BTN: {players[btn_seat].name} (seat {btn_seat})", end="")

        result = game.play_hand(hand_num=hand_num+1, btn_seat=btn_seat, seed=args.seed+hand_num)

        # 更新统计
        for i in range(3):
            player_total_profits[i] += result.player_profits[i]
            if result.player_profits[i] != 0:
                player_hands_played[i] += 1
            if result.showdown and players[i].is_active:
                player_showdowns[i] += 1
            if i in result.winner_seats:
                player_wins[i] += 1

        if not args.verbose:
            winners = [players[s].name for s in result.winner_seats]
            print(f" → Winner: {', '.join(winners)}, Pot: {result.pot:.1f}BB")

    # 最终统计
    print("\n" + "=" * 80)
    print("Final Statistics")
    print("=" * 80)

    print(f"\nTotal hands: {args.hands}")
    print(f"Random seed: {args.seed}")

    print("\nPlayer Performance:")
    print("-" * 80)
    print(f"{'Player':<15} {'Profit':<12} {'BB/100':<12} {'Wins':<8} {'Win%':<8} {'Showdowns'}")
    print("-" * 80)

    for i, player in enumerate(players):
        profit = player_total_profits[i]
        bb_per_100 = (profit / args.hands) * 100 if args.hands > 0 else 0
        wins = player_wins[i]
        win_rate = (wins / args.hands * 100) if args.hands > 0 else 0
        showdowns = player_showdowns[i]

        sign = "+" if profit >= 0 else ""
        print(f"{player.name:<15} {sign}{profit:>6.1f}BB    {sign}{bb_per_100:>6.1f}      "
              f"{wins:<8} {win_rate:>5.1f}%   {showdowns}")

    # 验证零和游戏
    total = sum(player_total_profits)
    print(f"\nTotal profit sum: {total:.2f}BB (should be ~0)")

    print("\n" + "=" * 80)
    if player_total_profits[0] > 0:
        print(f"✓ AI Player won {player_total_profits[0]:.1f}BB!")
    else:
        print(f"✗ AI Player lost {-player_total_profits[0]:.1f}BB")
    print("=" * 80)


if __name__ == '__main__':
    main()
