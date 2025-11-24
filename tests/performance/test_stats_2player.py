"""
2-Player Statistics Validation Test

使用2人游戏简化测试，验证统计系统是否正确工作。
排除多人游戏的复杂性和样本偏差。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState
from advisor_v2.integration.utils import convert_game_result_to_hand_history
from advisor_v2.modeling.tracker import StatsTracker
from advisor_v2.modeling.classifier import classify_player
from tests.performance.styled_players import create_styled_player
import random
import argparse


def run_2player_test(opponent_style: str, num_hands: int = 500, seed: int = 42):
    """
    运行2人游戏统计测试

    Args:
        opponent_style: 对手风格 ('nit', 'tag', 'lag', 'fish', 'calling_station', 'maniac')
        num_hands: 手牌数量
        seed: 随机种子
    """
    print(f"\n{'='*80}")
    print(f"2-Player Statistics Validation Test")
    print(f"{'='*80}\n")
    print(f"Opponent Style: {opponent_style.upper()}")
    print(f"Hands: {num_hands}")
    print(f"Seed: {seed}\n")

    # 创建玩家
    # 玩家0：简单的TAG玩家（用于对照）
    player0 = create_styled_player('tag', name='Hero', seat=0, stack=100.0)

    # 玩家1：待测试的对手
    player1 = create_styled_player(opponent_style, name='Opponent', seat=1, stack=100.0)

    players = [player0, player1]

    config = GameConfig(
        num_players=2,
        starting_stack=100.0,
        small_blind=0.5,
        big_blind=1.0,
        verbose=False,
        debug=False
    )

    # 设置随机种子
    random.seed(seed)

    # 创建游戏
    game = PokerGame(players, config)

    # 创建统计追踪器
    tracker = StatsTracker()

    # 运行游戏
    print(f"Running {num_hands} hands...")
    btn_seat = 0

    for hand_num in range(num_hands):
        result = game.play_hand(hand_num=hand_num+1, btn_seat=btn_seat, seed=seed+hand_num)

        # 转换为hand_history并更新统计
        hand_history = convert_game_result_to_hand_history(result, players)
        tracker.update_from_hand(hand_history)

        # 进度提示
        if (hand_num + 1) % 100 == 0:
            print(f"  {hand_num + 1}/{num_hands} hands completed")

        # 移动按钮
        btn_seat = (btn_seat + 1) % 2

    print(f"\n{'='*80}")
    print(f"Statistics Results")
    print(f"{'='*80}\n")

    # 获取对手统计
    opponent_stats = tracker.get_stats('Opponent')
    hero_stats = tracker.get_stats('Hero')

    # 显示统计
    print(f"{'Player':<15} {'Hands':>6} {'VPIP':>7} {'PFR':>7} {'AF':>6} {'3-Bet':>7} {'C-Bet':>7} {'WTSD':>7} {'W$SD':>7} {'Fold-Cbet':>10}")
    print(f"{'-'*95}")

    for name, stats in [('Hero', hero_stats), ('Opponent', opponent_stats)]:
        print(f"{name:<15} "
              f"{stats.hands_played:>6} "
              f"{stats.vpip:>6.1%} "
              f"{stats.pfr:>6.1%} "
              f"{stats.af:>6.2f} "
              f"{stats.three_bet_pct:>6.1%} "
              f"{stats.cbet_flop:>6.1%} "
              f"{stats.wtsd:>6.1%} "
              f"{stats.w_sd:>6.1%} "
              f"{stats.fold_to_cbet_flop:>9.1%}")

    print(f"\n{'='*80}")
    print(f"Opponent Analysis")
    print(f"{'='*80}\n")

    # 对手分类
    if opponent_stats.hands_played >= 30:
        classification = classify_player(opponent_stats)
        print(f"Classified as: {classification.player_type.name} (confidence: {classification.confidence:.1%})")
        print(f"Reason: {classification.reason}\n")
    else:
        print(f"Insufficient data for classification ({opponent_stats.hands_played} hands < 30)\n")

    # 期望值对比
    expected_stats = {
        'nit': {'vpip': 0.18, 'pfr': 0.06, 'af': 0.7, 'wtsd': 0.15},
        'tag': {'vpip': 0.22, 'pfr': 0.18, 'af': 3.0, 'wtsd': 0.20},
        'lag': {'vpip': 0.40, 'pfr': 0.28, 'af': 3.0, 'wtsd': 0.35},
        'fish': {'vpip': 0.58, 'pfr': 0.14, 'af': 0.6, 'wtsd': 0.30},
        'calling_station': {'vpip': 0.65, 'pfr': 0.08, 'af': 0.4, 'wtsd': 0.60},
        'maniac': {'vpip': 0.75, 'pfr': 0.60, 'af': 5.0, 'wtsd': 0.45},
    }

    expected = expected_stats.get(opponent_style.lower(), {})

    print(f"Expected vs Actual:")
    print(f"  VPIP: {expected.get('vpip', 0):.1%} vs {opponent_stats.vpip:.1%} " +
          (f"{'✓' if abs(opponent_stats.vpip - expected.get('vpip', 0)) < 0.10 else '✗'}"))
    print(f"  PFR:  {expected.get('pfr', 0):.1%} vs {opponent_stats.pfr:.1%} " +
          (f"{'✓' if abs(opponent_stats.pfr - expected.get('pfr', 0)) < 0.10 else '✗'}"))
    print(f"  AF:   {expected.get('af', 0):.2f} vs {opponent_stats.af:.2f}")
    print(f"  WTSD: {expected.get('wtsd', 0):.1%} vs {opponent_stats.wtsd:.1%}")

    # 关键指标验证
    print(f"\n{'='*80}")
    print(f"Key Metrics Validation")
    print(f"{'='*80}\n")

    # 检查计数器
    print(f"Internal Counters:")
    print(f"  Opponent _vpip_opportunities: {opponent_stats._vpip_opportunities}")
    print(f"  Opponent _pfr_opportunities: {opponent_stats._pfr_opportunities}")
    print(f"  Opponent _cbet_opportunities: {opponent_stats._cbet_opportunities}")
    print(f"  Opponent _faced_cbet_count: {opponent_stats._faced_cbet_count}")
    print(f"  Opponent _saw_flop_count: {opponent_stats._saw_flop_count}")
    print(f"  Opponent _showdown_count: {opponent_stats._showdown_count}")

    print(f"\n  Hero _vpip_opportunities: {hero_stats._vpip_opportunities}")
    print(f"  Hero _pfr_opportunities: {hero_stats._pfr_opportunities}")
    print(f"  Hero _cbet_opportunities: {hero_stats._cbet_opportunities}")
    print(f"  Hero _faced_cbet_count: {hero_stats._faced_cbet_count}")
    print(f"  Hero _saw_flop_count: {hero_stats._saw_flop_count}")
    print(f"  Hero _showdown_count: {hero_stats._showdown_count}")

    # 数据合理性检查
    print(f"\nData Sanity Checks:")
    checks_passed = 0
    checks_total = 0

    def check(condition, description):
        nonlocal checks_passed, checks_total
        checks_total += 1
        status = "✓" if condition else "✗"
        print(f"  {status} {description}")
        if condition:
            checks_passed += 1

    check(opponent_stats.hands_played == num_hands, f"Hands played = {num_hands}")
    check(hero_stats.hands_played == num_hands, f"Hero hands played = {num_hands}")
    check(opponent_stats._vpip_opportunities == num_hands, f"VPIP opportunities = hands")
    check(opponent_stats._pfr_opportunities == num_hands, f"PFR opportunities = hands")
    check(opponent_stats.pfr <= opponent_stats.vpip, "PFR <= VPIP")
    check(hero_stats.pfr <= hero_stats.vpip, "Hero PFR <= VPIP")
    check(opponent_stats._showdown_count <= opponent_stats._saw_flop_count, "Showdown <= Saw flop")
    check(opponent_stats._faced_cbet_count > 0, "Faced C-bet count > 0 (有数据)")
    check(opponent_stats._cbet_opportunities > 0, "C-bet opportunities > 0 (有数据)")

    print(f"\nChecks Passed: {checks_passed}/{checks_total}")

    return tracker, opponent_stats, hero_stats


def main():
    parser = argparse.ArgumentParser(description='2-Player Statistics Validation Test')
    parser.add_argument('--style', type=str, default='fish',
                       choices=['nit', 'tag', 'lag', 'fish', 'calling_station', 'maniac'],
                       help='Opponent style to test')
    parser.add_argument('--hands', type=int, default=500,
                       help='Number of hands to play (default: 500)')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed (default: 42)')

    args = parser.parse_args()

    run_2player_test(args.style, args.hands, args.seed)


if __name__ == '__main__':
    main()
