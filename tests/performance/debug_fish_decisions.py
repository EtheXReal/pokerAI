"""Debug Fish player decisions in 2-player game"""
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

random.seed(42)
game = PokerGame(players, config)

# Track decisions by position
btn_vpip = 0
btn_total = 0
bb_vpip = 0
bb_total = 0

# Custom tracking - hook into Fish player
original_decide = fish.decide

def tracked_decide(game_state):
    """Track Fish's decisions"""
    global btn_vpip, btn_total, bb_vpip, bb_total

    is_btn = (game_state.to_call == 0.5)  # Button posts SB
    is_bb = (game_state.to_call == 0)     # BB can check

    decision = original_decide(game_state)

    if is_btn:
        btn_total += 1
        if decision.action != 'fold':
            btn_vpip += 1
    elif is_bb and not (game_state.facing_bet > 1.0):
        # BB without facing raise
        bb_total += 1
        # In BB, if we bet or raise, that's VPIP. Check is not VPIP.
        if decision.action in ['bet', 'raise']:
            bb_vpip += 1

    return decision

fish.decide = tracked_decide

# Run 100 hands
for i in range(100):
    btn_seat = i % 2
    result = game.play_hand(hand_num=i+1, btn_seat=btn_seat, seed=42+i)

print(f"Fish decisions from Button (SB): {btn_vpip}/{btn_total} = {btn_vpip/btn_total*100:.1f}% VPIP")
print(f"Fish decisions from BB (no raise): {bb_vpip}/{bb_total} = {bb_vpip/bb_total*100 if bb_total > 0 else 0:.1f}% VPIP")
print(f"\nExpected from Button: 58%")
print(f"Expected overall: ~56-58%")
