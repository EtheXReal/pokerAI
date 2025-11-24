"""Debug game state values in 2-player poker"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from poker_env import PokerGame, GameConfig
from tests.performance.styled_players import create_styled_player
import random

# Create players
fish = create_styled_player('fish', 'Fish', 0, 100.0)
tag = create_styled_player('tag', 'TAG', 1, 100.0)

players = [fish, tag]

config = GameConfig(
    num_players=2,
    starting_stack=100.0,
    small_blind=0.5,
    big_blind=1.0,
    verbose=False,
    debug=False
)

# Hook into Fish to see game states
fish_states = []
original_decide = fish.decide

def capture_decide(game_state):
    fish_states.append({
        'to_call': game_state.to_call,
        'facing_bet': game_state.facing_bet,
        'pot': game_state.pot,
        'street': game_state.street,
        'num_active': game_state.num_active_players
    })
    return original_decide(game_state)

fish.decide = capture_decide

# Play 2 hands to see both positions
random.seed(42)
game = PokerGame(players, config)

# Hand 1: Fish on Button (seat 0)
print("=== Hand 1: Fish on Button (SB) ===")
result1 = game.play_hand(hand_num=1, btn_seat=0, seed=42)
print(f"Fish states in hand 1:")
for i, state in enumerate(fish_states):
    print(f"  Decision {i+1}: to_call={state['to_call']}, facing_bet={state['facing_bet']}, pot={state['pot']}, street={state['street']}, num_active={state['num_active']}")

fish_states.clear()

# Hand 2: Fish in BB (seat 0, button is seat 1)
print("\n=== Hand 2: Fish in BB ===")
result2 = game.play_hand(hand_num=2, btn_seat=1, seed=43)
print(f"Fish states in hand 2:")
for i, state in enumerate(fish_states):
    print(f"  Decision {i+1}: to_call={state['to_call']}, facing_bet={state['facing_bet']}, pot={state['pot']}, street={state['street']}, num_active={state['num_active']}")
