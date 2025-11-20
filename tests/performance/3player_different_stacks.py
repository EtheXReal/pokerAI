"""
3-Player Game with Different Stack Sizes

测试不同筹码量的3人游戏：
- AI: 100BB
- Random_1: 80BB
- Random_2: 150BB
"""
import sys
import os
import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState
from advisor_v2.analysis.range_engine import RangeEngine
from advisor_v2.analysis.equity_engine import EquityEngine
from advisor_v2.analysis.board_analyzer import BoardAnalyzer
from advisor_v2.strategy.gto_strategy import GTOStrategy
from advisor_v2.integration.decision_integrator import DecisionIntegrator
import random
import argparse


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
                street=game_state.street,
                position=game_state.position,
                is_in_position=game_state.is_in_position,
                hero_hand=game_state.hand,
                pot_size=game_state.pot,
                effective_stack=game_state.effective_stack,
                hero_stack=game_state.hero_stack,
                board=game_state.board,
                facing_bet=game_state.facing_bet,
                bet_to_call=game_state.to_call
            )

            # 使用integrator做决策
            decision_trace = self.integrator.decide(advisor_game_state)

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
                        amount = game_state.to_call if action_type == 'call' else 0

                    return PlayerAction(action=action_type, amount=amount)

            # 如果有selected_action
            if selected_action:
                action_type = selected_action.action
                amount = selected_action.amount if hasattr(selected_action, 'amount') else 0
                return PlayerAction(action=action_type, amount=amount)

            # 默认fallback
            if game_state.to_call > 0:
                return PlayerAction(action='fold', amount=0)
            else:
                return PlayerAction(action='check', amount=0)

        except Exception as e:
            # 出错时fallback到简单策略
            print(f"  [Error in AI decision: {e}]")
            if game_state.to_call > 0:
                # 50% fold, 50% call
                if random.random() < 0.5:
                    return PlayerAction(action='fold', amount=0)
                else:
                    return PlayerAction(action='call', amount=game_state.to_call)
            else:
                return PlayerAction(action='check', amount=0)


class RandomPlayer(Player):
    """随机策略玩家"""

    def decide(self, game_state: GameState) -> PlayerAction:
        """简单的随机决策"""
        rand = random.random()

        if game_state.to_call <= 0:
            # 无需跟注，check或bet
            if rand < 0.6:
                return PlayerAction(action='check', amount=0)
            else:
                # 小注bet
                bet_amount = game_state.pot * 0.6
                return PlayerAction(action='bet', amount=bet_amount)
        else:
            # 需要跟注
            if rand < 0.4:
                return PlayerAction(action='fold', amount=0)
            elif rand < 0.8:
                return PlayerAction(action='call', amount=game_state.to_call)
            else:
                # raise
                raise_amount = game_state.facing_bet * 2.5
                return PlayerAction(action='raise', amount=raise_amount)


class TeeOutput:
    """同时输出到终端和保存到内存"""
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


def run_test(num_hands: int, seed: int, verbose: bool = False):
    """运行3人游戏测试（不同筹码量）"""

    # 创建玩家（不同初始筹码）
    players = [
        AdvisorV2Player("AI", 0, 100.0),         # 100BB
        RandomPlayer("Random_1", 1, 80.0),       # 80BB
        RandomPlayer("Random_2", 2, 150.0),      # 150BB
    ]

    config = GameConfig(
        num_players=3,
        starting_stack=100.0,  # 这个参数会被每手牌reset时覆盖
        small_blind=0.5,
        big_blind=1.0,
        verbose=verbose,
        debug=False
    )

    game = PokerGame(players, config)

    # 记录每个玩家的初始筹码
    initial_stacks = {
        "AI": 100.0,
        "Random_1": 80.0,
        "Random_2": 150.0,
    }

    # 统计数据
    player_total_profits = {p.name: 0.0 for p in players}
    player_wins = {p.name: 0 for p in players}
    player_showdowns = {p.name: 0 for p in players}

    print(f"Playing {num_hands} hands with different stack sizes...")
    print(f"Initial stacks: AI=100BB, Random_1=80BB, Random_2=150BB")
    print()

    # 每手牌循环BTN
    for hand_num in range(1, num_hands + 1):
        btn_seat = (hand_num - 1) % 3

        # 重置玩家筹码到各自的初始值
        players[0].reset_for_new_hand(initial_stacks["AI"])
        players[1].reset_for_new_hand(initial_stacks["Random_1"])
        players[2].reset_for_new_hand(initial_stacks["Random_2"])

        result = game.play_hand(hand_num, btn_seat, seed + hand_num)

        # 更新统计
        for i, player in enumerate(players):
            profit = result.player_profits[i]
            player_total_profits[player.name] += profit

            if i in result.winner_seats:
                player_wins[player.name] += 1

            if result.showdown and player.is_active:
                player_showdowns[player.name] += 1

        # 简短摘要
        winner_names = [players[s].name for s in result.winner_seats]
        winner_str = ", ".join(winner_names) if winner_names else "No winner"
        print(f"Hand #{hand_num} - BTN: {players[btn_seat].name} (seat {btn_seat}) → Winner: {winner_str}, Pot: {result.pot:.1f}BB")

    # 最终统计
    print("\n" + "=" * 80)
    print("Final Statistics")
    print("=" * 80)
    print(f"\nTotal hands: {num_hands}")
    print(f"Random seed: {seed}")
    print(f"\nInitial stacks: AI=100BB, Random_1=80BB, Random_2=150BB")
    print("\nPlayer Performance:")
    print("-" * 80)
    print(f"{'Player':<16}{'Profit':<13}{'BB/100':<13}{'Wins':<9}{'Win%':<9}{'Showdowns'}")
    print("-" * 80)

    for player in players:
        profit = player_total_profits[player.name]
        bb_per_100 = (profit / num_hands) * 100 if num_hands > 0 else 0
        wins = player_wins[player.name]
        win_pct = (wins / num_hands) * 100 if num_hands > 0 else 0
        showdowns = player_showdowns[player.name]

        profit_str = f"{profit:+.1f}BB" if profit >= 0 else f"{profit:.1f}BB"
        bb100_str = f"{bb_per_100:+.1f}" if bb_per_100 >= 0 else f"{bb_per_100:.1f}"

        print(f"{player.name:<16}{profit_str:<13}{bb100_str:<13}{wins:<9}{win_pct:.1f}%{' ':<4}{showdowns}")

    # 验证零和
    total_sum = sum(player_total_profits.values())
    print(f"\nTotal profit sum: {total_sum:.2f}BB (should be ~0)")

    # 判断AI表现
    ai_profit = player_total_profits["AI"]
    print("\n" + "=" * 80)
    if ai_profit > 0:
        print(f"✓ AI Player won {ai_profit:.1f}BB")
    else:
        print(f"✗ AI Player lost {abs(ai_profit):.1f}BB")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description='3-Player Game with Different Stack Sizes')
    parser.add_argument('--hands', type=int, default=20, help='Number of hands to play')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    parser.add_argument('--verbose', action='store_true', help='Show detailed game output')
    args = parser.parse_args()

    # 设置随机种子
    random.seed(args.seed)

    # 创建输出目录
    output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'test_results')
    os.makedirs(output_dir, exist_ok=True)

    # 使用TeeOutput同时输出到终端和文件
    tee = TeeOutput()
    sys.stdout = tee

    try:
        run_test(args.hands, args.seed, args.verbose)
    finally:
        sys.stdout = tee.terminal

    # 保存输出到文件
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"3player_different_stacks_{timestamp}.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(tee.get_log())

    print(f"\n✅ Output saved to: {output_file}")


if __name__ == "__main__":
    main()
