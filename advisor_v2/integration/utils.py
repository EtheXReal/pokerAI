"""
Integration Utilities

提供GameResult到StatsTracker所需hand_history格式的转换工具
"""
from typing import Dict, List, Any
from poker_env.betting_round import ActionRecord


def convert_game_result_to_hand_history(game_result: 'GameResult', players: List['Player']) -> Dict[str, Any]:
    """
    将poker_env.GameResult转换为StatsTracker.update_from_hand()所需的格式

    Args:
        game_result: poker_env返回的GameResult对象
        players: 玩家列表（用于获取名字和座位映射）

    Returns:
        hand_history字典，格式为：
        {
            'hand_id': str,
            'players': [{'id': str, 'position': str, 'stack_start': float}, ...],
            'actions': [{'street': str, 'actor': str, 'action': str, 'amount': float}, ...],
            'winners': [{'seat': str, 'amount': float}, ...],
            'showdown': bool
        }
    """
    # 构建玩家列表
    players_data = []
    for player in players:
        players_data.append({
            'id': player.name,  # 使用玩家名字作为ID
            'seat': player.seat,
            'position': _get_position_name(player.seat, game_result.btn_seat, len(players)),
            'stack_start': 100.0,  # 简化：假设起始筹码（实际值在player对象中）
        })

    # 转换actions
    actions_data = []
    for action_record in game_result.actions:
        # ActionRecord包含: street, player_name, player_seat, action, amount, pot_after, to_call
        actions_data.append({
            'street': action_record.street,
            'actor': action_record.player_name,
            'action': action_record.action,
            'amount': action_record.amount,
            'pot_before': action_record.pot_after - action_record.amount,  # 近似
            'to_call': action_record.to_call,  # 使用ActionRecord中实际的to_call值
        })

    # 构建winners列表
    winners_data = []
    for seat in game_result.winner_seats:
        player_name = players[seat].name
        # 计算该玩家的盈利
        profit = game_result.player_profits[seat]
        # 如果赢了，amount是pot的一部分
        if profit > 0:
            winners_data.append({
                'seat': player_name,
                'amount': profit + players[seat].invested  # 赢得的总额
            })

    # 构建hand_history
    hand_history = {
        'hand_id': f"hand_{game_result.hand_num}",
        'players': players_data,
        'actions': actions_data,
        'winners': winners_data,
        'showdown': game_result.showdown,
    }

    return hand_history


def _get_position_name(seat: int, btn_seat: int, num_players: int) -> str:
    """
    获取位置名称

    Args:
        seat: 座位索引
        btn_seat: 庄家座位索引
        num_players: 玩家数量

    Returns:
        位置名称 (BTN, SB, BB, UTG, MP, CO)
    """
    offset = (seat - btn_seat) % num_players

    if num_players == 2:
        return 'BTN' if offset == 0 else 'BB'
    elif num_players == 3:
        if offset == 0:
            return 'BTN'
        elif offset == 1:
            return 'SB'
        else:
            return 'BB'
    else:
        # 4+人游戏
        if offset == 0:
            return 'BTN'
        elif offset == 1:
            return 'SB'
        elif offset == 2:
            return 'BB'
        elif offset == 3:
            return 'UTG'
        elif offset == num_players - 1:
            return 'CO'
        else:
            return 'MP'


def print_opponent_stats_report(tracker: 'StatsTracker', player_names: List[str]) -> None:
    """
    打印对手风格统计报告

    Args:
        tracker: StatsTracker实例
        player_names: 对手玩家名字列表
    """
    from advisor_v2.modeling import PlayerClassifier

    classifier = PlayerClassifier()

    print("\n" + "=" * 80)
    print("Opponent Modeling Report")
    print("=" * 80)

    for player_name in player_names:
        stats = tracker.get_stats(player_name)

        if stats.hands_played < 5:
            print(f"\n{player_name}: Insufficient data ({stats.hands_played} hands)")
            continue

        # 分类对手类型
        if stats.hands_played >= 20:
            classification_result = classifier.classify(stats)
            player_type = classification_result.player_type.value
            confidence = classification_result.confidence
        else:
            player_type = "UNKNOWN"
            confidence = 0.0

        print(f"\n{player_name}:")
        print(f"  Player Type: {player_type} (confidence: {confidence:.1%})")
        print(f"  Hands Played: {stats.hands_played}")
        print(f"  VPIP: {stats.vpip:.1%}")
        print(f"  PFR: {stats.pfr:.1%}")
        print(f"  Aggression Factor: {stats.af:.2f}")
        print(f"  3-Bet: {stats.three_bet_pct:.1%}")
        print(f"  C-Bet Flop: {stats.cbet_flop:.1%}")
        print(f"  Fold to C-Bet Flop: {stats.fold_to_cbet_flop:.1%}")
        print(f"  WTSD: {stats.wtsd:.1%}")
        print(f"  W$SD: {stats.w_sd:.1%}")

    print("\n" + "=" * 80)
