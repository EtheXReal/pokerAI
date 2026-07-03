"""
RangeEngine - Range管理和分析

这是range-based决策的核心模块，负责：
1. 管理GTO range库
2. 计算hand在range中的位置（相对强度）
3. 分析range vs range交互
4. 估计对手range
"""

import json
import os
from typing import List, Optional, Dict, Tuple
from collections import defaultdict

from advisor.core.interfaces.analysis_interface import IRangeEngine
from advisor.core.data_structures import RangeAdvantage, Action
from poker_core.position import Position
from poker_core.cards import Hand, Card
from poker_core.range import Range


class RangeEngine(IRangeEngine):
    """
    Range引擎实现

    核心改进：
    - 翻前决策基于hand在range中的相对位置（非绝对hand_strength）
    - 深度range分析（nut advantage + equity分布）
    - 基于对手类型动态调整range估计
    """

    def __init__(self, range_data_path: Optional[str] = None):
        """
        初始化RangeEngine

        Args:
            range_data_path: range数据文件路径，如果为None则使用默认路径
        """
        # 加载range数据
        if range_data_path is None:
            # 默认路径：advisor_v2/data/preflop_ranges.json
            current_dir = os.path.dirname(os.path.abspath(__file__))
            range_data_path = os.path.join(current_dir, '..', 'data', 'preflop_ranges.json')

        with open(range_data_path, 'r') as f:
            self.range_data = json.load(f)

        # 预解析所有range（性能优化：避免重复解析）
        self.range_cache = {}
        self._preload_ranges()

        # Preflop hand strength cache（用于hand percentile计算）
        self.preflop_hand_strength_cache = {}
        self._build_preflop_strength_cache()

        # Hand对象 → strength 备忘缓存（percentile计算热点）
        self._hand_strength_memo = {}

    def _preload_ranges(self):
        """预加载所有range到缓存"""
        # Open ranges
        for pos, data in self.range_data['open_ranges'].items():
            range_str = data['range']
            if range_str:  # BB的range是空的
                self.range_cache[f'open_{pos}'] = Range.from_string(range_str)

        # 3-bet ranges
        for key, data in self.range_data['vs_open_3bet_ranges'].items():
            self.range_cache[f'3bet_{key}'] = Range.from_string(data['range'])

        # Call ranges
        for key, data in self.range_data['vs_open_call_ranges'].items():
            self.range_cache[f'call_{key}'] = Range.from_string(data['range'])

        # 4-bet ranges
        for key, data in self.range_data.get('vs_3bet_4bet_ranges', {}).items():
            self.range_cache[f'4bet_{key}'] = Range.from_string(data['range'])

        # Call vs 3-bet ranges
        for key, data in self.range_data.get('vs_3bet_call_ranges', {}).items():
            self.range_cache[f'call_vs_3bet_{key}'] = Range.from_string(data['range'])

    def _build_preflop_strength_cache(self):
        """
        构建翻前hand strength缓存

        这个cache用于快速计算hand在range中的位置。
        基于Sklansky-Malmuth手牌组排名 + 实际equity调整。
        """
        # 简化版：使用标准的hand strength评分
        # 完整版可以从solver数据导入

        # AA=1.0, KK=0.95, QQ=0.90, ...
        pair_strength = {
            'AA': 1.00, 'KK': 0.95, 'QQ': 0.90, 'JJ': 0.85, 'TT': 0.80,
            '99': 0.75, '88': 0.70, '77': 0.65, '66': 0.60, '55': 0.55,
            '44': 0.50, '33': 0.45, '22': 0.40
        }

        # Suited connectors and broadways
        suited_strength = {
            'AKs': 0.92, 'AQs': 0.88, 'AJs': 0.84, 'ATs': 0.80,
            'A9s': 0.70, 'A8s': 0.65, 'A7s': 0.60, 'A6s': 0.58, 'A5s': 0.62,  # A5s有flush+straight潜力
            'A4s': 0.56, 'A3s': 0.54, 'A2s': 0.52,
            'KQs': 0.82, 'KJs': 0.78, 'KTs': 0.74, 'K9s': 0.66, 'K8s': 0.62,
            'K7s': 0.58, 'K6s': 0.54, 'K5s': 0.52, 'K4s': 0.48, 'K3s': 0.46, 'K2s': 0.44,
            'QJs': 0.76, 'QTs': 0.72, 'Q9s': 0.68, 'Q8s': 0.64, 'Q7s': 0.58,
            'Q6s': 0.54, 'Q5s': 0.50, 'Q4s': 0.46, 'Q3s': 0.44, 'Q2s': 0.42,
            'JTs': 0.74, 'J9s': 0.70, 'J8s': 0.66, 'J7s': 0.60, 'J6s': 0.54,
            'J5s': 0.50, 'J4s': 0.48, 'J3s': 0.44, 'J2s': 0.42,
            'T9s': 0.72, 'T8s': 0.68, 'T7s': 0.62, 'T6s': 0.58, 'T5s': 0.54,
            'T4s': 0.50, 'T3s': 0.46, 'T2s': 0.44,
            '98s': 0.70, '97s': 0.64, '96s': 0.60, '95s': 0.56, '94s': 0.52,
            '93s': 0.48, '92s': 0.46,
            '87s': 0.68, '86s': 0.62, '85s': 0.58, '84s': 0.54, '83s': 0.48, '82s': 0.46,
            '76s': 0.66, '75s': 0.60, '74s': 0.56, '73s': 0.52, '72s': 0.44,
            '65s': 0.64, '64s': 0.58, '63s': 0.54, '62s': 0.46,
            '54s': 0.62, '53s': 0.56, '52s': 0.52,
            '43s': 0.54, '42s': 0.50,
            '32s': 0.52
        }

        # Offsuit hands
        offsuit_strength = {
            'AKo': 0.87, 'AQo': 0.83, 'AJo': 0.79, 'ATo': 0.75,
            'A9o': 0.65, 'A8o': 0.60, 'A7o': 0.55, 'A6o': 0.52, 'A5o': 0.60,  # A5o有wheel潜力(同A5s)
            'A4o': 0.50, 'A3o': 0.48, 'A2o': 0.46,
            'KQo': 0.77, 'KJo': 0.73, 'KTo': 0.69, 'K9o': 0.61, 'K8o': 0.57,
            'K7o': 0.53, 'K6o': 0.49, 'K5o': 0.47, 'K4o': 0.43, 'K3o': 0.41, 'K2o': 0.39,
            'QJo': 0.71, 'QTo': 0.67, 'Q9o': 0.63, 'Q8o': 0.59, 'Q7o': 0.53,
            'Q6o': 0.49, 'Q5o': 0.45, 'Q4o': 0.41, 'Q3o': 0.39, 'Q2o': 0.37,
            'JTo': 0.69, 'J9o': 0.65, 'J8o': 0.61, 'J7o': 0.55, 'J6o': 0.49,
            'J5o': 0.45, 'J4o': 0.43, 'J3o': 0.39, 'J2o': 0.37,
            'T9o': 0.67, 'T8o': 0.63, 'T7o': 0.57, 'T6o': 0.53, 'T5o': 0.49,
            'T4o': 0.45, 'T3o': 0.41, 'T2o': 0.39,
            '98o': 0.65, '97o': 0.59, '96o': 0.55, '95o': 0.51, '94o': 0.47,
            '93o': 0.41, '92o': 0.39,
            '87o': 0.63, '86o': 0.57, '85o': 0.53, '84o': 0.49, '83o': 0.41, '82o': 0.39,
            '76o': 0.61, '75o': 0.55, '74o': 0.51, '73o': 0.47, '72o': 0.35,
            '65o': 0.59, '64o': 0.53, '63o': 0.49, '62o': 0.39,
            '54o': 0.57, '53o': 0.51, '52o': 0.47,
            '43o': 0.49, '42o': 0.45,
            '32o': 0.47
        }

        self.preflop_hand_strength_cache = {**pair_strength, **suited_strength, **offsuit_strength}

    def get_ideal_range(self, position: Position, action_history: list,
                       stack_depth: Optional[float] = None) -> Range:
        """
        获取GTO理论范围

        Args:
            position: 位置
            action_history: 行动历史
            stack_depth: 有效筹码深度（BB数），暂不使用，预留给未来

        Returns:
            GTO理论range
        """
        if not action_history:
            # 开池range
            cache_key = f'open_{position.name}'
            if cache_key in self.range_cache:
                return self.range_cache[cache_key]
            else:
                # BB不能开池，返回空Range（不能用空字符串）
                return Range()

        # 分析行动历史
        last_action = action_history[-1]

        if len(action_history) == 1 and last_action.action == 'raise':
            # 面对open：3-bet或call
            opener_position = self._infer_opener_position(action_history, position)

            # 3-bet range
            three_bet_key = f'3bet_{position.name}_vs_{opener_position.name}'
            if three_bet_key in self.range_cache:
                three_bet_range = self.range_cache[three_bet_key]
            else:
                # 如果没有精确匹配，使用通用3-bet range
                three_bet_range = Range.from_string("99+,ATs+,KQs,AQo+")

            # Call range
            call_key = f'call_{position.name}_vs_{opener_position.name}'
            if call_key in self.range_cache:
                call_range = self.range_cache[call_key]
            else:
                # 通用call range
                call_range = Range.from_string("22-88,A2s+,K5s+,Q8s+,J8s+,T8s+,A5o+,K9o+")

            # 合并3-bet和call range
            return three_bet_range.union(call_range)

        elif len(action_history) == 2:
            # 可能是面对3-bet
            if action_history[0].action == 'raise' and action_history[1].action == 'raise':
                # open → 3-bet，现在我们要4-bet或call

                # 4-bet range
                four_bet_key = f'4bet_{position.name}_vs_BB_3bet'  # 简化，假设是vs BB
                if four_bet_key in self.range_cache:
                    four_bet_range = self.range_cache[four_bet_key]
                else:
                    four_bet_range = Range.from_string("JJ+,AQs+,AKo")

                # Call vs 3-bet range
                call_vs_3bet_key = f'call_vs_3bet_{position.name}_vs_BB_3bet'
                if call_vs_3bet_key in self.range_cache:
                    call_vs_3bet_range = self.range_cache[call_vs_3bet_key]
                else:
                    call_vs_3bet_range = Range.from_string("88-TT,AJs,KQs,AQo")

                # 合并
                return four_bet_range.union(call_vs_3bet_range)

        # 默认：返回较宽的range
        return Range.from_string("22+,A2s+,K5s+,Q8s+,J8s+,T8s+,A5o+,K9o+")

    def get_hand_percentile(self, hand: Hand, range_obj: Range,
                           board: Optional[List] = None) -> float:
        """
        计算hand在range中的位置（0-1）

        这是range-based决策的核心：不看绝对强度，看相对位置。

        Args:
            hand: Hero的手牌
            range_obj: Hero应该持有的range
            board: Board（如果是翻后）

        Returns:
            0-1的百分位数（1.0 = range中最强，0.0 = range中最弱）
        """
        all_hands = range_obj.to_hands()

        if not all_hands:
            return 0.5  # Empty range，返回中间值

        # 检查hand是否在range中
        if hand not in all_hands:
            # Hand不在range中，返回0
            return 0.0

        # Percentile = 1 - (严格更强的组合数 / 总数)
        # 并列的组合共享同一(最优)percentile：单一AA range中AA=1.0
        if not board or len(board) == 0:
            # 翻前：基于preflop strength
            my_strength = self._get_preflop_hand_strength(hand)
            stronger = sum(
                1 for h in all_hands
                if self._get_preflop_hand_strength(h) > my_strength
            )
            return 1.0 - (stronger / len(all_hands))

        else:
            # 翻后：基于当前成牌强度
            # （真正的equity计算由EquityEngine完成，这里只用于range内部排序）
            my_score = self._board_hand_score(hand, board)
            if my_score is None:
                return 0.0  # hand与board冲突

            # 排除与board冲突的组合
            valid_scores = [s for s in (self._board_hand_score(h, board) for h in all_hands)
                            if s is not None]
            if not valid_scores:
                return 0.5

            stronger = sum(1 for s in valid_scores if s > my_score)
            return 1.0 - (stronger / len(valid_scores))

    def _get_preflop_hand_strength(self, hand: Hand) -> float:
        """
        获取翻前hand strength

        Args:
            hand: 手牌

        Returns:
            0-1的strength评分
        """
        # 按Hand对象缓存（避免重复的字符串转换，percentile计算的热点）
        cached = self._hand_strength_memo.get(hand)
        if cached is not None:
            return cached

        # 获取hand的字符串表示
        hand_str = self._hand_to_str(hand)

        # 从cache查找（不在表中返回默认值）
        strength = self.preflop_hand_strength_cache.get(hand_str, 0.5)
        self._hand_strength_memo[hand] = strength
        return strength

    def _hand_to_str(self, hand: Hand) -> str:
        """
        将Hand对象转换为标准字符串表示

        Args:
            hand: Hand对象

        Returns:
            字符串表示，如"AKs", "AKo", "AA"
        """
        if not hand or not hand.cards or len(hand.cards) < 2:
            return ""

        card1, card2 = hand.cards[0], hand.cards[1]
        rank1, rank2 = card1.rank, card2.rank

        # 确保高牌在前
        if self._rank_value(rank1) < self._rank_value(rank2):
            rank1, rank2 = rank2, rank1

        # 判断是否同花
        if card1.suit == card2.suit:
            if rank1 == rank2:
                return f"{rank1}{rank2}"  # Pair
            else:
                return f"{rank1}{rank2}s"  # Suited
        else:
            if rank1 == rank2:
                return f"{rank1}{rank2}"  # Pair
            else:
                return f"{rank1}{rank2}o"  # Offsuit

    def _rank_value(self, rank) -> int:
        """将rank转换为数值（用于排序），兼容str和Rank枚举"""
        rank_order = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
                     '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
        return rank_order.get(str(rank), 0)

    def _estimate_hand_equity_on_board(self, hand: Hand, board: List) -> float:
        """
        简化的翻后equity估计（用于hand percentile计算）

        这是一个快速估计，不进行完整的Monte Carlo模拟。
        真正的equity计算由EquityEngine完成。

        Args:
            hand: 手牌
            board: Board

        Returns:
            估计的equity (0-1)
        """
        # 简化实现：基于当前成牌强度排序
        # 完整实现会调用EquityEngine，但那会导致循环依赖
        # 这里只用于range内部排序，不需要绝对准确
        score = self._board_hand_score(hand, board)
        if score is None:
            return 0.50

        # HandStrength.to_score(): rank*10^12 + 牌面值，最大约 10*10^12
        # 归一化到0-1（只用于排序，绝对值无意义）
        return min(1.0, score / (11 * 10**12))

    @staticmethod
    def _board_hand_score(hand: Hand, board: List) -> Optional[int]:
        """
        计算hand在board上的成牌分数（越大越强）

        与board冲突（共用牌）或无法评估时返回None。
        """
        from poker_core.evaluator import HandEvaluator

        board_cards = list(board)
        all_cards = list(hand.cards) + board_cards

        # hand与board共用牌 → 该组合实际不可能存在
        if len(set(all_cards)) != len(all_cards):
            return None

        try:
            if len(all_cards) == 5:
                strength = HandEvaluator.evaluate(all_cards)
            elif len(all_cards) == 7:
                strength = HandEvaluator.evaluate_best_5(all_cards)
            elif len(all_cards) == 6:
                # turn: 从6张中取最佳5张
                from itertools import combinations
                strength = max(
                    (HandEvaluator.evaluate(list(five)) for five in combinations(all_cards, 5)),
                    key=lambda s: s.to_score()
                )
            else:
                return None
            return strength.to_score()
        except (ValueError, KeyError):
            return None

    def analyze_range_interaction(self, hero_range: Range, villain_range: Range,
                                  board: List) -> RangeAdvantage:
        """
        分析range vs range交互

        Args:
            hero_range: Hero的range
            villain_range: Villain的range
            board: Board

        Returns:
            RangeAdvantage对象
        """
        # 1. Range size比较
        hero_size = len(hero_range.to_hands())
        villain_size = len(villain_range.to_hands())
        size_ratio = hero_size / villain_size if villain_size > 0 else 1.0

        # 2. Nut advantage（如果有board）
        nut_adv = 0.0
        if board and len(board) >= 3:
            nut_adv = self._calculate_nut_advantage(hero_range, villain_range, board)

        # 3. Equity分布（简化版）
        hero_equity_dist = self._estimate_equity_distribution(hero_range, villain_range, board)
        villain_equity_dist = self._estimate_equity_distribution(villain_range, hero_range, board)

        # 4. 计算advantage_score
        # 综合考虑：nut advantage (40%), range size (30%), equity分布 (30%)
        nut_component = nut_adv * 0.4
        size_component = (size_ratio - 1.0) * 0.2  # size_ratio > 1 → 正分
        equity_component = (hero_equity_dist.get('strong', 0) - villain_equity_dist.get('strong', 0)) * 0.4

        advantage_score = nut_component + size_component + equity_component
        advantage_score = max(-1.0, min(1.0, advantage_score))  # Clamp to [-1, 1]

        # 5. 判断advantage类型
        if abs(nut_adv) > 0.3:
            advantage_type = 'nut'
        elif abs(size_ratio - 1.0) > 0.3:
            advantage_type = 'range'
        else:
            advantage_type = 'none'

        # 6. Board favors
        if advantage_score > 0.15:
            board_favors = 'hero'
        elif advantage_score < -0.15:
            board_favors = 'villain'
        else:
            board_favors = 'neutral'

        return RangeAdvantage(
            advantage_score=advantage_score,
            advantage_type=advantage_type,
            hero_nut_advantage=nut_adv,
            hero_range_size_ratio=size_ratio,
            hero_equity_distribution=hero_equity_dist,
            villain_equity_distribution=villain_equity_dist,
            board_favors=board_favors,
            board_texture_impact=0.0,  # 由BoardAnalyzer提供
            hero_polarization=0.5,  # 简化，默认0.5
            villain_polarization=0.5
        )

    def _calculate_nut_advantage(self, hero_range: Range, villain_range: Range,
                                 board: List) -> float:
        """
        计算nut advantage

        Args:
            hero_range: Hero的range
            villain_range: Villain的range
            board: Board

        Returns:
            -1到1的nut advantage评分
        """
        hero_hands = hero_range.to_hands()
        villain_hands = villain_range.to_hands()

        # 找出所有可能的hands在当前board上的成牌分数（越大越强）
        hero_scores = [s for s in (self._board_hand_score(h, board) for h in hero_hands)
                       if s is not None]
        villain_scores = [s for s in (self._board_hand_score(h, board) for h in villain_hands)
                          if s is not None]

        if not hero_scores or not villain_scores:
            return 0.0

        # 计算top 10%的平均分数
        hero_top_10 = sorted(hero_scores, reverse=True)[:max(1, len(hero_scores) // 10)]
        villain_top_10 = sorted(villain_scores, reverse=True)[:max(1, len(villain_scores) // 10)]

        hero_top_avg = sum(hero_top_10) / len(hero_top_10)
        villain_top_avg = sum(villain_top_10) / len(villain_top_10)

        # Nut advantage：比较top hands的质量（分数越大越强）
        nut_diff = (hero_top_avg - villain_top_avg) / (11 * 10**12)  # 归一化

        # Clamp to [-1, 1]
        nut_advantage = max(-1.0, min(1.0, nut_diff * 5.0))  # 放大差异

        return nut_advantage

    def _estimate_equity_distribution(self, hero_range: Range, villain_range: Range,
                                     board: Optional[List]) -> Dict[str, float]:
        """
        估计equity分布

        Args:
            hero_range: Hero的range
            villain_range: Villain的range
            board: Board

        Returns:
            Equity分布字典
        """
        # 简化实现：基于range质量估计
        # 完整实现需要对每个hero hand计算vs villain range的equity

        hero_hands = hero_range.to_hands()
        if not hero_hands:
            return {'strong': 0, 'medium': 0, 'weak': 1.0}

        # 简化：基于hand count估计
        # 假设强牌占20%，中等牌占50%，弱牌占30%
        return {
            'strong': 0.25,
            'medium': 0.50,
            'weak': 0.25
        }

    # ------------------------------------------------------------------
    # 范围动态收缩（翻后）
    # ------------------------------------------------------------------

    # 各动作保留的范围比例（按成牌强度排序），按对手行动信息量分档：
    # - honest: 动作与牌力强相关（紧凶/规则型对手）→ 激进收缩
    # - neutral: 未知对手 → 温和收缩（GTO近似）
    # - sticky: 动作几乎不含信息（跟注站/疯狂型，什么牌都call/bet）→ 微收缩
    NARROW_PROFILES = {
        'honest':  {'bet': 0.45, 'raise': 0.35, 'call': 0.70, 'check_drop': 0.15},
        'neutral': {'bet': 0.60, 'raise': 0.45, 'call': 0.85, 'check_drop': 0.10},
        'sticky':  {'bet': 0.75, 'raise': 0.55, 'call': 1.00, 'check_drop': 0.05},
    }
    NARROW_MIN_COMBOS = 20        # 收缩下限，防止范围塌缩

    def narrow_range_postflop(self, range_obj: Range, board: List,
                              action: str, style: str = 'neutral') -> Range:
        """
        根据一次翻后动作收缩范围

        - bet/raise: 保留成牌强度前段 + 听牌（花听/两头顺听作为bluff/半bluff部分）
        - call: 去掉最弱的部分（那些牌面对下注会弃牌）
        - check: 去掉最强的顶部（强牌通常会下注），保留其余
        - fold/其他: 不收缩（fold后该玩家已出局）

        Args:
            style: 对手动作的信息量档位 'honest' / 'neutral' / 'sticky'

        收缩后不足 NARROW_MIN_COMBOS 个组合时返回原范围（信息不足，宁可保守）。
        """
        action = (action or '').lower()
        if action not in ('bet', 'raise', 'call', 'check') or not board:
            return range_obj

        profile = self.NARROW_PROFILES.get(style, self.NARROW_PROFILES['neutral'])
        if action == 'call' and profile['call'] >= 1.0:
            return range_obj  # sticky对手的call不含信息

        combos = list(range_obj.combos)
        if len(combos) <= self.NARROW_MIN_COMBOS:
            return range_obj

        # 计算每个组合的成牌分数（排除与board冲突的组合）
        scored = []
        for combo in combos:
            score = self._board_hand_score(combo.hand, board)
            if score is not None:
                scored.append((combo, score))

        if len(scored) <= self.NARROW_MIN_COMBOS:
            return range_obj

        scored.sort(key=lambda x: x[1], reverse=True)
        n = len(scored)

        if action in ('bet', 'raise', 'call'):
            keep_n = max(self.NARROW_MIN_COMBOS, int(n * profile[action]))
            kept = {c for c, _ in scored[:keep_n]}
            # 半bluff部分：保留强听牌（花听/两头顺听）
            for combo, _ in scored[keep_n:]:
                if self._has_strong_draw(combo.hand, board):
                    kept.add(combo)
        else:  # check
            drop_n = int(n * profile['check_drop'])
            kept = {c for c, _ in scored[drop_n:]}

        if len(kept) < self.NARROW_MIN_COMBOS:
            return range_obj

        return Range(kept)

    @staticmethod
    def _has_strong_draw(hand: Hand, board: List) -> bool:
        """
        检测强听牌：同花听牌（4张同花含≥1张手牌）或两头顺听

        河牌圈无听牌意义，调用方保证board为flop/turn。
        """
        if len(board) >= 5:
            return False

        all_cards = list(hand.cards) + list(board)
        # 与board冲突的组合无意义
        if len(set(all_cards)) != len(all_cards):
            return False

        # 花听：手牌+board同花色共4张，且至少用到1张手牌
        from collections import Counter
        suit_counts = Counter(c.suit for c in all_cards)
        for suit, count in suit_counts.items():
            if count == 4 and any(c.suit == suit for c in hand.cards):
                return True

        # 两头顺听：存在连续4张（用到≥1张手牌），且两端都能补成顺子
        ranks = sorted({int(c.rank) for c in all_cards})
        rank_set = set(ranks)
        hand_ranks = {int(c.rank) for c in hand.cards}
        # A可作低端
        if 14 in rank_set:
            rank_set.add(1)
        for low in range(1, 11):
            window = {low, low + 1, low + 2, low + 3}
            if window <= rank_set:
                # 两头都开（low-1或low+4至少一端可补，两头顺听要求两端）
                if (low - 1) >= 1 or (low + 4) <= 14:
                    # 确认手牌参与
                    if window & hand_ranks or (1 in window and 14 in hand_ranks):
                        # 两头顺听：low-1和low+4都是合法牌
                        if low - 1 >= 2 and low + 4 <= 14:
                            return True
        return False

    def get_preflop_caller_range(self, position: Position,
                                 vs_position: Position) -> Range:
        """
        翻前跟注者的范围（call open，非3bet）

        优先查预置的call range表，无精确匹配时用通用call range。
        """
        call_key = f'call_{position.name}_vs_{vs_position.name}'
        if call_key in self.range_cache:
            return self.range_cache[call_key]
        return Range.from_string("22-99,A2s+,K7s+,Q8s+,J8s+,T8s+,98s,87s,76s,ATo-A5o,KTo+,QTo+,JTo")

    def estimate_villain_range(self, villain_position: Position, action_history: list,
                               villain_tendencies: Optional[dict] = None) -> Range:
        """
        估计对手range

        Args:
            villain_position: 对手位置
            action_history: 行动历史
            villain_tendencies: 对手统计（Phase 2实现）

        Returns:
            估计的villain range
        """
        # Phase 1：使用GTO baseline
        # Phase 2：会根据villain_tendencies调整

        # 注意语义：action_history的最后一个动作是villain自己做的。
        # villain的range = 做出该动作时面对的历史(去掉最后一项)对应的理想range。
        # 例如villain open raise → 面对空历史 → open range
        facing_history = list(action_history[:-1]) if action_history else []
        gto_range = self.get_ideal_range(villain_position, facing_history)

        # Phase 2会根据player_type调整：
        # - LAG: 扩大range (+30-50%)
        # - TAG: 缩小range (-10-20%)
        # - TIGHT_PASSIVE: 缩小并线性化
        # - LOOSE_PASSIVE: 扩大并线性化

        # 暂时直接返回GTO range
        return gto_range

    def _infer_opener_position(self, action_history: list, hero_position: Position) -> Position:
        """
        根据行动历史推断开池者位置

        这是一个简化实现，实际应该从GameState获取。
        """
        # 简化：假设opener是BTN或CO
        if hero_position == Position.BB:
            # BB面对open，可能是BTN, CO, MP, SB
            # 简化：假设是BTN
            return Position.BTN
        elif hero_position == Position.BTN:
            # BTN面对open，可能是CO, MP
            return Position.CO
        elif hero_position == Position.CO:
            # CO面对open，可能是MP
            return Position.MP
        else:
            # 默认BTN
            return Position.BTN
