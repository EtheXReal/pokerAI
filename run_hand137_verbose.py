#!/usr/bin/env python3
"""Run Hand #137 specifically with the real Advisor"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
        try:
            from advisor.strategy_engine import GameState as AdvisorGameState
            position_map = {
                'BTN': 'BTN', 'BTN/SB': 'BTN', 'SB': 'BTN',
                'BB': 'BB', 'UTG': 'UTG', 'MP': 'MP', 'CO': 'CO',
            }
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
            decision_trace = self.integrator.decide(advisor_game_state)
            selected_action = decision_trace.selected_action
            if not selected_action and decision_trace.final_decision:
                actions = list(decision_trace.final_decision.action_dist.keys())
                probs = list(decision_trace.final_decision.action_dist.values())
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
            if game_state.to_call > 0:
                if random.random() < 0.5:
                    return PlayerAction(action='fold', amount=0)
                else:
                    return PlayerAction(action='call', amount=game_state.to_call)
            else:
                return PlayerAction(action='check', amount=0)


class RandomPlayer(Player):
    """随机策略玩家"""
    def decide(self, game_state: GameState) -> PlayerAction:
        rand = random.random()
        if game_state.to_call <= 0:
            if rand < 0.5:
                return PlayerAction(action='check', amount=0)
            else:
                bet_amount = game_state.pot * 0.6
                return PlayerAction(action='bet', amount=bet_amount)
        else:
            if rand < 0.2:
                return PlayerAction(action='fold', amount=0)
            elif rand < 0.5:
                return PlayerAction(action='call', amount=game_state.to_call)
            else:
                raise_amount = game_state.facing_bet * 5
                return PlayerAction(action='raise', amount=raise_amount)

players = [
    AdvisorV2Player("AI", 0, 100.0),
    RandomPlayer("Random_1", 1, 80.0),
    RandomPlayer("Random_2", 2, 150.0),
]

config = GameConfig(
    num_players=3,
    starting_stack=100.0,
    small_blind=0.5,
    big_blind=1.0,
    verbose=False,
    debug=False
)

game = PokerGame(players, config)
initial_stacks = {"AI": 100.0, "Random_1": 80.0, "Random_2": 150.0}

# Run hands 136-138
seed = 42
random.seed(seed)

for hand_num in [136, 137, 138]:
    btn_seat = (hand_num - 1) % 3

    print(f"\n{'='*80}")
    print(f"Hand #{hand_num}")
    print('='*80)

    players[0].reset_for_new_hand(initial_stacks["AI"])
    players[1].reset_for_new_hand(initial_stacks["Random_1"])
    players[2].reset_for_new_hand(initial_stacks["Random_2"])

    result = game.play_hand(hand_num, btn_seat, seed + hand_num, reset_stacks=False)

    print(f"\nFinal: Pot={result.pot:.1f}BB, Profit sum={sum(result.player_profits):.2f}BB")
