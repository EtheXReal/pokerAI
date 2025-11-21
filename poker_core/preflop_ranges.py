"""
5人桌翻前范围表定义
参考标准GTO范围和职业玩家经验

范围紧度分级:
- tight: 保守型 (~15% VPIP)
- normal: 标准GTO (~22% VPIP)
- loose: 激进型 (~28% VPIP)
"""

# ===== 手牌表示说明 =====
# 使用标准范围字符串:
# - "AA", "KK" 等: 口袋对
# - "AKs": suited combo (同花)
# - "AKo": offsuit combo (非同花)
# - "A5s+": A5s, A6s, ..., AKs
# - "77+": 77, 88, ..., AA
# - "ATo+": ATo, AJo, AQo, AKo

# ===== UTG (Under The Gun) 范围 =====
# 最紧位置，5人桌占20%

UTG_OPEN_RANGES = {
    'tight': {
        'pairs': ['77+'],           # 77-AA (6.3% combos)
        'suited': ['A9s+', 'KTs+', 'QJs'],  # ~3.3%
        'offsuit': ['AJo+', 'KQo'],  # ~2.7%
        # 总计: ~12.3%
    },
    'normal': {
        'pairs': ['55+'],           # 55-AA (11.3%)
        'suited': ['A2s+', 'K9s+', 'Q9s+', 'JTs'],  # ~12.1%
        'offsuit': ['ATo+', 'KJo+'],  # ~4.8%
        # 总计: ~28%
    },
    'loose': {
        'pairs': ['55+'],           # 55-AA (11.3%)
        'suited': ['A2s+', 'K9s+', 'Q9s+', 'J9s+', 'T8s+', '98s'],  # ~12.5%
        'offsuit': ['A9o+', 'KTo+', 'QJo'],  # ~8.1%
        # 总计: ~31.9%
    }
}

# ===== MP (Middle Position) 范围 =====
# CO前一位，5人桌相当于HJ

MP_OPEN_RANGES = {
    'tight': {
        'pairs': ['66+'],
        'suited': ['A8s+', 'K9s+', 'QTs+', 'JTs'],
        'offsuit': ['ATo+', 'KQo'],
        # 总计: ~16.5%
    },
    'normal': {
        'pairs': ['55+'],
        'suited': ['A4s+', 'K9s+', 'Q9s+', 'J9s+', 'T9s'],
        'offsuit': ['A9o+', 'KTo+', 'QJo'],
        # 总计: ~26.3%
    },
    'loose': {
        'pairs': ['44+'],
        'suited': ['A2s+', 'K7s+', 'Q8s+', 'J8s+', 'T8s+', '97s+', '87s'],
        'offsuit': ['A8o+', 'K9o+', 'QTo+', 'JTo'],
        # 总计: ~37.5%
    }
}

# ===== CO (Cutoff) 范围 =====
# BTN前一位，位置优势明显

CO_OPEN_RANGES = {
    'tight': {
        'pairs': ['55+'],
        'suited': ['A5s+', 'K9s+', 'Q9s+', 'J9s+', 'T9s'],
        'offsuit': ['A9o+', 'KTo+', 'QJo'],
        # 总计: ~22.5%
    },
    'normal': {
        'pairs': ['44+'],
        'suited': ['A2s+', 'K8s+', 'Q9s+', 'J8s+', 'T8s+', '98s'],
        'offsuit': ['A8o+', 'K9o+', 'QTo+', 'JTo'],
        # 总计: ~32.8%
    },
    'loose': {
        'pairs': ['33+'],
        'suited': ['A2s+', 'K6s+', 'Q7s+', 'J7s+', 'T7s+', '97s+', '86s+', '76s'],
        'offsuit': ['A7o+', 'K8o+', 'Q9o+', 'J9o+', 'T9o'],
        # 总计: ~44.2%
    }
}

# ===== BTN (Button) 范围 =====
# 最佳位置，可以玩最宽范围

BTN_OPEN_RANGES = {
    'tight': {
        'pairs': ['44+'],
        'suited': ['A2s+', 'K8s+', 'Q9s+', 'J8s+', 'T8s+', '98s'],
        'offsuit': ['A8o+', 'K9o+', 'QTo+', 'JTo'],
        # 总计: ~28.5%
    },
    'normal': {
        'pairs': ['22+'],
        'suited': ['A2s+', 'K5s+', 'Q7s+', 'J7s+', 'T7s+', '97s+', '86s+', '76s', '65s'],
        'offsuit': ['A5o+', 'K8o+', 'Q9o+', 'J9o+', 'T8o+', '98o'],
        # 总计: ~46.8%
    },
    'loose': {
        'pairs': ['22+'],
        'suited': ['A2s+', 'K2s+', 'Q4s+', 'J6s+', 'T6s+', '96s+', '85s+', '75s+', '65s', '54s'],
        'offsuit': ['A2o+', 'K7o+', 'Q8o+', 'J8o+', 'T8o+', '98o'],
        # 总计: ~58.3%
    }
}

# ===== SB (Small Blind) 范围 =====
# vs BB，位置不利但已投入0.5BB

SB_OPEN_RANGES = {
    'tight': {
        'pairs': ['55+'],
        'suited': ['A4s+', 'K9s+', 'Q9s+', 'J9s+', 'T9s'],
        'offsuit': ['A8o+', 'KTo+', 'QJo'],
        # 总计: ~24.3%
    },
    'normal': {
        'pairs': ['33+'],
        'suited': ['A2s+', 'K6s+', 'Q8s+', 'J8s+', 'T8s+', '97s+', '87s'],
        'offsuit': ['A6o+', 'K9o+', 'Q9o+', 'JTo'],
        # 总计: ~38.7%
    },
    'loose': {
        'pairs': ['22+'],
        'suited': ['A2s+', 'K4s+', 'Q6s+', 'J6s+', 'T7s+', '96s+', '86s+', '76s', '65s'],
        'offsuit': ['A4o+', 'K7o+', 'Q8o+', 'J8o+', 'T8o+', '98o'],
        # 总计: ~51.5%
    }
}

# ===== BB (Big Blind) 范围 =====
# 被动跟注，已投入1BB，价格好

BB_CALL_RANGES = {
    # vs BTN open
    'vs_btn_tight': {
        'pairs': ['22+'],
        'suited': ['A2s+', 'K5s+', 'Q7s+', 'J7s+', 'T7s+', '97s+', '86s+', '76s', '65s'],
        'offsuit': ['A5o+', 'K8o+', 'Q9o+', 'J9o+', 'T9o'],
        # ~42%
    },
    'vs_btn_normal': {
        'pairs': ['22+'],
        'suited': ['A2s+', 'K2s+', 'Q4s+', 'J6s+', 'T6s+', '96s+', '85s+', '75s+', '65s', '54s'],
        'offsuit': ['A2o+', 'K6o+', 'Q8o+', 'J8o+', 'T8o+', '98o'],
        # ~56%
    },
    # vs SB open
    'vs_sb_tight': {
        'pairs': ['22+'],
        'suited': ['A2s+', 'K4s+', 'Q6s+', 'J7s+', 'T7s+', '97s+', '87s', '76s'],
        'offsuit': ['A4o+', 'K7o+', 'Q9o+', 'J9o+', 'T9o'],
        # ~46%
    },
    'vs_sb_normal': {
        'pairs': ['22+'],
        'suited': ['A2s+', 'K2s+', 'Q2s+', 'J5s+', 'T6s+', '96s+', '85s+', '75s+', '65s', '54s'],
        'offsuit': ['A2o+', 'K5o+', 'Q7o+', 'J8o+', 'T8o+', '98o'],
        # ~62%
    },
    # vs EP/MP open
    'vs_ep_tight': {
        'pairs': ['55+'],
        'suited': ['A7s+', 'K9s+', 'QTs+', 'JTs'],
        'offsuit': ['A9o+', 'KQo'],
        # ~18%
    },
    'vs_ep_normal': {
        'pairs': ['44+'],
        'suited': ['A4s+', 'K8s+', 'Q9s+', 'J9s+', 'T9s', '98s'],
        'offsuit': ['A7o+', 'KTo+', 'QJo'],
        # ~28%
    }
}

# ===== 3-bet 范围 =====

THREEBET_RANGES = {
    # UTG vs BTN open
    'utg_vs_btn': {
        'value': {
            'pairs': ['JJ+'],
            'suited': ['AKs'],
            'offsuit': ['AKo'],
            # ~3.6% (纯价值)
        },
        'bluff': {
            'suited': ['A5s', 'A4s'],  # wheel blockers
            # ~0.6%
        }
    },
    # BTN vs UTG open
    'btn_vs_utg': {
        'value': {
            'pairs': ['99+'],
            'suited': ['AJs+', 'KQs'],
            'offsuit': ['AQo+'],
            # ~6.8%
        },
        'bluff': {
            'suited': ['A5s-A2s', 'K9s', 'Q9s'],
            # ~2.1%
        }
    },
    # BTN vs CO open
    'btn_vs_co': {
        'value': {
            'pairs': ['88+'],
            'suited': ['ATs+', 'KQs'],
            'offsuit': ['AJo+', 'KQo'],
            # ~9.5%
        },
        'bluff': {
            'suited': ['A5s-A2s', 'K8s', 'Q8s', 'J8s'],
            # ~3.0%
        }
    },
    # BB vs BTN open
    'bb_vs_btn': {
        'value': {
            'pairs': ['77+'],
            'suited': ['A9s+', 'KJs+'],
            'offsuit': ['AJo+', 'KQo'],
            # ~11.2%
        },
        'bluff': {
            'suited': ['A5s-A2s', 'K7s', 'Q8s', 'J8s', 'T8s'],
            # ~3.6%
        }
    }
}

# ===== 4-bet 范围 =====

FOURBET_RANGES = {
    'utg_vs_btn_3bet': {
        'value': {
            'pairs': ['QQ+'],
            'suited': ['AKs'],
            'offsuit': ['AKo'],
            # ~2.5%
        },
        'bluff': {
            'suited': ['A5s'],
            # ~0.3%
        }
    },
    'btn_vs_utg_3bet': {
        'value': {
            'pairs': ['JJ+'],
            'suited': ['AKs'],
            'offsuit': ['AKo'],
            # ~3.6%
        },
        'bluff': {
            'suited': ['A5s', 'A4s'],
            # ~0.6%
        }
    },
    'bb_vs_btn_3bet': {
        'value': {
            'pairs': ['TT+'],
            'suited': ['AQs+'],
            'offsuit': ['AKo'],
            # ~4.5%
        },
        'bluff': {
            'suited': ['A5s', 'A4s', 'K9s'],
            # ~0.9%
        }
    }
}

# ===== 辅助函数 =====

def get_open_range(position: str, tightness: str = 'normal') -> dict:
    """
    获取开池范围

    Args:
        position: 'UTG', 'MP', 'CO', 'BTN', 'SB'
        tightness: 'tight', 'normal', 'loose'

    Returns:
        范围字典 {'pairs': [...], 'suited': [...], 'offsuit': [...]}
    """
    position = position.upper()
    range_map = {
        'UTG': UTG_OPEN_RANGES,
        'MP': MP_OPEN_RANGES,
        'CO': CO_OPEN_RANGES,
        'BTN': BTN_OPEN_RANGES,
        'SB': SB_OPEN_RANGES,
    }

    if position not in range_map:
        raise ValueError(f"Unknown position: {position}")

    return range_map[position].get(tightness, range_map[position]['normal'])


def get_bb_call_range(vs_position: str, tightness: str = 'normal') -> dict:
    """
    获取BB跟注范围

    Args:
        vs_position: 'BTN', 'SB', 'EP', 'MP'
        tightness: 'tight', 'normal'

    Returns:
        范围字典
    """
    key = f"vs_{vs_position.lower()}_{tightness}"
    if key in BB_CALL_RANGES:
        return BB_CALL_RANGES[key]

    # 默认返回 vs_btn_normal
    return BB_CALL_RANGES['vs_btn_normal']


def get_3bet_range(position: str, vs_position: str) -> dict:
    """
    获取3-bet范围

    Args:
        position: 我方位置 (e.g., 'BTN', 'BB')
        vs_position: 对手位置 (e.g., 'UTG', 'CO')

    Returns:
        {'value': {...}, 'bluff': {...}}
    """
    key = f"{position.lower()}_vs_{vs_position.lower()}"
    if key in THREEBET_RANGES:
        return THREEBET_RANGES[key]

    # 默认返回保守3-bet
    return THREEBET_RANGES['utg_vs_btn']


def get_4bet_range(position: str, vs_position: str) -> dict:
    """
    获取4-bet范围

    Args:
        position: 我方位置
        vs_position: 对手位置

    Returns:
        {'value': {...}, 'bluff': {...}}
    """
    key = f"{position.lower()}_vs_{vs_position.lower()}_3bet"
    if key in FOURBET_RANGES:
        return FOURBET_RANGES[key]

    # 默认返回保守4-bet
    return FOURBET_RANGES['utg_vs_btn_3bet']


def parse_range_dict(range_dict: dict) -> 'Range':
    """
    将范围字典转换为Range对象

    Args:
        range_dict: 范围字典，如 {'pairs': ['77+'], 'suited': ['A9s+'], 'offsuit': ['AJo+']}

    Returns:
        Range对象

    Example:
        range_dict = get_open_range('BTN', 'normal')
        btn_range = parse_range_dict(range_dict)
    """
    from .range import Range

    # 合并所有手牌
    all_hands = []
    for category in ['pairs', 'suited', 'offsuit']:
        if category in range_dict:
            all_hands.extend(range_dict[category])

    # 用逗号连接所有手牌
    range_str = ','.join(all_hands)

    return Range.from_string(range_str)
