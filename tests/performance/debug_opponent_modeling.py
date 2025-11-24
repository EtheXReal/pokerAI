#!/usr/bin/env python
"""
调试对手建模系统 - 验证tracker是否正常工作

测试内容：
1. tracker是否在积累数据
2. 分类器是否正确识别玩家类型
3. exploit策略是否被应用
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState
from advisor_v2.integration.decision_integrator import DecisionIntegrator
from advisor_v2.analysis.range_engine import RangeEngine
from advisor_v2.analysis.equity_engine import EquityEngine
from advisor_v2.analysis.board_analyzer import BoardAnalyzer
from advisor_v2.strategy.hybrid_strategy import HybridStrategy
from advisor_v2.modeling import classify_player

from tests.performance.styled_players import create_styled_player


class DebugAdvisorV2Player(Player):
    """带调试输出的AI玩家"""

    def __init__(self, name: str, seat: int, stack: float, all_players=None):
        super().__init__(name, seat, stack)
        self.range_engine = RangeEngine()
        self.equity_engine = EquityEngine()
        self.board_analyzer = BoardAnalyzer()
        self.hybrid_strategy = HybridStrategy()

        self.integrator = DecisionIntegrator(
            range_engine=self.range_engine,
            equity_engine=self.equity_engine,
            board_analyzer=self.board_analyzer,
            strategy=self.hybrid_strategy
        )
        self.all_players = all_players or []

    def decide(self, game_state: GameState) -> PlayerAction:
        try:
            decision_trace = self.integrator.decide(game_state)
            selected_action = decision_trace.selected_action

            if not selected_action:
                if decision_trace.final_decision:
                    action_dist = decision_trace.final_decision.action_dist
                    import random
                    actions = list(action_dist.keys())
                    probs = list(action_dist.values())
                    action_type = random.choices(actions, weights=probs)[0]

                    if action_type in ['bet', 'raise'] and decision_trace.final_decision.sizing_dist:
                        sizings = list(decision_trace.final_decision.sizing_dist.keys())
                        sizing_probs = list(decision_trace.final_decision.sizing_dist.values())
                        amount_multiplier = random.choices(sizings, weights=sizing_probs)[0]
                        amount = amount_multiplier * game_state.pot
                    else:
                        amount = game_state.to_call if action_type == 'call' else 0

                    return PlayerAction(action=action_type, amount=amount)

            if selected_action:
                action_type = selected_action.action
                amount = selected_action.amount if hasattr(selected_action, 'amount') else 0
                return PlayerAction(action=action_type, amount=amount)

            if game_state.to_call > 0:
                return PlayerAction(action='fold', amount=0)
            else:
                return PlayerAction(action='check', amount=0)

        except Exception as e:
            print(f"  [决策错误: {e}]")
            import traceback
            traceback.print_exc()
            if game_state.to_call > 0:
                return PlayerAction('fold', 0.0)
            else:
                return PlayerAction('check', 0.0)

    def on_hand_complete(self, game_result) -> None:
        try:
            from advisor_v2.integration.utils import convert_game_result_to_hand_history
            hand_history = convert_game_result_to_hand_history(game_result, self.all_players)
            self.integrator.tracker.update_from_hand(hand_history)
        except Exception as e:
            print(f"⚠️  on_hand_complete失败: {e}")
            import traceback
            traceback.print_exc()

    def print_opponent_stats(self, opponent_name: str):
        """打印对手统计数据"""
        stats = self.integrator.tracker.get_stats(opponent_name)
        if not stats or stats.hands_played == 0:
            print(f"❌ 没有找到{opponent_name}的统计数据或手数为0")
            print(f"   这说明 on_hand_complete 可能没有被正确调用")
            return

        print(f"\n{'='*80}")
        print(f"对手统计: {opponent_name}")
        print(f"{'='*80}")
        print(f"手数: {stats.hands_played}")
        print(f"VPIP: {stats.vpip*100:.1f}%")
        print(f"PFR: {stats.pfr*100:.1f}%")
        print(f"AF: {stats.af:.2f}")
        print(f"C-bet (flop): {stats.cbet_flop*100:.1f}%")
        print(f"Fold to C-bet (flop): {stats.fold_to_cbet_flop*100:.1f}%")
        print(f"WTSD: {stats.wtsd*100:.1f}%")
        print(f"W$SD: {stats.w_sd*100:.1f}%")

        # 分类
        if stats.hands_played >= 10:
            classification = classify_player(stats)
            print(f"\n玩家分类:")
            print(f"  类型: {classification.player_type.name}")
            print(f"  置信度: {classification.confidence:.2f}")
            print(f"  理由: {classification.reason if hasattr(classification, 'reason') else 'N/A'}")
        else:
            print(f"\n玩家分类: 手数不足 ({stats.hands_played} < 10)")


def test_opponent_modeling(opponent_style: str, n_hands: int = 100):
    """测试对手建模功能"""
    print(f"\n{'#'*80}")
    print(f"测试对手风格: {opponent_style.upper()}")
    print(f"{'#'*80}\n")

    # 创建玩家
    players = [None, None]
    opponent = create_styled_player(opponent_style, "Opponent", seat=1, stack=100.0)
    players[1] = opponent

    ai = DebugAdvisorV2Player("AI", seat=0, stack=100.0, all_players=players)
    players[0] = ai

    # 创建游戏
    config = GameConfig(
        num_players=2,
        starting_stack=100.0,
        small_blind=0.5,
        big_blind=1.0,
        verbose=False,
        debug=False
    )
    game = PokerGame(players, config)

    # 运行游戏
    print(f"开始运行{n_hands}手牌...\n")
    for i in range(n_hands):
        btn_seat = i % 2
        try:
            result = game.play_hand(hand_num=i, btn_seat=btn_seat, seed=42 * 10000 + i)

            # 每10手打印一次进度
            if (i + 1) % 10 == 0:
                print(f"Hand #{i+1} 完成")

        except Exception as e:
            print(f"Hand #{i+1} 错误: {e}")

    # 打印最终统计
    ai.print_opponent_stats("Opponent")

    # 打印AI盈亏
    print(f"\n{'='*80}")
    print(f"AI盈亏统计")
    print(f"{'='*80}")
    total_profit = sum([r.player_profits[0] for r in game.results])
    print(f"总盈利: {total_profit:+.2f} BB")
    print(f"BB/100: {(total_profit / n_hands) * 100:+.2f}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='调试对手建模系统')
    parser.add_argument('--style', type=str, default='nit',
                       choices=['nit', 'tag', 'lag', 'fish', 'calling_station', 'maniac'],
                       help='对手风格')
    parser.add_argument('--hands', type=int, default=100, help='测试手数')
    args = parser.parse_args()

    test_opponent_modeling(args.style, args.hands)
