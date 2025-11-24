import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.performance import five_player_classify_test as test_module
import random

random.seed(42)
players, all_stats = test_module.run_test(num_hands=200, seed=42, verbose=False)

ai_stats = all_stats['AI']
print(f'AI PFR opportunities: {ai_stats._pfr_opportunities}')
print(f'AI PFR count: {int(ai_stats.pfr * ai_stats._pfr_opportunities)}')
print(f'AI C-bet opportunities: {ai_stats._cbet_opportunities}')
print(f'AI C-bet frequency: {ai_stats.cbet_flop:.1%}')
print(f'AI saw_flop count: {ai_stats._saw_flop_count}')
