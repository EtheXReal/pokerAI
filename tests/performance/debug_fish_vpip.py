"""Debug script to test Fish VPIP decision logic"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from styled_players import create_styled_player
from poker_env import GameState
import random

# Create a Fish player
fish = create_styled_player('fish', 'Fish', 0, 100.0)

# Test Button (SB) decisions in 2-player
random.seed(42)
vpip_btn = 0
pfr_btn = 0

print("Testing Fish from Button (SB) in 2-player...")
for i in range(1000):
    # Button in 2-player: to_call = 0.5, facing_bet = 0.5
    state = GameState(
        hero_seat=0,
        hero_stack=100.0,
        street='preflop',
        pot=1.5,
        to_call=0.5,
        facing_bet=0.5,
        community_cards=[],
        hole_cards=['Ah', 'Kh'],
        player_stacks=[100.0, 100.0],
        player_committed=[0.5, 1.0],
        active_players=[0, 1],
        current_bets=[0.5, 1.0],
    )

    decision = fish.decide(state)
    if decision.action != 'fold':
        vpip_btn += 1
        if decision.action in ['bet', 'raise']:
            pfr_btn += 1

print(f"Button VPIP: {vpip_btn/10:.1f}% (expected 58%)")
print(f"Button PFR: {pfr_btn/10:.1f}%\n")

# Test BB decisions in 2-player
random.seed(42)
vpip_bb = 0
pfr_bb = 0

print("Testing Fish from BB in 2-player...")
for i in range(1000):
    # BB in 2-player facing Button raise: to_call = some amount > 0
    # Let's say Button raised to 3BB
    state = GameState(
        hero_seat=1,
        hero_stack=99.0,  # Already posted 1BB
        street='preflop',
        pot=4.0,  # 3 (raise) + 1 (BB)
        to_call=2.0,  # Need to call 2 more (3 total - 1 already in)
        facing_bet=3.0,
        community_cards=[],
        hole_cards=['Ah', 'Kh'],
        player_stacks=[97.0, 99.0],
        player_committed=[3.0, 1.0],
        active_players=[0, 1],
        current_bets=[3.0, 1.0],
    )

    decision = fish.decide(state)
    if decision.action != 'fold':
        vpip_bb += 1
        if decision.action in ['bet', 'raise']:
            pfr_bb += 1

print(f"BB VPIP facing raise: {vpip_bb/10:.1f}%")
print(f"BB 3-bet%: {pfr_bb/10:.1f}%\n")

# Combined VPIP (average of BTN and BB)
combined_vpip = (vpip_btn + vpip_bb) / 20
print(f"Combined VPIP (average): {combined_vpip:.1f}% (expected 58%)")
