#!/usr/bin/env python
"""
Hand Strength计算

将手牌转换为strength值 (0.0-1.0)，用于GTO决策
"""
from advisor.range_engine import Hand
from advisor.range_engine.cards import Rank


def calculate_preflop_hand_strength(hand: Hand) -> float:
    """
    计算翻前手牌强度

    Args:
        hand: 手牌

    Returns:
        strength值 (0.0-1.0)

    强度标准:
    - 0.95-1.00: AA, KK
    - 0.85-0.95: QQ, JJ, AKs
    - 0.75-0.85: TT, 99, AKo, AQs, AJs
    - 0.65-0.75: 88-22, AQo, KQs, AJo, ATs
    - 0.55-0.65: Suited connectors, suited Ax
    - 0.45-0.55: 中等suited, offsuit broadway
    - < 0.45: 弱牌
    """
    rank1 = hand.cards[0].rank
    rank2 = hand.cards[1].rank

    suited = (hand.cards[0].suit == hand.cards[1].suit)
    is_pair = (rank1 == rank2)

    # 对子
    if is_pair:
        return _pair_strength(rank1)

    # 非对子：高牌和低牌
    high_rank = max(rank1, rank2)
    low_rank = min(rank1, rank2)

    # Ace高张
    if high_rank == Rank.ACE:
        return _ace_high_strength(low_rank, suited)

    # King高张
    if high_rank == Rank.KING:
        return _king_high_strength(low_rank, suited)

    # Queen高张
    if high_rank == Rank.QUEEN:
        return _queen_high_strength(low_rank, suited)

    # Jack高张
    if high_rank == Rank.JACK:
        return _jack_high_strength(low_rank, suited)

    # Ten高张
    if high_rank == Rank.TEN:
        return _ten_high_strength(low_rank, suited)

    # 其他牌
    return _other_strength(high_rank, low_rank, suited)


def _pair_strength(rank: Rank) -> float:
    """对子强度"""
    if rank.value >= 14:  # AA
        return 1.00
    elif rank.value >= 13:  # KK
        return 0.95
    elif rank.value >= 12:  # QQ
        return 0.90
    elif rank.value >= 11:  # JJ
        return 0.87
    elif rank.value >= 10:  # TT
        return 0.82
    elif rank.value >= 9:  # 99
        return 0.77
    elif rank.value >= 8:  # 88
        return 0.72
    elif rank.value >= 7:  # 77
        return 0.69
    elif rank.value >= 6:  # 66
        return 0.67
    elif rank.value >= 5:  # 55
        return 0.65
    elif rank.value >= 4:  # 44
        return 0.63
    elif rank.value >= 3:  # 33
        return 0.62
    else:  # 22
        return 0.61


def _ace_high_strength(low_rank: Rank, suited: bool) -> float:
    """Ace高张强度"""
    if low_rank.value >= 13:  # AK
        return 0.92 if suited else 0.85
    elif low_rank.value >= 12:  # AQ
        return 0.84 if suited else 0.76
    elif low_rank.value >= 11:  # AJ
        return 0.80 if suited else 0.71
    elif low_rank.value >= 10:  # AT
        return 0.76 if suited else 0.67
    elif low_rank.value >= 9:  # A9
        return 0.70 if suited else 0.57
    elif low_rank.value >= 8:  # A8
        return 0.68 if suited else 0.53
    elif low_rank.value >= 7:  # A7
        return 0.66 if suited else 0.50
    elif low_rank.value >= 6:  # A6
        return 0.64 if suited else 0.48
    elif low_rank.value >= 5:  # A5
        return 0.63 if suited else 0.47
    elif low_rank.value >= 4:  # A4
        return 0.62 if suited else 0.45
    elif low_rank.value >= 3:  # A3
        return 0.61 if suited else 0.43
    else:  # A2
        return 0.60 if suited else 0.42


def _king_high_strength(low_rank: Rank, suited: bool) -> float:
    """King高张强度"""
    if low_rank.value >= 12:  # KQ
        return 0.78 if suited else 0.70
    elif low_rank.value >= 11:  # KJ
        return 0.74 if suited else 0.65
    elif low_rank.value >= 10:  # KT
        return 0.70 if suited else 0.61
    elif low_rank.value >= 9:  # K9
        return 0.64 if suited else 0.53
    elif low_rank.value >= 8:  # K8
        return 0.62 if suited else 0.49
    elif low_rank.value >= 7:  # K7
        return 0.60 if suited else 0.46
    else:  # K6-K2
        return 0.58 if suited else 0.42


def _queen_high_strength(low_rank: Rank, suited: bool) -> float:
    """Queen高张强度"""
    if low_rank.value >= 11:  # QJ
        return 0.72 if suited else 0.63
    elif low_rank.value >= 10:  # QT
        return 0.68 if suited else 0.58
    elif low_rank.value >= 9:  # Q9
        return 0.63 if suited else 0.52
    elif low_rank.value >= 8:  # Q8
        return 0.60 if suited else 0.47
    else:  # Q7-Q2
        return 0.56 if suited else 0.40


def _jack_high_strength(low_rank: Rank, suited: bool) -> float:
    """Jack高张强度"""
    if low_rank.value >= 10:  # JT
        return 0.67 if suited else 0.57
    elif low_rank.value >= 9:  # J9
        return 0.62 if suited else 0.51
    elif low_rank.value >= 8:  # J8
        return 0.59 if suited else 0.46
    else:  # J7-J2
        return 0.54 if suited else 0.38


def _ten_high_strength(low_rank: Rank, suited: bool) -> float:
    """Ten高张强度"""
    if low_rank.value >= 9:  # T9
        return 0.65 if suited else 0.54
    elif low_rank.value >= 8:  # T8
        return 0.61 if suited else 0.49
    elif low_rank.value >= 7:  # T7
        return 0.57 if suited else 0.44
    else:  # T6-T2
        return 0.52 if suited else 0.36


def _other_strength(high_rank: Rank, low_rank: Rank, suited: bool) -> float:
    """其他牌强度"""
    # 连张加分
    gap = high_rank.value - low_rank.value
    connector_bonus = 0.05 if gap == 1 else (0.03 if gap == 2 else 0.0)

    # 基础强度
    if high_rank.value >= 9:  # 9高
        base = 0.58 if suited else 0.46
    elif high_rank.value >= 8:  # 8高
        base = 0.54 if suited else 0.42
    elif high_rank.value >= 7:  # 7高
        base = 0.50 if suited else 0.38
    else:  # 6高或更低
        base = 0.45 if suited else 0.34

    return min(0.95, base + connector_bonus)


def get_hand_strength_category(strength: float) -> str:
    """
    将strength转换为类别描述

    Returns:
        'premium', 'strong', 'medium', 'weak', 'trash'
    """
    if strength >= 0.90:
        return 'premium'
    elif strength >= 0.75:
        return 'strong'
    elif strength >= 0.60:
        return 'medium'
    elif strength >= 0.45:
        return 'weak'
    else:
        return 'trash'


if __name__ == '__main__':
    # 测试
    test_hands = [
        ('AsAh', 1.00, 'AA'),
        ('KsKh', 0.95, 'KK'),
        ('QhQd', 0.90, 'QQ'),
        ('JsJh', 0.87, 'JJ'),
        ('AsKs', 0.92, 'AKs'),
        ('AsKh', 0.85, 'AKo'),
        ('7h2d', 0.38, '72o'),
        ('9s8s', 0.66, '98s'),
    ]

    print('Hand Strength测试:')
    print('=' * 60)

    for hand_str, expected, name in test_hands:
        hand = Hand.from_str(hand_str)
        strength = calculate_preflop_hand_strength(hand)
        category = get_hand_strength_category(strength)

        status = '✅' if abs(strength - expected) < 0.05 else '⚠️'
        print(f'{status} {name:6s}: {strength:.3f} (期望 {expected:.3f}) [{category}]')
