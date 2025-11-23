"""
分析C-Bet机会出现的频率

看看为什么C-bet统计这么低
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


def analyze_cbet_opportunities(num_hands=200):
    """分析C-bet机会"""

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
        'total_hands': 0,
        'saw_flop': 0,
        'has_pfr': 0,  # 有翻前加注者
        'pfr_saw_flop': 0,  # 翻前加注者看到翻牌
        'player_cbet_opps': {p.name: 0 for p in players},
        'player_cbets': {p.name: 0 for p in players},
        'player_was_pfr': {p.name: 0 for p in players},
    }

    btn_seat = 0
    for hand_num in range(num_hands):
        result = game.play_hand(hand_num=hand_num+1, btn_seat=btn_seat, seed=42+hand_num)
        stats['total_hands'] += 1

        # 转换为hand_history
        hand_history = convert_game_result_to_hand_history(result, players)
        actions = hand_history.get('actions', [])

        # 检查是否看到flop
        saw_flop = any(a.get('street') == 'flop' for a in actions)
        if saw_flop:
            stats['saw_flop'] += 1

        # 找翻前加注者
        preflop_raiser = None
        for action in actions:
            if action.get('street') == 'preflop':
                action_type = classify_action(action.get('action', ''))
                if action_type in [ActionType.BET, ActionType.RAISE]:
                    preflop_raiser = action.get('actor')

        if preflop_raiser:
            stats['has_pfr'] += 1
            stats['player_was_pfr'][preflop_raiser] += 1

            if saw_flop:
                stats['pfr_saw_flop'] += 1

        # 为每个玩家分析
        for player_name in [p.name for p in players]:
            hand_result = ActionParser.parse_hand_actions(actions, player_name)

            if player_name == preflop_raiser and saw_flop:
                stats['player_cbet_opps'][player_name] += 1

                if hand_result.cbet_flop:
                    stats['player_cbets'][player_name] += 1

        btn_seat = (btn_seat + 1) % 4

    # 打印统计
    print(f"{'='*80}")
    print(f"C-Bet Opportunity Analysis - {num_hands} hands")
    print(f"{'='*80}\n")

    print(f"Total hands: {stats['total_hands']}")
    print(f"Hands that saw flop: {stats['saw_flop']} ({stats['saw_flop']/stats['total_hands']*100:.1f}%)")
    print(f"Hands with PFR: {stats['has_pfr']} ({stats['has_pfr']/stats['total_hands']*100:.1f}%)")
    print(f"PFR saw flop: {stats['pfr_saw_flop']} ({stats['pfr_saw_flop']/stats['total_hands']*100:.1f}%)")
    print()

    print(f"Player PFR Stats:")
    for player_name in ['TAG', 'LAG', 'Nit', 'Fish']:
        pfr_count = stats['player_was_pfr'][player_name]
        print(f"  {player_name:6} was PFR: {pfr_count} times ({pfr_count/stats['total_hands']*100:.1f}%)")
    print()

    print(f"C-Bet Stats:")
    for player_name in ['TAG', 'LAG', 'Nit', 'Fish']:
        opps = stats['player_cbet_opps'][player_name]
        cbets = stats['player_cbets'][player_name]
        pct = (cbets / opps * 100) if opps > 0 else 0
        print(f"  {player_name:6} C-bet: {cbets:3}/{opps:3} = {pct:5.1f}%")


if __name__ == '__main__':
    analyze_cbet_opportunities(num_hands=200)
