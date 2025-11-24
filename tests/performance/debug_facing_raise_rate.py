"""Check how often Fish faces a raise from BB"""
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

# Track Fish's game states
btn_decisions = []
bb_no_raise = []
bb_facing_raise = []

original_decide = fish.decide

def capture_decide(game_state):
    decision = original_decide(game_state)

    if game_state.street == 'preflop':
        facing_raise = game_state.facing_bet > 1.0

        if game_state.to_call == 0.5:
            # Button (SB)
            btn_decisions.append(decision.action != 'fold')
        elif not facing_raise:
            # BB, no raise
            bb_no_raise.append(decision.action in ['bet', 'raise', 'call'])
        else:
            # BB, facing raise
            bb_facing_raise.append(decision.action != 'fold')

    return decision

fish.decide = capture_decide

# Run 500 hands
random.seed(42)
game = PokerGame(players, config)

for i in range(500):
    btn_seat = i % 2
    result = game.play_hand(hand_num=i+1, btn_seat=btn_seat, seed=42+i)

print(f"Fish from Button: {sum(btn_decisions)}/{len(btn_decisions)} = {sum(btn_decisions)/len(btn_decisions)*100:.1f}% VPIP")
print(f"Fish from BB (no raise): {sum(bb_no_raise)}/{len(bb_no_raise)} = {sum(bb_no_raise)/len(bb_no_raise)*100 if bb_no_raise else 0:.1f}% VPIP")
print(f"Fish from BB (facing raise): {sum(bb_facing_raise)}/{len(bb_facing_raise)} = {sum(bb_facing_raise)/len(bb_facing_raise)*100:.1f}% VPIP")

print(f"\nTAG raised from Button: {len(bb_facing_raise)}/{len(bb_facing_raise) + len(bb_no_raise)} = {len(bb_facing_raise)/(len(bb_facing_raise) + len(bb_no_raise))*100:.1f}% of the time")

# Calculate combined VPIP
total_vpip_hands = sum(btn_decisions) + sum(bb_no_raise) + sum(bb_facing_raise)
total_hands = len(btn_decisions) + len(bb_no_raise) + len(bb_facing_raise)
print(f"\nFish overall VPIP: {total_vpip_hands}/{total_hands} = {total_vpip_hands/total_hands*100:.1f}%")
print(f"Expected: ~56-58%")
