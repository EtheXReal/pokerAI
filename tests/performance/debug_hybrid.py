"""
调试HybridStrategy - 查看决策细节
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState
from advisor_v2.analysis.range_engine import RangeEngine
from advisor_v2.analysis.equity_engine import EquityEngine
from advisor_v2.analysis.board_analyzer import BoardAnalyzer
from advisor_v2.strategy.hybrid_strategy import HybridStrategy
from advisor_v2.integration.decision_integrator import DecisionIntegrator
from advisor_v2.integration.utils import convert_game_result_to_hand_history
import random

from styled_players import NitPlayer


class DebugAIPlayer(Player):
    """调试用AI玩家 - 打印所有决策细节"""

    def __init__(self, name: str, seat: int, stack: float, all_players: list = None):
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
        self.decision_count = 0

    def decide(self, game_state: GameState) -> PlayerAction:
        """使用HybridStrategy做决策并打印细节"""
        self.decision_count += 1

        # 只打印前10个决策和第100-110个决策（看confidence变化）
        should_print = (self.decision_count <= 10) or (100 <= self.decision_count <= 110)

        if should_print:
            print(f"\n{'='*60}")
            print(f"Decision #{self.decision_count}")
            print(f"Street: {game_state.street}, Position: {game_state.position}")
            print(f"to_call: {game_state.to_call}, facing_bet: {game_state.facing_bet}")

        try:
            decision_trace = self.integrator.decide(game_state)

            if should_print:
                # 打印对手建模数据
                nit_stats = self.integrator.tracker.get_stats('Nit')
                if nit_stats:
                    print(f"\nNit Stats:")
                    print(f"  Hands: {nit_stats.hands_played}, VPIP: {nit_stats.vpip:.1%}, Confidence: {nit_stats.get_confidence():.1%}")

                # 打印final_decision
                if decision_trace.final_decision:
                    print(f"\nFinal Decision:")
                    print(f"  Actions: {decision_trace.final_decision.action_distribution}")
                    print(f"  Reasoning: {decision_trace.final_decision.reasoning[:80]}")
                    print(f"  Key Factors:")
                    for k, v in decision_trace.final_decision.key_factors.items():
                        print(f"    {k}: {v}")

            # 提取action
            if decision_trace.final_decision:
                action_dist = decision_trace.final_decision.action_distribution
                actions = list(action_dist.keys())
                probs = list(action_dist.values())
                action_type = random.choices(actions, weights=probs)[0]

                if action_type in ['bet', 'raise'] and decision_trace.final_decision.sizing_distribution:
                    sizings = list(decision_trace.final_decision.sizing_distribution.keys())
                    sizing_probs = list(decision_trace.final_decision.sizing_distribution.values())
                    amount_multiplier = random.choices(sizings, weights=sizing_probs)[0]
                    amount = amount_multiplier * game_state.pot
                else:
                    amount = game_state.to_call if action_type == 'call' else 0

                if should_print:
                    print(f"\nSelected: {action_type} {amount:.1f}")

                return PlayerAction(action=action_type, amount=amount)

            # Fallback
            if game_state.to_call > 0:
                return PlayerAction(action='fold', amount=0)
            else:
                return PlayerAction(action='check', amount=0)

        except Exception as e:
            if should_print:
                print(f"\nERROR: {e}")
                import traceback
                traceback.print_exc()

            # Fallback
            if game_state.to_call > 0:
                return PlayerAction(action='fold', amount=0)
            else:
                return PlayerAction(action='check', amount=0)

    def on_hand_complete(self, game_result) -> None:
        """手牌结束回调"""
        try:
            hand_history = convert_game_result_to_hand_history(game_result, self.all_players)
            self.integrator.tracker.update_from_hand(hand_history)
        except Exception as e:
            pass


def run_debug_test():
    """运行调试测试"""
    print("HybridStrategy Debug Test\n")

    players = [None, None]
    ai_player = DebugAIPlayer("AI", 0, 200.0, all_players=players)
    nit_player = NitPlayer("Nit", 1, 200.0)
    players[0] = ai_player
    players[1] = nit_player

    config = GameConfig(
        num_players=2,
        starting_stack=200.0,
        small_blind=0.5,
        big_blind=1.0,
        verbose=False,
        debug=False
    )

    random.seed(42)
    game = PokerGame(players, config)

    # 只跑120手，看看前10个和100-110个决策
    num_hands = 120
    btn_seat = 0

    for hand_num in range(num_hands):
        result = game.play_hand(hand_num=hand_num+1, btn_seat=btn_seat, seed=42+hand_num)
        btn_seat = (btn_seat + 1) % 2

    print(f"\n{'='*60}")
    print(f"Test Complete")
    print(f"Total decisions: {ai_player.decision_count}")


if __name__ == '__main__':
    run_debug_test()
