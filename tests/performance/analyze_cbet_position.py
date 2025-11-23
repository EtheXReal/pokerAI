"""
分析C-bet机会中PFR是否第一个行动

看看有多少C-bet机会实际上允许PFR第一个下注
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from poker_env import PokerGame, GameConfig
from advisor_v2.integration.utils import convert_game_result_to_hand_history
from advisor_v2.modeling.models import classify_action, ActionType
from styled_players import TAGPlayer, LAGPlayer, NitPlayer, FishPlayer
import random


def analyze_cbet_action_order(num_hands=200):
    """分析C-bet机会中谁先行动"""

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
        'player_cbet_opps': {p.name: 0 for p in players},  # PFR看到翻牌
        'player_first_to_act': {p.name: 0 for p in players},  # PFR第一个行动
        'player_faced_bet': {p.name: 0 for p in players},  # PFR面对下注
    }

    btn_seat = 0
    for hand_num in range(num_hands):
        result = game.play_hand(hand_num=hand_num+1, btn_seat=btn_seat, seed=42+hand_num)

        # 转换为hand_history
        hand_history = convert_game_result_to_hand_history(result, players)
        actions = hand_history.get('actions', [])

        # 找翻前加注者
        preflop_raiser = None
        for action in actions:
            if action.get('street') == 'preflop':
                action_type = classify_action(action.get('action', ''))
                if action_type in [ActionType.BET, ActionType.RAISE]:
                    preflop_raiser = action.get('actor')

        # 检查翻牌圈行动
        if preflop_raiser:
            flop_actions = [a for a in actions if a.get('street') == 'flop']

            if len(flop_actions) > 0:
                # PFR看到翻牌
                stats['player_cbet_opps'][preflop_raiser] += 1

                # 检查第一个BET/RAISE是谁
                first_bettor = None
                for action in flop_actions:
                    actor = action.get('actor')
                    action_type = classify_action(action.get('action', ''))

                    # 跳过check，找第一个bet/raise
                    if action_type in [ActionType.BET, ActionType.RAISE]:
                        first_bettor = actor
                        break

                # 统计: PFR是否有机会第一个下注
                if first_bettor == preflop_raiser:
                    # PFR第一个下注 = 实际C-bet
                    stats['player_first_to_act'][preflop_raiser] += 1
                elif first_bettor is None:
                    # 所有人都check = PFR有机会但选择不bet
                    stats['player_first_to_act'][preflop_raiser] += 1
                else:
                    # 别人先下注 = PFR面对下注，无法C-bet
                    stats['player_faced_bet'][preflop_raiser] += 1

        btn_seat = (btn_seat + 1) % 4

    # 打印统计
    print(f"{'='*80}")
    print(f"C-Bet Action Order Analysis - {num_hands} hands")
    print(f"{'='*80}\\n")

    for player_name in ['TAG', 'LAG', 'Nit', 'Fish']:
        opps = stats['player_cbet_opps'][player_name]
        first = stats['player_first_to_act'][player_name]
        faced = stats['player_faced_bet'][player_name]

        first_pct = (first / opps * 100) if opps > 0 else 0
        faced_pct = (faced / opps * 100) if opps > 0 else 0

        print(f"{player_name:6}:")
        print(f"  Total C-bet opportunities: {opps}")
        print(f"  First to act: {first:3} ({first_pct:5.1f}%)")
        print(f"  Faced bet/action: {faced:3} ({faced_pct:5.1f}%)")
        print()


if __name__ == '__main__':
    analyze_cbet_action_order(num_hands=200)
