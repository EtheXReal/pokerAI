"""Debug why tracker is not receiving opponent data"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState
from tests.performance.styled_players import create_styled_player
from advisor_v2.integration.decision_integrator import DecisionIntegrator
from advisor_v2.analysis.range_engine import RangeEngine
from advisor_v2.analysis.equity_engine import EquityEngine
from advisor_v2.analysis.board_analyzer import BoardAnalyzer
from advisor_v2.strategy.hybrid_strategy import HybridStrategy
from advisor_v2.integration.utils import convert_game_result_to_hand_history
import random

# Create AIPlayer wrapper
class AIPlayer(Player):
    def __init__(self, name, seat, stack, all_players):
        super().__init__(name, seat, stack)
        self.all_players = all_players
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

    def decide(self, game_state):
        decision_trace = self.integrator.decide(game_state)
        selected_action = decision_trace.selected_action
        if selected_action:
            return PlayerAction(action=selected_action.action, amount=getattr(selected_action, 'amount', 0))
        return PlayerAction(action='fold', amount=0)

    def on_hand_complete(self, game_result):
        """手牌结束回调"""
        print(f"\n[DEBUG] on_hand_complete called for {self.name}")
        print(f"  game_result type: {type(game_result)}")
        print(f"  game_result attributes: {dir(game_result)}")

        try:
            hand_history = convert_game_result_to_hand_history(game_result, self.all_players)
            print(f"  [DEBUG] hand_history: {hand_history}")

            # 更新tracker
            self.integrator.tracker.update_from_hand(hand_history)

            # 检查tracker状态
            all_stats = self.integrator.tracker.get_all_stats()
            print(f"  [DEBUG] Tracker now has {len(all_stats)} players:")
            for player_id, stats in all_stats.items():
                print(f"    - {player_id}: hands={stats.hands_played}, VPIP={stats.vpip:.1%}, PFR={stats.pfr:.1%}")

        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback
            traceback.print_exc()

# Create players
players = [None, None]
maniac = create_styled_player('maniac', 'Maniac', 1, 100.0)
players[1] = maniac

ai = AIPlayer('AI', 0, 100.0, players)
players[0] = ai

config = GameConfig(
    num_players=2,
    starting_stack=100.0,
    small_blind=0.5,
    big_blind=1.0,
    verbose=False,
    debug=False
)

# Run 30 hands to trigger opponent modeling
random.seed(42)
game = PokerGame(players, config)

for i in range(30):
    btn_seat = i % 2
    print(f"\n{'='*80}")
    print(f"Hand #{i+1}")
    print(f"{'='*80}")
    result = game.play_hand(hand_num=i+1, btn_seat=btn_seat, seed=42+i)

    # After 30 hands, check if opponent is being classified
    if i == 29:
        print("\n[DEBUG] After 30 hands, checking opponent classification:")
        maniac_stats = ai.integrator.tracker.get_stats('Maniac')
        print(f"  Maniac stats: hands={maniac_stats.hands_played}, VPIP={maniac_stats.vpip:.1%}, PFR={maniac_stats.pfr:.1%}, AF={maniac_stats.af:.2f}")

        if maniac_stats.hands_played >= 20:
            print(f"  three_bet_pct: {maniac_stats.three_bet_pct:.1%}")
            print(f"  wtsd: {maniac_stats.wtsd:.1%}")
            print(f"  w_sd: {maniac_stats.w_sd:.1%}")

            # Calculate scores for all types
            scores = ai.integrator.classifier._calculate_type_scores(maniac_stats)
            print(f"\n  Type scores:")
            for ptype, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
                print(f"    {ptype.name}: {score:.3f}")

            classification = ai.integrator.classifier.classify(maniac_stats)
            print(f"\n  Final classification: {classification.player_type.name}, confidence={classification.confidence:.2f}")
            print(f"  Reason: {classification.reason}")

print(f"\n{'='*80}")
print("Final tracker state:")
print(f"{'='*80}")
all_stats = ai.integrator.tracker.get_all_stats()
for player_id, stats in all_stats.items():
    print(f"{player_id}:")
    print(f"  hands_played: {stats.hands_played}")
    print(f"  VPIP: {stats.vpip:.1%}")
    print(f"  PFR: {stats.pfr:.1%}")
    print(f"  AF: {stats.af:.2f}")
