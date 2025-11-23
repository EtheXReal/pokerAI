"""
分析3-bet情况 - 区分facing BB vs facing raise
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from poker_env import PokerGame, GameConfig
from advisor_v2.integration.utils import convert_game_result_to_hand_history
from advisor_v2.modeling.tracker import ActionParser
from advisor_v2.modeling.models import classify_action, ActionType
from styled_players import TAGPlayer, LAGPlayer, NitPlayer, FishPlayer
import random


def analyze_3bet_contexts(num_hands=500):
    """分析3-bet发生在什么情况下"""

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

    stats = {
        'player_faced_raise': {p.name: 0 for p in players},  # 面对真正的raise
        'player_faced_bb_only': {p.name: 0 for p in players},  # 只面对BB（可以open）
        'player_3bet_vs_raise': {p.name: 0 for p in players},  # 面对raise时3-bet
        'player_raise_vs_bb': {p.name: 0 for p in players},  # 面对BB时raise（open）
    }

    btn_seat = 0
    for hand_num in range(num_hands):
        result = game.play_hand(hand_num=hand_num+1, btn_seat=btn_seat, seed=42+hand_num)

        # 转换为hand_history
        hand_history = convert_game_result_to_hand_history(result, players)
        actions = hand_history.get('actions', [])

        # 分析翻前行动
        preflop_actions = [a for a in actions if a.get('street') == 'preflop']

        # 追踪每个玩家的情况
        for player_name in [p.name for p in players]:
            # 找到该玩家的第一个行动
            player_actions = [a for a in preflop_actions if a.get('actor') == player_name]
            if not player_actions:
                continue

            first_action = player_actions[0]
            action_str = first_action.get('action', '')
            action_type = classify_action(action_str)

            # 在该玩家行动前，有多少次raise
            actions_before = []
            for a in preflop_actions:
                if a.get('actor') == player_name:
                    break
                actions_before.append(a)

            raise_count_before = sum(1 for a in actions_before
                                    if classify_action(a.get('action', '')) in [ActionType.BET, ActionType.RAISE])

            # 分类情况
            if raise_count_before == 0:
                # 没有人raise，玩家可以open
                if action_type in [ActionType.BET, ActionType.RAISE]:
                    stats['player_raise_vs_bb'][player_name] += 1
            elif raise_count_before == 1:
                # 有一次raise，玩家面对raise
                stats['player_faced_raise'][player_name] += 1
                if action_type in [ActionType.RAISE]:
                    stats['player_3bet_vs_raise'][player_name] += 1
            # raise_count_before >= 2 意味着已经有3-bet或4-bet，我们暂时忽略

        btn_seat = (btn_seat + 1) % 4

    # 打印统计
    print(f"{'='*80}")
    print(f"3-Bet Context Analysis - {num_hands} hands")
    print(f"{'='*80}\n")

    for player_name in ['TAG', 'LAG', 'Nit', 'Fish']:
        faced_raise = stats['player_faced_raise'][player_name]
        threebet = stats['player_3bet_vs_raise'][player_name]
        open_raise = stats['player_raise_vs_bb'][player_name]

        threebet_pct = (threebet / faced_raise * 100) if faced_raise > 0 else 0

        print(f"{player_name:6}:")
        print(f"  Times faced raise: {faced_raise}")
        print(f"  3-bet when facing raise: {threebet} ({threebet_pct:.1f}%)")
        print(f"  Open raises (no prior raise): {open_raise}")
        print()


if __name__ == '__main__':
    analyze_3bet_contexts(num_hands=500)
