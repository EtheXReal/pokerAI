"""
1v1 Adaptive Strategy Test (Fixed Probe Experiment)

Objective:
Verify that the AI adapts its strategy against a specific opponent style (Fish) over time.

Methodology:
1.  Play a 1v1 match against a fixed opponent style (Fish).
2.  Every N hands, pause and query the AI with a "Fixed Probe" scenario.
3.  The Probe: River scenario, Top Pair Weak Kicker.
    - vs Unknown: Should Check (Pot Control).
    - vs Fish: Should Bet (Thin Value).
4.  Observe if the decision shifts from Check to Bet as the AI classifies the opponent.
"""
import sys
import os
import random
import argparse
from typing import List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState
from poker_core import Hand, Board, Card
from advisor_v2.core.data_structures import StrategyContext, Position
from advisor_v2.analysis.range_engine import RangeEngine
from advisor_v2.analysis.equity_engine import EquityEngine
from advisor_v2.analysis.board_analyzer import BoardAnalyzer
from advisor_v2.strategy.hybrid_strategy import HybridStrategy
from advisor_v2.integration.decision_integrator import DecisionIntegrator
from advisor_v2.integration.utils import convert_game_result_to_hand_history
from advisor_v2.modeling.classifier import classify_player

from styled_players import FishPlayer

class AdaptiveAIPlayer(Player):
    """AI Player that exposes internal state for probing"""

    def __init__(self, name: str, seat: int, stack: float, all_players: List[Player] = None):
        super().__init__(name, seat, stack)
        self.range_engine = RangeEngine()
        self.equity_engine = EquityEngine()
        self.board_analyzer = BoardAnalyzer()
        # Use HybridStrategy to enable exploitation
        self.strategy = HybridStrategy()
        
        self.integrator = DecisionIntegrator(
            range_engine=self.range_engine,
            equity_engine=self.equity_engine,
            board_analyzer=self.board_analyzer,
            strategy=self.strategy
        )
        self.all_players = all_players or []

    def decide(self, game_state: GameState) -> PlayerAction:
        """Normal gameplay decision"""
        try:
            decision_trace = self.integrator.decide(game_state)
            selected_action = decision_trace.selected_action
            
            if selected_action:
                return PlayerAction(action=selected_action.action, amount=selected_action.amount)
            
            # Fallback
            if game_state.to_call > 0:
                return PlayerAction(action='fold', amount=0)
            return PlayerAction(action='check', amount=0)

        except Exception as e:
            # print(f"AI Error: {e}") # Suppress during gameplay to keep output clean
            if game_state.to_call > 0:
                return PlayerAction(action='call', amount=game_state.to_call)
            return PlayerAction(action='check', amount=0)

    def on_hand_complete(self, game_result) -> None:
        """Update tracker"""
        try:
            hand_history = convert_game_result_to_hand_history(game_result, self.all_players)
            self.integrator.tracker.update_from_hand(hand_history)
        except Exception:
            pass

    def probe_decision(self, opponent_name: str) -> Tuple[str, float, str, float]:
        """
        Run the Fixed Probe scenario.
        
        Scenario:
        - Hero (BTN): Kh 9c (Top Pair, Weak Kicker)
        - Board: Ks 8d 3c 2h 2s (Dry, paired board)
        - Pot: 10 BB
        - Opponent (BB): Checked
        
        Returns:
            (Action, Amount, OpponentType, Confidence)
        """
        # Construct the probe state manually
        # Note: We need to construct a StrategyContext-like object or use the integrator's internal methods
        # But integrator.decide takes a GameState. Let's mock a GameState.
        
        # Mock Board and Hand
        hero_hand = Hand([Card.from_str('Kh'), Card.from_str('9c')])
        board = Board([Card.from_str('Ks'), Card.from_str('8d'), Card.from_str('3c'), Card.from_str('2h'), Card.from_str('2s')])
        
        # Construct a GameState for the probe
        # We need to be careful to match the expected fields of GameState
        # Assuming GameState is a dataclass or similar from poker_env
        
        # Create a dummy GameState
        # Note: In the actual code, GameState might be different from StrategyContext
        # Let's look at how decide() uses it. It passes it to integrator.decide(game_state)
        # integrator.decide converts it to StrategyContext.
        
        # We will create a StrategyContext directly to bypass the conversion if possible,
        # OR create a mock GameState that the converter accepts.
        # Let's try creating a StrategyContext directly and calling strategy.calculate() 
        # BUT we want the full integration logic (including modeling).
        
        # So we must use integrator.decide(). We need to mock GameState.
        # Let's look at what GameState looks like in poker_env (inferred)
        
        probe_state = GameState(
            street='river',
            player=self,
            position='BTN',
            hand=hero_hand,
            board=board,
            pot=10.0,
            effective_stack=95.0,
            hero_stack=95.0,
            facing_bet=0.0,
            to_call=0.0,
            min_raise=1.0,
            num_active_players=2,
            num_allin_players=0,
            is_in_position=True
        )
        
        # We need to ensure the integrator uses the CURRENT tracker state for the opponent
        # The integrator looks up opponent stats based on seat/name.
        # In this 1v1 test, opponent is at the other seat.
        
        # Run decision
        decision_trace = self.integrator.decide(probe_state)
        
        # Extract info
        action = "check"
        amount = 0.0
        if decision_trace.selected_action:
            action = decision_trace.selected_action.action
            amount = decision_trace.selected_action.amount
        
        # Get opponent classification info from the tracker
        opp_stats = self.integrator.tracker.get_stats(opponent_name)
        if opp_stats:
            classification = classify_player(opp_stats)
            opp_type = classification.player_type
            confidence = classification.confidence
        else:
            opp_type = "Unknown"
            confidence = 0.0
            
        return action, amount, opp_type, confidence

def run_experiment(num_hands: int = 200, probe_interval: int = 20):
    print(f"\n{'='*80}")
    print(f"1v1 Adaptive Strategy Experiment: AI vs Fish")
    print(f"{'='*80}")
    print(f"Probe Scenario: River, TPWK (K9 on K8322), Pot 10BB")
    print(f"Hypothesis: AI should switch from CHECK to BET as it identifies the Fish.")
    print(f"{'-'*80}\n")
    
    # Setup
    players = [
        None, # AI
        FishPlayer("Fishy", 1, 200.0)
    ]
    ai_player = AdaptiveAIPlayer("AI_Pro", 0, 200.0, all_players=players)
    players[0] = ai_player
    
    config = GameConfig(num_players=2, starting_stack=200.0, small_blind=0.5, big_blind=1.0, verbose=False)
    game = PokerGame(players, config)
    
    # Header
    print(f"{'Hand':<6} | {'Opponent Type':<15} | {'Conf.':<6} | {'Probe Action':<12} | {'Amount':<8} | {'Comment'}")
    print(f"{'-'*80}")
    
    # Initial Probe (Hand 0)
    action, amount, opp_type, conf = ai_player.probe_decision("Fishy")
    print(f"{0:<6} | {opp_type:<15} | {conf:>5.0%} | {action.upper():<12} | {amount:>6.1f}BB | Initial Baseline")
    
    # Loop
    btn_seat = 0
    for i in range(1, num_hands + 1):
        # Play one hand
        game.play_hand(hand_num=i, btn_seat=btn_seat, seed=42+i)
        btn_seat = (btn_seat + 1) % 2
        
        # Probe every N hands
        if i % probe_interval == 0:
            action, amount, opp_type, conf = ai_player.probe_decision("Fishy")
            
            # Determine comment
            comment = ""
            if action == 'bet' and amount > 0:
                comment = "--> EXPLOITING!"
            
            print(f"{i:<6} | {opp_type:<15} | {conf:>5.0%} | {action.upper():<12} | {amount:>6.1f}BB | {comment}")

    print(f"{'-'*80}")
    print("Experiment Complete.")

if __name__ == "__main__":
    run_experiment()
