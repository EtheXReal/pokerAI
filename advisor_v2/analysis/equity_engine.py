"""
EquityEngine - Equity计算引擎

负责计算完整的equity信息（不只是单点equity），包括：
1. Hand vs Range的equity计算（Monte Carlo）
2. Equity分布计算（crushing/strong/ahead/flip/behind）
3. Range vs Range的平均equity
4. LRU缓存（性能优化）
"""

import random
from typing import List, Optional, Dict, Tuple
from collections import OrderedDict

from advisor_v2.core.interfaces.analysis_interface import IEquityEngine
from advisor_v2.core.data_structures import EquityInfo
from poker_core.cards import Hand, Card, Rank, Suit
from poker_core.range import Range
from poker_core.evaluator import HandEvaluator


class Deck:
    """
    简单的Deck实现（用于Monte Carlo模拟）
    """

    def __init__(self):
        """初始化52张牌的deck"""
        self.cards = []
        for rank in Rank:
            for suit in Suit:
                self.cards.append(Card(rank, suit))
        random.shuffle(self.cards)

    def remove_card(self, card: Card):
        """移除已知牌"""
        # 找到并移除
        for i, c in enumerate(self.cards):
            if c.rank == card.rank and c.suit == card.suit:
                self.cards.pop(i)
                return

    def draw(self) -> Card:
        """抽一张牌"""
        return self.cards.pop()


class LRUCache:
    """
    LRU (Least Recently Used) 缓存

    当缓存满时，移除最久未使用的项。
    """

    def __init__(self, max_size: int = 10000):
        """
        初始化LRU缓存

        Args:
            max_size: 最大缓存大小
        """
        self.cache = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def get(self, key: any) -> Optional[any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在则返回None
        """
        if key in self.cache:
            # 移到末尾（表示最近使用）
            self.cache.move_to_end(key)
            self.hits += 1
            return self.cache[key]
        else:
            self.misses += 1
            return None

    def put(self, key: any, value: any):
        """
        添加/更新缓存

        Args:
            key: 缓存键
            value: 缓存值
        """
        if key in self.cache:
            # 已存在，更新并移到末尾
            self.cache.move_to_end(key)
        else:
            # 新增
            if len(self.cache) >= self.max_size:
                # 缓存满，移除最久未使用的（第一个）
                self.cache.popitem(last=False)

        self.cache[key] = value

    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0

    def get_stats(self) -> Dict[str, any]:
        """获取缓存统计"""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0.0

        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': hit_rate
        }


class EquityEngine(IEquityEngine):
    """
    Equity引擎实现

    关键改进：
    - 返回完整EquityInfo（不只是单点equity）
    - LRU缓存（避免重复计算）
    - 可配置迭代次数（vs Random用200次，vs人类用1000次）
    """

    def __init__(self, cache_size: int = 10000):
        """
        初始化EquityEngine

        Args:
            cache_size: 缓存大小
        """
        self.cache = LRUCache(max_size=cache_size)
        self.evaluator = HandEvaluator()

    def calculate_equity(self, hand: Hand, villain_range: Range, board: List,
                        iterations: int = 200) -> EquityInfo:
        """
        计算完整的equity信息

        Args:
            hand: Hero的手牌
            villain_range: Villain的range
            board: Board
            iterations: Monte Carlo迭代次数

        Returns:
            EquityInfo对象
        """
        # 1. 生成缓存键
        cache_key = self._generate_cache_key(hand, villain_range, board)

        # 2. 尝试从缓存获取
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        # 3. 计算point equity
        point_equity = self._monte_carlo_equity(hand, villain_range, board, iterations)

        # 4. 计算equity分布
        equity_dist = self._calculate_equity_distribution(hand, villain_range, board)

        # 5. 计算outs（如果还有街道）
        outs, clean_outs = self._count_outs(hand, board, villain_range)

        # 6. 估计implied odds factor
        implied_odds_factor = self._estimate_implied_odds_factor(hand, board, outs)

        # 7. 构建EquityInfo
        equity_info = EquityInfo(
            point_equity=point_equity,
            equity_distribution=equity_dist,
            equity_vs_calling_range=None,  # 需要额外的range信息
            equity_vs_raising_range=None,
            equity_vs_folding_range=None,
            outs=outs,
            clean_outs=clean_outs,
            implied_odds_factor=implied_odds_factor,
            reverse_implied_odds=0.0  # 简化，Phase 2实现
        )

        # 8. 缓存结果
        self.cache.put(cache_key, equity_info)

        return equity_info

    def _generate_cache_key(self, hand: Hand, villain_range: Range, board: List) -> str:
        """
        生成缓存键

        Args:
            hand: Hero手牌
            villain_range: Villain range
            board: Board

        Returns:
            缓存键字符串
        """
        # Hand的字符串表示
        hand_str = ''.join([str(c) for c in hand.cards])

        # Board的字符串表示
        board_str = ''.join([str(c) for c in board]) if board else 'preflop'

        # Range的字符串表示（简化：使用range的手牌数量）
        range_hands = villain_range.to_hands()
        range_size = len(range_hands)
        range_str = f"range_{range_size}"

        return f"{hand_str}_{board_str}_{range_str}"

    def _monte_carlo_equity(self, hand: Hand, villain_range: Range, board: List,
                           iterations: int) -> float:
        """
        Monte Carlo equity计算

        Args:
            hand: Hero手牌
            villain_range: Villain range
            board: Board
            iterations: 迭代次数

        Returns:
            Equity (0-1)
        """
        if not villain_range.to_hands() or len(villain_range.to_hands()) == 0:
            return 0.5  # 空range，返回0.5

        wins = 0
        ties = 0
        total = 0

        # 获取villain的所有可能hands
        villain_hands = villain_range.to_hands()

        # 如果villain hands太多，采样
        if len(villain_hands) > 100:
            villain_hands = random.sample(villain_hands, 100)

        # 对每个villain hand进行模拟
        for villain_hand in villain_hands:
            # 检查冲突（hero和villain不能有相同的牌）
            if self._has_card_conflict(hand, villain_hand, board):
                continue

            # 模拟剩余的board（如果board未完成）
            wins_vs_hand, ties_vs_hand = self._simulate_vs_hand(
                hand, villain_hand, board, iterations // len(villain_hands) + 1
            )

            wins += wins_vs_hand
            ties += ties_vs_hand
            total += iterations // len(villain_hands) + 1

        if total == 0:
            return 0.5

        # Equity = (wins + ties/2) / total
        equity = (wins + ties / 2.0) / total
        return max(0.0, min(1.0, equity))  # Clamp to [0, 1]

    def _has_card_conflict(self, hand1: Hand, hand2: Hand, board: List) -> bool:
        """检查两个hand和board是否有重复的牌"""
        all_cards = hand1.cards + hand2.cards + board
        card_strs = [str(c) for c in all_cards]
        return len(card_strs) != len(set(card_strs))

    def _simulate_vs_hand(self, hero_hand: Hand, villain_hand: Hand, board: List,
                         iterations: int) -> Tuple[int, int]:
        """
        模拟hero vs villain的equity

        Args:
            hero_hand: Hero手牌
            villain_hand: Villain手牌
            board: 当前board
            iterations: 迭代次数

        Returns:
            (wins, ties)
        """
        wins = 0
        ties = 0

        # 已知的牌
        known_cards = hero_hand.cards + villain_hand.cards + board

        # 如果board已完成，直接比较
        if len(board) == 5:
            # 组合手牌+公共牌评估最佳5张
            hero_cards = list(hero_hand.cards) + list(board)
            villain_cards = list(villain_hand.cards) + list(board)

            hero_strength = self.evaluator.evaluate_best_5(hero_cards)
            villain_strength = self.evaluator.evaluate_best_5(villain_cards)

            if hero_strength > villain_strength:  # HandStrength使用>比较
                return (iterations, 0)
            elif hero_strength == villain_strength:
                return (0, iterations)
            else:
                return (0, 0)

        # Board未完成，Monte Carlo模拟
        cards_needed = 5 - len(board)

        for _ in range(iterations):
            # 创建deck并移除已知牌
            deck = Deck()
            for card in known_cards:
                deck.remove_card(card)

            # 发剩余的board
            remaining_board = [deck.draw() for _ in range(cards_needed)]
            full_board = board + remaining_board

            # 评估
            try:
                # 组合手牌+完整公共牌评估最佳5张
                hero_cards = list(hero_hand.cards) + list(full_board)
                villain_cards = list(villain_hand.cards) + list(full_board)

                hero_strength = self.evaluator.evaluate_best_5(hero_cards)
                villain_strength = self.evaluator.evaluate_best_5(villain_cards)

                if hero_strength > villain_strength:  # HandStrength使用>比较
                    wins += 1
                elif hero_strength == villain_strength:
                    ties += 1
            except Exception as e:
                # 评估失败，跳过（通常不应该发生）
                pass

        return (wins, ties)

    def _calculate_equity_distribution(self, hand: Hand, villain_range: Range,
                                      board: List) -> Dict[str, float]:
        """
        计算equity分布

        分类：
        - crushing: equity > 0.80 (vs villain hand)
        - strong: equity 0.65-0.80
        - ahead: equity 0.55-0.65
        - flip: equity 0.45-0.55
        - behind: equity 0.35-0.45
        - weak: equity < 0.35

        Args:
            hand: Hero手牌
            villain_range: Villain range
            board: Board

        Returns:
            Equity分布字典
        """
        if not villain_range.to_hands() or len(villain_range.to_hands()) == 0:
            return {'flip': 1.0}

        # 对villain range中的每个hand计算equity
        equity_counts = {
            'crushing': 0,
            'strong': 0,
            'ahead': 0,
            'flip': 0,
            'behind': 0,
            'weak': 0
        }

        villain_hands = villain_range.to_hands()
        if len(villain_hands) > 50:
            villain_hands = random.sample(villain_hands, 50)

        valid_count = 0

        for vh in villain_hands:
            # 检查冲突
            if self._has_card_conflict(hand, vh, board):
                continue

            # 简化计算：基于当前board直接比较（不模拟未来）
            if len(board) >= 3:
                try:
                    hero_rank = self.evaluator.evaluate(board, hand.cards)
                    villain_rank = self.evaluator.evaluate(board, vh.cards)

                    # 将rank差异转换为equity估计
                    rank_diff = villain_rank - hero_rank
                    # rank_diff > 0 → hero stronger
                    # rank_diff < 0 → villain stronger

                    # 粗略的equity估计
                    if rank_diff > 2000:
                        equity_counts['crushing'] += 1
                    elif rank_diff > 1000:
                        equity_counts['strong'] += 1
                    elif rank_diff > 0:
                        equity_counts['ahead'] += 1
                    elif rank_diff > -1000:
                        equity_counts['flip'] += 1
                    elif rank_diff > -2000:
                        equity_counts['behind'] += 1
                    else:
                        equity_counts['weak'] += 1

                    valid_count += 1
                except:
                    pass
            else:
                # 翻前：基于hand strength粗略估计
                valid_count += 1
                equity_counts['flip'] += 1  # 简化

        # 归一化
        if valid_count == 0:
            return {'flip': 1.0}

        equity_dist = {k: v / valid_count for k, v in equity_counts.items()}
        return equity_dist

    def _count_outs(self, hand: Hand, board: List, villain_range: Range) -> Tuple[int, int]:
        """
        计算outs（听牌）

        Args:
            hand: Hero手牌
            board: Board
            villain_range: Villain range

        Returns:
            (outs, clean_outs)
        """
        if len(board) == 5:
            return (0, 0)  # River，没有outs

        # 简化实现：基于手牌类型估计
        # 完整实现需要遍历所有可能的turn/river牌

        # 这里只做粗略估计
        outs = 0

        # 检查flush draw
        if len(board) >= 3:
            suits = [c.suit for c in board]
            hero_suits = [c.suit for c in hand.cards]

            for suit in set(suits):
                if suits.count(suit) == 2 and hero_suits.count(suit) >= 1:
                    # Flush draw
                    outs += 9
                    break

        # 检查straight draw（简化）
        # 完整实现需要检查连牌

        clean_outs = outs  # 简化：假设所有outs都是clean

        return (outs, clean_outs)

    def _estimate_implied_odds_factor(self, hand: Hand, board: List, outs: int) -> float:
        """
        估计implied odds factor

        Args:
            hand: Hero手牌
            board: Board
            outs: Outs数量

        Returns:
            Implied odds factor (1.0 = no implied odds, >1.0 = positive implied odds)
        """
        if outs == 0:
            return 1.0

        # 简化：基于outs数量估计
        # 听牌越多，implied odds越高
        if outs >= 15:
            return 1.5  # Strong draw
        elif outs >= 9:
            return 1.3  # Flush draw
        elif outs >= 6:
            return 1.2  # OESD
        elif outs >= 3:
            return 1.1  # Gutshot
        else:
            return 1.0

    def calculate_range_equity(self, hero_range: Range, villain_range: Range,
                              board: List) -> float:
        """
        计算range vs range的平均equity

        Args:
            hero_range: Hero range
            villain_range: Villain range
            board: Board

        Returns:
            平均equity
        """
        if not hero_range.to_hands() or not villain_range.to_hands():
            return 0.5

        # 采样（避免计算量过大）
        hero_sample = hero_range.to_hands()
        if len(hero_sample) > 20:
            hero_sample = random.sample(hero_sample, 20)

        total_equity = 0.0
        valid_count = 0

        for hero_hand in hero_sample:
            # 计算这个hero hand vs villain range的equity
            equity_info = self.calculate_equity(hero_hand, villain_range, board, iterations=100)
            total_equity += equity_info.point_equity
            valid_count += 1

        if valid_count == 0:
            return 0.5

        avg_equity = total_equity / valid_count
        return avg_equity

    def clear_cache(self):
        """清空equity缓存"""
        self.cache.clear()

    def get_cache_stats(self) -> dict:
        """
        获取缓存统计

        Returns:
            缓存统计字典
        """
        return self.cache.get_stats()
