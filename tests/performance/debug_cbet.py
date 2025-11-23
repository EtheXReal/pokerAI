"""
调试C-Bet检测逻辑

运行少量手牌并输出详细的action序列和C-bet检测结果
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from poker_env import PokerGame, GameConfig
from advisor_v2.integration.utils import convert_game_result_to_hand_history
from advisor_v2.modeling.tracker import ActionParser
from advisor_v2.modeling.models import parse_street, classify_action, ActionType, StreetType
from styled_players import TAGPlayer, LAGPlayer, NitPlayer, FishPlayer
import random


def debug_cbet_detection(num_hands=20):
    """运行少量手牌并调试C-bet检测"""

    # 创建4个风格玩家（不需要AI）
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

    print(f"{'='*80}")
    print(f"C-Bet Detection Debug - {num_hands} hands")
    print(f"{'='*80}\n")

    cbet_stats = {p.name: {'opportunities': 0, 'cbets': 0} for p in players}

    btn_seat = 0
    for hand_num in range(num_hands):
        result = game.play_hand(hand_num=hand_num+1, btn_seat=btn_seat, seed=42+hand_num)

        # 转换为hand_history
        hand_history = convert_game_result_to_hand_history(result, players)

        print(f"\n{'='*80}")
        print(f"Hand #{hand_num+1} - BTN: {players[result.btn_seat].name}")
        print(f"{'='*80}")

        # 分析每个玩家的行动
        actions = hand_history.get('actions', [])

        # 打印action序列
        print(f"\nAction Sequence:")
        preflop_raiser = None
        saw_flop = False

        for action in actions:
            street = action.get('street', '')
            actor = action.get('actor', '')
            action_str = action.get('action', '')
            amount = action.get('amount', 0)
            to_call = action.get('to_call', 0)

            action_type = classify_action(action_str)

            # 记录翻前加注者
            if street == 'preflop' and action_type in [ActionType.BET, ActionType.RAISE]:
                if preflop_raiser is None:
                    preflop_raiser = actor

            if street == 'flop':
                saw_flop = True

            print(f"  {street:8} | {actor:6} | {action_str:20} | amount={amount:6.2f} | to_call={to_call:6.2f}")

        if not saw_flop:
            print(f"\n  → No flop, skipping C-bet analysis")
            btn_seat = (btn_seat + 1) % 4
            continue

        print(f"\n  Preflop Raiser: {preflop_raiser}")

        # 为每个玩家分析C-bet
        for player_name in [p.name for p in players]:
            hand_result = ActionParser.parse_hand_actions(actions, player_name)

            # 检查是否是翻前加注者
            if player_name == preflop_raiser:
                cbet_stats[player_name]['opportunities'] += 1

                cbet_result = hand_result.cbet_flop
                if cbet_result:
                    cbet_stats[player_name]['cbets'] += 1
                    print(f"  → {player_name} (PFR): C-bet = {cbet_result} ✓")
                else:
                    print(f"  → {player_name} (PFR): C-bet = {cbet_result} ✗")

                # 手动检查flop actions
                flop_actions = [(a.get('actor'), classify_action(a.get('action')), a.get('amount'))
                               for a in actions if a.get('street') == 'flop']
                print(f"     Flop actions: {flop_actions}")

        btn_seat = (btn_seat + 1) % 4

    # 总结C-bet统计
    print(f"\n{'='*80}")
    print(f"C-Bet Summary")
    print(f"{'='*80}\n")

    for player_name, stats in cbet_stats.items():
        opps = stats['opportunities']
        cbets = stats['cbets']
        pct = (cbets / opps * 100) if opps > 0 else 0
        print(f"{player_name:6} - C-bet: {cbets}/{opps} = {pct:.1f}%")


if __name__ == '__main__':
    debug_cbet_detection(num_hands=20)
