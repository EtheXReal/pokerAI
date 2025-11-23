"""
3-Player Game with AI Players

演示如何在3人游戏中使用AdvisorV2 AI玩家
"""
import sys
import os
from typing import List
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState
from advisor_v2.analysis.range_engine import RangeEngine
from advisor_v2.analysis.equity_engine import EquityEngine
from advisor_v2.analysis.board_analyzer import BoardAnalyzer
from advisor_v2.strategy.gto_strategy import GTOStrategy
from advisor_v2.integration.decision_integrator import DecisionIntegrator
from advisor_v2.integration.utils import convert_game_result_to_hand_history, print_opponent_stats_report
import random


class AdvisorV2Player(Player):
    """使用AdvisorV2的AI玩家"""

    def __init__(self, name: str, seat: int, stack: float, all_players: List[Player] = None):
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

        # 保存所有玩家引用（用于hand_history转换）
        self.all_players = all_players or []

    def decide(self, game_state: GameState) -> PlayerAction:
        """使用advisor_v2做决策"""
        try:
            # DecisionIntegrator现在可以直接接受poker_env.GameState
            decision_trace = self.integrator.decide(game_state)

            # 从DecisionTrace中提取最终决策
            selected_action = decision_trace.selected_action
            if not selected_action:
                # 如果没有selected_action，使用final_decision
                if decision_trace.final_decision:
                    selected_action = decision_trace.final_decision.action_dist
                    # 从distribution中采样
                    import random
                    actions = list(selected_action.keys())
                    probs = list(selected_action.values())
                    action_type = random.choices(actions, weights=probs)[0]

                    # 获取sizing
                    if action_type in ['bet', 'raise'] and decision_trace.final_decision.sizing_dist:
                        sizings = list(decision_trace.final_decision.sizing_dist.keys())
                        sizing_probs = list(decision_trace.final_decision.sizing_dist.values())
                        amount_multiplier = random.choices(sizings, weights=sizing_probs)[0]
                        amount = amount_multiplier * game_state.pot
                    else:
                        amount = 0.0
                else:
                    # 兜底：check或fold
                    action_type = 'check' if game_state.to_call < 0.01 else 'fold'
                    amount = 0.0
            else:
                # 使用selected_action
                action_type = selected_action.action
                amount = selected_action.amount if hasattr(selected_action, 'amount') else 0.0

                # 如果amount是pot的倍数，转换为实际金额
                if action_type in ['bet', 'raise'] and amount > 0:
                    amount = amount * game_state.pot

            # 限制在筹码范围内
            if amount > 0:
                amount = min(amount, game_state.hero_stack)

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

    def on_hand_complete(self, game_result) -> None:
        """
        手牌结束回调 - 更新对手建模数据

        当一手牌结束时，poker_env会调用此方法。
        我们将GameResult转换为tracker可以理解的格式，然后更新对手统计。
        """
        try:
            # 转换GameResult为hand_history格式
            hand_history = convert_game_result_to_hand_history(game_result, self.all_players)

            # 更新tracker
            self.integrator.tracker.update_from_hand(hand_history)
        except Exception as e:
            # 静默失败，不影响游戏
            pass


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


class TeeOutput:
    """同时输出到控制台和文件的类"""
    def __init__(self):
        self.terminal = sys.stdout
        self.log = []

    def write(self, message):
        self.terminal.write(message)
        self.log.append(message)

    def flush(self):
        self.terminal.flush()

    def get_log(self):
        return ''.join(self.log)


def main():
    """运行3人AI游戏测试"""
    import argparse
    import datetime

    parser = argparse.ArgumentParser(description='3-player game with AI')
    parser.add_argument('--hands', type=int, default=10, help='手牌数量')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    args = parser.parse_args()

    random.seed(args.seed)

    # 设置输出重定向
    tee = TeeOutput()
    old_stdout = sys.stdout
    sys.stdout = tee

    print("=" * 80)
    print("3-Player Texas Hold'em - AI vs Random Players")
    print("=" * 80)

    # 创建玩家：1个AI + 2个随机玩家
    # 先创建列表，然后让AI玩家获取引用
    players = [
        None,  # AI - 稍后创建
        RandomPlayer("Random_1", 1, 100.0, fold_prob=0.35, raise_prob=0.2),
        RandomPlayer("Random_2", 2, 100.0, fold_prob=0.40, raise_prob=0.15),
    ]

    # 创建AI玩家，传入所有玩家引用
    ai_player = AdvisorV2Player("AI", 0, 100.0, all_players=players)
    players[0] = ai_player

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

    # 打印对手建模报告
    opponent_names = ["Random_1", "Random_2"]
    print_opponent_stats_report(ai_player.integrator.tracker, opponent_names)

    # 恢复stdout
    sys.stdout = old_stdout

    # 保存输出到文件
    output_dir = "test_results"
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"3player_ai_test_{timestamp}.txt")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(tee.get_log())

    print(f"\n✅ Output saved to: {output_file}")


if __name__ == '__main__':
    main()
