#!/usr/bin/env python3
"""Debug side pot calculation with detailed logging"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState
import random


# Simple test player
class SimplePlayer(Player):
    """Simple player for testing"""
    def decide(self, game_state: GameState) -> PlayerAction:
        if game_state.to_call > 0:
            if random.random() < 0.5:
                return PlayerAction('call', game_state.to_call)
            else:
                return PlayerAction('fold', 0)
        else:
            return PlayerAction('check', 0)


# Test specific scenario that might cause issues
players = [
    SimplePlayer("P0", 0, 100.0),
    SimplePlayer("P1", 1, 80.0),
    SimplePlayer("P2", 2, 150.0),
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
initial_stacks = {"P0": 100.0, "P1": 80.0, "P2": 150.0}

# Run many hands to find the error
seed = 42
error_hands = []

print("Running hands to find validation errors...")
for hand_num in range(1, 200):
    players[0].reset_for_new_hand(initial_stacks["P0"])
    players[1].reset_for_new_hand(initial_stacks["P1"])
    players[2].reset_for_new_hand(initial_stacks["P2"])

    btn_seat = (hand_num - 1) % 3
    result = game.play_hand(hand_num, btn_seat, seed + hand_num, reset_stacks=False)

    # Check zero-sum
    profit_sum = sum(result.player_profits)
    if abs(profit_sum) > 0.01:
        error_hands.append(hand_num)
        print(f"Hand #{hand_num}: ERROR - profit sum = {profit_sum:.2f}BB")

print(f"\nFound {len(error_hands)} hands with errors: {error_hands}")
