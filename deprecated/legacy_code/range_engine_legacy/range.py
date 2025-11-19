"""
Range类: 德州扑克手牌范围的表示和操作

核心功能:
1. 范围的表示 (字符串解析)
2. 范围的操作 (组合/过滤/差集)
3. 范围转combo列表
4. 范围equity计算
"""
import re
from typing import List, Set, Tuple, Optional
from itertools import combinations


class Range:
    """
    手牌范围类

    范围字符串格式:
    - "AA": 特定口袋对
    - "77+": 77到AA的所有口袋对
    - "AKs": AK同花
    - "AKo": AK非同花
    - "AKs+": AKs (没有更高的了)
    - "A5s+": A5s, A6s, ..., AKs
    - "ATo+": ATo, AJo, AQo, AKo
    - "AK": 所有AK (同花+非同花)
    """

    RANKS = '23456789TJQKA'
    RANK_VALUES = {r: i for i, r in enumerate(RANKS)}
    SUITS = 'cdhs'  # clubs, diamonds, hearts, spades

    def __init__(self, range_str: Optional[str] = None):
        """
        初始化范围

        Args:
            range_str: 范围字符串，多个用逗号分隔，如 "AA,KK,AKs,AQs+"
        """
        self.combos: Set[str] = set()

        if range_str:
            self.parse(range_str)

    def parse(self, range_str: str) -> 'Range':
        """
        解析范围字符串

        Args:
            range_str: "AA,KK,AKs,AQs+,77+"

        Returns:
            self (支持链式调用)
        """
        parts = [p.strip() for p in range_str.split(',')]

        for part in parts:
            if not part:
                continue

            # 处理 "+" 符号
            if part.endswith('+'):
                self._parse_plus_notation(part[:-1])
            else:
                self._parse_single_hand(part)

        return self

    def _parse_single_hand(self, hand: str):
        """解析单个手牌"""
        if len(hand) == 2:
            # "AA" 或 "AK"
            r1, r2 = hand[0], hand[1]
            if r1 == r2:
                # 口袋对
                self._add_pair(r1)
            else:
                # 所有AK (suited + offsuit)
                self._add_suited(r1, r2)
                self._add_offsuit(r1, r2)

        elif len(hand) == 3:
            # "AKs" 或 "AKo"
            r1, r2, suit_flag = hand[0], hand[1], hand[2]
            if suit_flag == 's':
                self._add_suited(r1, r2)
            elif suit_flag == 'o':
                self._add_offsuit(r1, r2)

    def _parse_plus_notation(self, hand: str):
        """
        解析 "+" 符号

        例如:
        - "77+": 77, 88, 99, TT, JJ, QQ, KK, AA
        - "A5s+": A5s, A6s, A7s, A8s, A9s, ATs, AJs, AQs, AKs
        - "ATo+": ATo, AJo, AQo, AKo
        """
        if len(hand) == 2 and hand[0] == hand[1]:
            # 口袋对 "77+"
            start_rank = hand[0]
            start_idx = self.RANK_VALUES[start_rank]
            for idx in range(start_idx, len(self.RANKS)):
                rank = self.RANKS[idx]
                self._add_pair(rank)

        elif len(hand) == 3:
            # "A5s+" 或 "ATo+"
            r1, r2, suit_flag = hand[0], hand[1], hand[2]
            start_idx = self.RANK_VALUES[r2]
            high_idx = self.RANK_VALUES[r1]

            # 从start_idx到high_idx-1 (不包括high_idx本身，因为AKs不存在A>K的kicker)
            for idx in range(start_idx, high_idx):
                kicker = self.RANKS[idx]
                if suit_flag == 's':
                    self._add_suited(r1, kicker)
                elif suit_flag == 'o':
                    self._add_offsuit(r1, kicker)

    def _add_pair(self, rank: str):
        """添加口袋对的所有combo"""
        suits = self.SUITS
        for s1, s2 in combinations(suits, 2):
            combo = f"{rank}{s1}{rank}{s2}"
            self.combos.add(combo)

    def _add_suited(self, r1: str, r2: str):
        """添加同花combo"""
        for suit in self.SUITS:
            combo = f"{r1}{suit}{r2}{suit}"
            self.combos.add(combo)

    def _add_offsuit(self, r1: str, r2: str):
        """添加非同花combo"""
        for s1 in self.SUITS:
            for s2 in self.SUITS:
                if s1 != s2:
                    combo = f"{r1}{s1}{r2}{s2}"
                    self.combos.add(combo)

    def remove_dead_cards(self, dead_cards: List[str]) -> 'Range':
        """
        移除包含死牌的combo

        Args:
            dead_cards: 已知的牌 (如公共牌、对手牌)，格式 ["As", "Kd"]

        Returns:
            self
        """
        # 规范化死牌格式为 "Ac", "Kd" 等
        dead_set = set()
        for card in dead_cards:
            if len(card) == 2:
                # 统一为小写花色
                dead_set.add(card[0].upper() + card[1].lower())

        # 过滤掉包含死牌的combo
        new_combos = set()
        for combo in self.combos:
            # combo格式: "AcKd" (4个字符)
            card1 = combo[0:2]
            card2 = combo[2:4]

            if card1 not in dead_set and card2 not in dead_set:
                new_combos.add(combo)

        self.combos = new_combos
        return self

    def filter_by_board(self, board: List[str], keep_fn) -> 'Range':
        """
        根据公共牌过滤范围

        Args:
            board: 公共牌
            keep_fn: 判断函数 (combo, board) -> bool

        Returns:
            self
        """
        self.combos = {
            combo for combo in self.combos
            if keep_fn(combo, board)
        }
        return self

    def intersect(self, other: 'Range') -> 'Range':
        """范围交集"""
        result = Range()
        result.combos = self.combos & other.combos
        return result

    def union(self, other: 'Range') -> 'Range':
        """范围并集"""
        result = Range()
        result.combos = self.combos | other.combos
        return result

    def subtract(self, other: 'Range') -> 'Range':
        """范围差集 (self - other)"""
        result = Range()
        result.combos = self.combos - other.combos
        return result

    def size(self) -> int:
        """返回combo数量"""
        return len(self.combos)

    def to_list(self) -> List[str]:
        """返回combo列表 (sorted)"""
        return sorted(list(self.combos))

    def __repr__(self):
        return f"Range({self.size()} combos)"

    def __str__(self):
        if self.size() <= 10:
            return f"Range: {', '.join(sorted(self.combos))}"
        else:
            sample = ', '.join(sorted(list(self.combos))[:5])
            return f"Range({self.size()} combos): {sample}... (+{self.size()-5} more)"


# ===== 辅助函数 =====

def parse_range_dict(range_dict: dict) -> Range:
    """
    从preflop_ranges.py的字典格式构建Range

    Args:
        range_dict: {'pairs': ['77+'], 'suited': ['A9s+', 'KTs+'], 'offsuit': [...]}

    Returns:
        Range对象
    """
    parts = []
    if 'pairs' in range_dict:
        parts.extend(range_dict['pairs'])
    if 'suited' in range_dict:
        parts.extend(range_dict['suited'])
    if 'offsuit' in range_dict:
        parts.extend(range_dict['offsuit'])

    return Range(','.join(parts))


def merge_range_dicts(value_dict: dict, bluff_dict: dict) -> Range:
    """
    合并value和bluff范围 (用于3-bet/4-bet)

    Args:
        value_dict: {'pairs': [...], 'suited': [...], 'offsuit': [...]}
        bluff_dict: {'suited': [...]}

    Returns:
        合并后的Range
    """
    value_range = parse_range_dict(value_dict)
    bluff_range = parse_range_dict(bluff_dict)
    return value_range.union(bluff_range)


# ===== 示例用法 =====

if __name__ == '__main__':
    # 测试基础解析
    print("=== 测试范围解析 ===")
    r1 = Range("AA,KK,QQ")
    print(f"AA,KK,QQ: {r1.size()} combos")  # 应该是 18

    r2 = Range("77+")
    print(f"77+: {r2.size()} combos")  # 应该是 48 (8种对*6)

    r3 = Range("AKs")
    print(f"AKs: {r3.size()} combos")  # 应该是 4

    r4 = Range("AKo")
    print(f"AKo: {r4.size()} combos")  # 应该是 12

    r5 = Range("A5s+")
    print(f"A5s+: {r5.size()} combos")  # 应该是 32 (8种kicker*4花色)

    # 测试组合范围
    print("\n=== 测试组合范围 ===")
    utg_open = Range("77+,A9s+,KTs+,QJs,AJo+,KQo")
    print(f"UTG open (tight): {utg_open.size()} combos")
    print(utg_open)

    # 测试死牌移除
    print("\n=== 测试死牌移除 ===")
    r6 = Range("AA,KK")
    print(f"Before: {r6.size()} combos")
    r6.remove_dead_cards(["As", "Kd"])
    print(f"After removing As, Kd: {r6.size()} combos")  # AA少3个，KK少5个

    # 测试集合操作
    print("\n=== 测试集合操作 ===")
    r7 = Range("AA,KK,QQ")
    r8 = Range("QQ,JJ,TT")
    r9 = r7.intersect(r8)
    print(f"Intersection: {r9.size()} combos (should be 6 for QQ)")

    r10 = r7.union(r8)
    print(f"Union: {r10.size()} combos (should be 30 for AA+KK+QQ+JJ+TT)")

    # 测试从字典解析
    print("\n=== 测试从字典解析 ===")
    from preflop_ranges import get_open_range

    utg_normal = get_open_range('UTG', 'normal')
    utg_range = parse_range_dict(utg_normal)
    print(f"UTG normal range: {utg_range.size()} combos")
    print(f"Expected ~21% of 1326 = ~278 combos")
