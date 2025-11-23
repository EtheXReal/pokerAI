"""
快速测试VPIP - 检查面对BB vs 面对raise的逻辑
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from poker_env import PokerGame, GameConfig
from styled_players import TAGPlayer, LAGPlayer, NitPlayer, FishPlayer
import random

players = [
    TAGPlayer("TAG", 0, 200.0),
    LAGPlayer("LAG", 1, 200.0),
    NitPlayer("Nit", 2, 200.0),
    FishPlayer("Fish", 3, 200.0),
]

config = GameConfig(
    num_players=4,
    starting_stack=200.0,
    small_blind=0.5,
    big_blind=1.0,
    verbose=False,
    debug=False
)

random.seed(42)
game = PokerGame(players, config)

btn_seat = 0
for i in range(100):
    result = game.play_hand(hand_num=i+1, btn_seat=btn_seat, seed=42+i)
    btn_seat = (btn_seat + 1) % 4

# 打印VPIP/PFR
from advisor_v2.integration.utils import convert_game_result_to_hand_history
from advisor_v2.modeling.tracker import StatsTracker

tracker = StatsTracker()

# 重新运行并收集统计
random.seed(42)
game2 = PokerGame(players, config)
btn_seat = 0
for i in range(100):
    result = game2.play_hand(hand_num=i+1, btn_seat=btn_seat, seed=42+i)
    hand_history = convert_game_result_to_hand_history(result, players)
    tracker.update_from_hand(hand_history)
    btn_seat = (btn_seat + 1) % 4

all_stats = tracker.get_all_stats()
for name in ['TAG', 'LAG', 'Nit', 'Fish']:
    stats = all_stats.get(name)
    if stats:
        print(f"{name}: VPIP={stats.vpip:.1%}, PFR={stats.pfr:.1%}, hands={stats.hands_played}")
