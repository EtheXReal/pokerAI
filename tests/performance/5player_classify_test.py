"""
5-Player Classification Test

测试对手建模系统的准确性，使用4种明确风格的玩家：
- TAG (Tight-Aggressive)
- LAG (Loose-Aggressive)
- Nit (Tight-Passive)
- Fish (Loose-Passive)

验证统计追踪器能否准确识别不同的玩家类型
"""
import sys
import os
import datetime
from typing import List
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState
from advisor_v2.analysis.range_engine import RangeEngine
from advisor_v2.analysis.equity_engine import EquityEngine
from advisor_v2.analysis.board_analyzer import BoardAnalyzer
from advisor_v2.strategy.gto_strategy import GTOStrategy
from advisor_v2.integration.decision_integrator import DecisionIntegrator
from advisor_v2.integration.utils import convert_game_result_to_hand_history, print_opponent_stats_report
from advisor_v2.modeling.classifier import classify_player
import random
import argparse

from styled_players import TAGPlayer, LAGPlayer, NitPlayer, FishPlayer


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
            if game_state.to_call > 0:
                # 50% fold, 50% call
                if random.random() < 0.5:
                    return PlayerAction(action='fold', amount=0)
                else:
                    return PlayerAction(action='call', amount=game_state.to_call)
            else:
                return PlayerAction(action='check', amount=0)

    def on_hand_complete(self, game_result) -> None:
        """手牌结束回调 - 更新对手建模数据"""
        try:
            # 转换GameResult为hand_history格式
            hand_history = convert_game_result_to_hand_history(game_result, self.all_players)

            # 更新tracker
            self.integrator.tracker.update_from_hand(hand_history)
        except Exception as e:
            # 静默失败，不影响游戏
            pass


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
    """运行5人游戏测试"""

    # 创建玩家列表
    players = [
        None,  # AI - 稍后创建
        TAGPlayer("TAG", 1, 200.0),
        LAGPlayer("LAG", 2, 200.0),
        NitPlayer("Nit", 3, 200.0),
        FishPlayer("Fish", 4, 200.0),
    ]

    # 创建AI玩家，传入所有玩家引用
    ai_player = AdvisorV2Player("AI", 0, 200.0, all_players=players)
    players[0] = ai_player

    config = GameConfig(
        num_players=5,
        starting_stack=200.0,
        small_blind=0.5,
        big_blind=1.0,
        verbose=verbose,
        debug=False
    )

    # 设置随机种子
    random.seed(seed)

    # 创建游戏
    game = PokerGame(players, config)

    # 重定向输出
    tee = TeeOutput()
    old_stdout = sys.stdout
    if not verbose:
        sys.stdout = tee

    # 运行游戏
    print(f"\n{'='*80}")
    print(f"5-Player Classification Test")
    print(f"{'='*80}\n")
    print(f"Testing opponent modeling with 4 player styles:")
    print(f"  - TAG (Tight-Aggressive): Expected VPIP ~22%, PFR ~18%, AF ~3.0")
    print(f"  - LAG (Loose-Aggressive): Expected VPIP ~40%, PFR ~28%, AF ~3.0")
    print(f"  - Nit (Tight-Passive): Expected VPIP ~18%, PFR ~6%, AF ~0.7")
    print(f"  - Fish (Loose-Passive): Expected VPIP ~58%, PFR ~14%, AF ~0.6")
    print(f"\nRunning {num_hands} hands with seed={seed}...\n")

    btn_seat = 0
    player_total_profits = [0.0] * 5  # 累积每个玩家的总profit

    for hand_num in range(num_hands):
        result = game.play_hand(hand_num=hand_num+1, btn_seat=btn_seat, seed=seed+hand_num)

        # 累加profit（使用env提供的数据）
        for i in range(5):
            player_total_profits[i] += result.player_profits[i]

        # 输出简短信息
        btn_player = players[result.btn_seat]
        winner_names = [players[seat].name for seat in result.winner_seats]
        winner_str = ', '.join(winner_names)
        print(f"Hand #{hand_num+1} - BTN: {btn_player.name} (seat {result.btn_seat}) → Winner: {winner_str}, Pot: {result.pot:.1f}BB")

        # 移动按钮
        btn_seat = (btn_seat + 1) % 5

    # 恢复stdout
    sys.stdout = old_stdout

    # 收集最终统计
    print(f"\n{'='*80}")
    print(f"Final Statistics")
    print(f"{'='*80}\n")
    print(f"Total hands: {num_hands}")
    print(f"Random seed: {seed}\n")

    # 玩家表现
    print(f"Player Performance:")
    print(f"{'-'*80}")
    print(f"{'Player':<15} {'Profit':>12} {'BB/100':>12} {'Stack':>10}")
    print(f"{'-'*80}")

    total_profit = 0
    for i, player in enumerate(players):
        profit = player_total_profits[i]  # 使用env累积的profit
        bb_per_100 = (profit / num_hands) * 100
        total_profit += profit

        print(f"{player.name:<15} {profit:+11.1f}BB {bb_per_100:+11.1f} {player.stack:>9.1f}BB")

    print(f"\nTotal profit sum: {total_profit:.2f}BB (should be ~0)\n")

    # 对手建模报告
    print(f"{'='*80}")
    print(f"Opponent Modeling Analysis")
    print(f"{'='*80}\n")

    # 获取统计数据
    all_stats = ai_player.integrator.tracker.get_all_stats()

    # 预期值
    expected_stats = {
        'TAG': {'vpip': 0.22, 'pfr': 0.18, 'af': 3.0, 'three_bet': 0.063, 'cbet': 0.75, 'player_type': 'TAG'},
        'LAG': {'vpip': 0.40, 'pfr': 0.28, 'af': 3.0, 'three_bet': 0.102, 'cbet': 0.65, 'player_type': 'LAG'},
        'Nit': {'vpip': 0.18, 'pfr': 0.06, 'af': 0.7, 'three_bet': 0.021, 'cbet': 0.35, 'player_type': 'Nit'},
        'Fish': {'vpip': 0.58, 'pfr': 0.14, 'af': 0.6, 'three_bet': 0.050, 'cbet': 0.25, 'player_type': 'Fish'},
    }

    for player_id, stats in sorted(all_stats.items()):
        if player_id == 'AI':
            continue

        confidence = stats.get_confidence()
        classification_result = classify_player(stats)
        player_type = classification_result.player_type
        type_confidence = classification_result.confidence

        # 获取预期值
        expected = expected_stats.get(player_id, {})
        expected_type = expected.get('player_type', 'Unknown')

        print(f"{player_id}:")
        print(f"  Classified as: {player_type} (confidence: {type_confidence:.1%})")
        print(f"  Expected type: {expected_type}")
        print(f"  Hands Played: {stats.hands_played}")

        # 统计数据 vs 预期
        def show_stat(name, actual, expected_val, tolerance=0.10):
            diff = abs(actual - expected_val)
            status = "✓" if diff <= tolerance else "✗"
            return f"  {name}: {actual:.1%} (expected {expected_val:.1%}) {status}"

        print(show_stat("VPIP", stats.vpip, expected.get('vpip', 0)))
        print(show_stat("PFR", stats.pfr, expected.get('pfr', 0)))
        print(f"  Aggression Factor: {stats.af:.2f} (expected {expected.get('af', 0):.2f})")
        print(show_stat("3-Bet", stats.three_bet_pct, expected.get('three_bet', 0.05), tolerance=0.05))  # 使用实际期望值
        print(show_stat("C-Bet Flop", stats.cbet_flop, expected.get('cbet', 0), tolerance=0.20))  # 放宽C-bet容差（受位置影响）
        print(f"  Fold to C-Bet Flop: {stats.fold_to_cbet_flop:.1%}")
        print(f"  WTSD: {stats.wtsd:.1%}")
        print(f"  W$SD: {stats.w_sd:.1%}")
        print(f"  Confidence: {confidence:.1%}\n")

    # 保存结果到文件
    output_dir = os.path.join(os.path.dirname(__file__), '../../test_results')
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(output_dir, f'5player_classify_test_{timestamp}.txt')

    with open(output_file, 'w') as f:
        if not verbose:
            f.write(tee.get_log())
        else:
            # 如果是verbose模式，只写总结
            f.write(f"5-Player Classification Test - {num_hands} hands\n")
            f.write(f"Seed: {seed}\n\n")
            f.write("See console output for detailed statistics\n")

    print(f"{'='*80}\n")
    print(f"✅ Output saved to: {output_file}")

    return players, all_stats


def main():
    parser = argparse.ArgumentParser(description='5-Player Classification Test')
    parser.add_argument('--hands', type=int, default=200,
                       help='Number of hands to play (default: 200)')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed (default: 42)')
    parser.add_argument('--verbose', action='store_true',
                       help='Show detailed game output')

    args = parser.parse_args()

    run_test(num_hands=args.hands, seed=args.seed, verbose=args.verbose)


if __name__ == '__main__':
    main()
