#!/usr/bin/env python
"""
Range引擎 (Range Engine)

表示和操作手牌范围:
- Range类: 存储一组手牌组合
- RangeParser: 解析字符串表达式 (如 "QQ+,AK")
- 组合生成器: 生成所有可能的牌组合
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Set, FrozenSet, Optional
from itertools import combinations

from .cards import Card, Hand, Rank, Suit, create_deck


@dataclass
class HandCombo:
    """
    单个手牌组合 (具体的2张牌)

    Example:
        HandCombo.from_str("AsAh")  # A♠A♥
    """
    hand: Hand

    def __str__(self) -> str:
        return str(self.hand)

    def __repr__(self) -> str:
        return f"HandCombo('{self.hand}')"

    def __hash__(self) -> int:
        return hash(frozenset(self.hand.cards))

    def __eq__(self, other) -> bool:
        if not isinstance(other, HandCombo):
            return False
        return frozenset(self.hand.cards) == frozenset(other.hand.cards)

    @staticmethod
    def from_str(s: str) -> HandCombo:
        """从字符串创建组合"""
        return HandCombo(Hand.from_str(s))


class Range:
    """
    手牌范围 (一组手牌组合)

    Example:
        # 创建AA的所有组合
        range_aa = Range.from_hand_notation("AA")

        # 创建QQ+, AK
        range_premium = Range.from_string("QQ+,AK")
    """

    def __init__(self, combos: Optional[Set[HandCombo]] = None):
        """
        Args:
            combos: 手牌组合集合
        """
        self.combos: Set[HandCombo] = combos if combos is not None else set()

    def __str__(self) -> str:
        return f"Range({len(self.combos)} combos)"

    def __repr__(self) -> str:
        return f"Range(combos={len(self.combos)})"

    def __len__(self) -> int:
        return len(self.combos)

    def __iter__(self):
        return iter(self.combos)

    def add(self, combo: HandCombo) -> None:
        """添加一个组合"""
        self.combos.add(combo)

    def remove_dead_cards(self, dead_cards: Set[Card]) -> Range:
        """
        移除包含死牌的组合

        Args:
            dead_cards: 已知的死牌 (如自己的手牌、公共牌)

        Returns:
            新的Range (不包含死牌组合)
        """
        valid_combos = set()
        for combo in self.combos:
            # 检查是否有死牌
            has_dead_card = any(card in dead_cards for card in combo.hand.cards)
            if not has_dead_card:
                valid_combos.add(combo)

        return Range(valid_combos)

    def to_hands(self) -> List[Hand]:
        """转换为Hand列表 (用于equity计算)"""
        return [combo.hand for combo in self.combos]

    @staticmethod
    def from_hand_notation(notation: str) -> Range:
        """
        从手牌符号创建Range

        Args:
            notation: 手牌符号，如:
                - "AA" - 所有AA组合 (6种)
                - "AKs" - 同花AK (4种)
                - "AKo" - 非同花AK (12种)
                - "AK" - 所有AK (16种)

        Returns:
            Range对象
        """
        combos = RangeGenerator.generate_from_notation(notation)
        return Range(set(combos))

    @staticmethod
    def from_string(s: str) -> Range:
        """
        从字符串解析Range

        Args:
            s: Range表达式，如:
                - "AA,KK,QQ" - 三个对子
                - "QQ+" - QQ及以上对子 (QQ,KK,AA)
                - "ATs+" - AT及以上同花大牌 (ATs,AJs,AQs,AKs)
                - "88-JJ" - 88到JJ的对子

        Returns:
            Range对象
        """
        return RangeParser.parse(s)


class RangeGenerator:
    """Range组合生成器"""

    @staticmethod
    def generate_from_notation(notation: str) -> List[HandCombo]:
        """
        从手牌符号生成所有组合

        Args:
            notation: 如 "AA", "AKs", "AKo"

        Returns:
            HandCombo列表
        """
        notation = notation.strip().upper()

        # 解析符号
        if len(notation) == 2:
            # 可能是对子 (如 "AA") 或两张不同牌 (如 "AK")
            if notation[0] == notation[1]:
                # 对子
                rank = Rank.from_str(notation[0])
                return RangeGenerator._generate_pair_combos(rank)
            else:
                # 两张不同牌，生成所有组合
                rank1 = Rank.from_str(notation[0])
                rank2 = Rank.from_str(notation[1])
                suited = RangeGenerator._generate_suited_combos(rank1, rank2)
                offsuit = RangeGenerator._generate_offsuit_combos(rank1, rank2)
                return suited + offsuit

        elif len(notation) == 3:
            # 两张不同牌，如 "AKs" 或 "AKo"
            rank1 = Rank.from_str(notation[0])
            rank2 = Rank.from_str(notation[1])
            suited = notation[2].lower() == 's'
            offsuit = notation[2].lower() == 'o'

            if suited:
                return RangeGenerator._generate_suited_combos(rank1, rank2)
            elif offsuit:
                return RangeGenerator._generate_offsuit_combos(rank1, rank2)
            else:
                raise ValueError(f"Invalid notation: {notation}")

        else:
            raise ValueError(f"Invalid notation: {notation}")

    @staticmethod
    def _generate_pair_combos(rank: Rank) -> List[HandCombo]:
        """生成对子的所有组合 (6种)"""
        combos = []
        suits = list(Suit)

        for i in range(len(suits)):
            for j in range(i + 1, len(suits)):
                card1 = Card(rank, suits[i])
                card2 = Card(rank, suits[j])
                combos.append(HandCombo(Hand([card1, card2])))

        return combos

    @staticmethod
    def _generate_suited_combos(rank1: Rank, rank2: Rank) -> List[HandCombo]:
        """生成同花组合 (4种)"""
        combos = []

        for suit in Suit:
            card1 = Card(rank1, suit)
            card2 = Card(rank2, suit)
            combos.append(HandCombo(Hand([card1, card2])))

        return combos

    @staticmethod
    def _generate_offsuit_combos(rank1: Rank, rank2: Rank) -> List[HandCombo]:
        """生成非同花组合 (12种)"""
        combos = []
        suits = list(Suit)

        for suit1 in suits:
            for suit2 in suits:
                if suit1 != suit2:
                    card1 = Card(rank1, suit1)
                    card2 = Card(rank2, suit2)
                    combos.append(HandCombo(Hand([card1, card2])))

        return combos


class RangeParser:
    """Range表达式解析器"""

    @staticmethod
    def parse(expression: str) -> Range:
        """
        解析Range表达式

        Args:
            expression: 如 "QQ+,AK", "88-JJ,ATs+"

        Returns:
            Range对象
        """
        all_combos = set()

        # 按逗号分割
        parts = [p.strip() for p in expression.split(',')]

        for part in parts:
            # 处理每个部分
            if '+' in part:
                # Range扩展，如 "QQ+", "ATs+"
                combos = RangeParser._parse_plus(part)
            elif '-' in part:
                # Range范围，如 "88-JJ"
                combos = RangeParser._parse_range(part)
            else:
                # 单个符号，如 "AA", "AKs"
                combos = RangeGenerator.generate_from_notation(part)

            all_combos.update(combos)

        return Range(all_combos)

    @staticmethod
    def _parse_plus(notation: str) -> List[HandCombo]:
        """
        解析+符号 (及以上)

        Args:
            notation: 如 "QQ+", "ATs+"

        Returns:
            HandCombo列表
        """
        base = notation.replace('+', '').strip()
        combos = []

        if len(base) == 2 and base[0] == base[1]:
            # 对子范围，如 "QQ+"
            rank = Rank.from_str(base[0])

            # 生成该rank及以上的所有对子
            for r in Rank:
                if r >= rank:
                    combos.extend(RangeGenerator._generate_pair_combos(r))

        elif len(base) == 3 and base[2].lower() == 's':
            # 同花范围，如 "ATs+"
            rank1 = Rank.from_str(base[0])
            rank2 = Rank.from_str(base[1])

            # 生成该组合及以上的所有同花组合
            # 例如 ATs+ = ATs, AJs, AQs, AKs
            for r in Rank:
                if rank2 <= r < rank1:  # 第二张牌从rank2到rank1-1
                    combos.extend(RangeGenerator._generate_suited_combos(rank1, r))

        elif len(base) == 3 and base[2].lower() == 'o':
            # 非同花范围，如 "ATo+"
            rank1 = Rank.from_str(base[0])
            rank2 = Rank.from_str(base[1])

            for r in Rank:
                if rank2 <= r < rank1:
                    combos.extend(RangeGenerator._generate_offsuit_combos(rank1, r))

        elif len(base) == 2 and base[0] != base[1]:
            # 两张不同牌的范围，如 "AQ+" (所有AQ及以上)
            rank1 = Rank.from_str(base[0])
            rank2 = Rank.from_str(base[1])

            # 生成该组合及以上的所有组合 (同花+非同花)
            for r in Rank:
                if rank2 <= r < rank1:
                    combos.extend(RangeGenerator._generate_suited_combos(rank1, r))
                    combos.extend(RangeGenerator._generate_offsuit_combos(rank1, r))

        else:
            raise ValueError(f"Invalid + notation: {notation}")

        return combos

    @staticmethod
    def _parse_range(notation: str) -> List[HandCombo]:
        """
        解析-范围

        Args:
            notation: 如 "88-JJ"

        Returns:
            HandCombo列表
        """
        parts = notation.split('-')
        if len(parts) != 2:
            raise ValueError(f"Invalid range notation: {notation}")

        start_str = parts[0].strip()
        end_str = parts[1].strip()

        # 目前只支持对子范围
        if len(start_str) == 2 and start_str[0] == start_str[1]:
            start_rank = Rank.from_str(start_str[0])
            end_rank = Rank.from_str(end_str[0])

            if start_rank > end_rank:
                start_rank, end_rank = end_rank, start_rank

            combos = []
            for r in Rank:
                if start_rank <= r <= end_rank:
                    combos.extend(RangeGenerator._generate_pair_combos(r))

            return combos

        else:
            raise ValueError(f"Currently only pair ranges are supported: {notation}")


def create_premium_range() -> Range:
    """创建premium range (QQ+, AK)"""
    return Range.from_string("QQ+,AK")


def create_broadw_range() -> Range:
    """创建broadway range (所有T+的组合)"""
    return Range.from_string("TT+,ATs+,ATo+,KQs,KQo")


def create_any_pair_range() -> Range:
    """创建所有对子"""
    return Range.from_string("22+")
