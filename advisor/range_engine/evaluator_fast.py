#!/usr/bin/env python
"""
快速手牌评估器 (Fast Hand Evaluator)

性能优化版本：
1. 预计算查找表：所有C(52,5)=2,598,960种5张牌组合
2. 位运算表示：快速哈希和比较
3. 最小化内存：使用紧凑编码

预期加速：10-20x
"""
from __future__ import annotations
import pickle
import os
from pathlib import Path
from typing import List, Tuple, Optional
from itertools import combinations
from collections import Counter

from .cards import Card, Rank, Suit
from .evaluator import HandStrength, HandRank


# ===== 位运算卡牌表示 =====

def card_to_int(card: Card) -> int:
    """
    将Card转换为整数表示 (0-51)

    编码: rank * 4 + suit
    - 2c=0, 2d=1, 2h=2, 2s=3
    - 3c=4, 3d=5, 3h=6, 3s=7
    - ...
    - Ac=48, Ad=49, Ah=50, As=51
    """
    rank_val = int(card.rank) - 2  # 2→0, 3→1, ..., A→12
    suit_val = list(Suit).index(card.suit)  # C→0, D→1, H→2, S→3
    return rank_val * 4 + suit_val


def int_to_card(n: int) -> Card:
    """整数转回Card"""
    rank_val = n // 4 + 2
    suit_val = n % 4
    rank = Rank(rank_val)
    suit = list(Suit)[suit_val]
    return Card(rank, suit)


def five_cards_to_key(cards: List[Card]) -> int:
    """
    将5张牌转换为唯一的整数key（用于查表）

    使用位掩码：52位，每位表示一张牌是否存在
    """
    mask = 0
    for card in cards:
        card_int = card_to_int(card)
        mask |= (1 << card_int)
    return mask


def seven_cards_to_best_five_key(cards: List[Card]) -> int:
    """
    从7张牌中找出最佳5张，返回key

    注意：这里仍需要枚举21种组合，但比较使用查表
    """
    from .evaluator import HandEvaluator

    best_strength = None
    best_five = None

    for five_cards in combinations(cards, 5):
        key = five_cards_to_key(list(five_cards))
        strength = LOOKUP_TABLE.get(key)

        if strength is None:
            # 如果查表失败，回退到原始评估
            from .evaluator import HandEvaluator
            strength = HandEvaluator.evaluate(list(five_cards))

        if best_strength is None or strength > best_strength:
            best_strength = strength
            best_five = five_cards

    return best_strength


# ===== 查找表生成 =====

class LookupTableGenerator:
    """查找表生成器"""

    @staticmethod
    def generate_full_table() -> dict:
        """
        生成完整查找表：所有C(52,5)=2,598,960种5张牌

        Returns:
            {card_mask: HandStrength}
        """
        from .evaluator import HandEvaluator
        from .cards import create_deck

        print("生成HandEvaluator查找表...")
        print(f"总组合数: C(52,5) = 2,598,960")

        deck = create_deck()
        lookup_table = {}

        count = 0
        total = 2598960

        for five_cards in combinations(deck, 5):
            # 评估这5张牌
            strength = HandEvaluator.evaluate(list(five_cards))

            # 计算key
            key = five_cards_to_key(list(five_cards))

            # 存储
            lookup_table[key] = strength

            count += 1
            if count % 100000 == 0:
                print(f"进度: {count}/{total} ({count*100/total:.1f}%)")

        print(f"完成！生成了 {len(lookup_table)} 个条目")
        return lookup_table

    @staticmethod
    def save_table(table: dict, filepath: str):
        """保存查找表到文件"""
        print(f"保存查找表到: {filepath}")
        with open(filepath, 'wb') as f:
            pickle.dump(table, f, protocol=pickle.HIGHEST_PROTOCOL)

        # 检查文件大小
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"文件大小: {size_mb:.1f} MB")

    @staticmethod
    def load_table(filepath: str) -> dict:
        """从文件加载查找表"""
        print(f"加载查找表从: {filepath}")
        with open(filepath, 'rb') as f:
            table = pickle.load(f)
        print(f"加载了 {len(table)} 个条目")
        return table


# ===== 全局查找表 =====

LOOKUP_TABLE: Optional[dict] = None
LOOKUP_TABLE_PATH = Path(__file__).parent / "evaluator_lookup_table.pkl"


def initialize_lookup_table():
    """初始化查找表（首次运行时生成，后续加载）"""
    global LOOKUP_TABLE

    if LOOKUP_TABLE is not None:
        return  # 已经初始化

    if LOOKUP_TABLE_PATH.exists():
        # 加载已有的表
        LOOKUP_TABLE = LookupTableGenerator.load_table(str(LOOKUP_TABLE_PATH))
    else:
        # 首次运行，生成表
        print("首次运行，正在生成查找表（约需1-2分钟）...")
        LOOKUP_TABLE = LookupTableGenerator.generate_full_table()
        LookupTableGenerator.save_table(LOOKUP_TABLE, str(LOOKUP_TABLE_PATH))
        print("查找表生成完成！")


# ===== 快速评估器 =====

class FastHandEvaluator:
    """
    快速手牌评估器

    使用预计算查找表，速度提升10-20x
    """

    @staticmethod
    def evaluate(cards: List[Card]) -> HandStrength:
        """
        评估5张牌（查表版本）

        Args:
            cards: 5张牌

        Returns:
            HandStrength对象
        """
        if len(cards) != 5:
            raise ValueError(f"Must evaluate exactly 5 cards, got {len(cards)}")

        # 确保查找表已初始化
        if LOOKUP_TABLE is None:
            initialize_lookup_table()

        # 计算key
        key = five_cards_to_key(cards)

        # 查表
        strength = LOOKUP_TABLE.get(key)

        if strength is None:
            # 理论上不应该发生，回退到原始方法
            from .evaluator import HandEvaluator
            return HandEvaluator.evaluate(cards)

        return strength

    @staticmethod
    def evaluate_best_5(cards: List[Card]) -> HandStrength:
        """
        从7张牌中评估最佳5张（优化版本）

        Args:
            cards: 7张牌

        Returns:
            最佳5张牌的强度
        """
        if len(cards) != 7:
            raise ValueError(f"Must evaluate exactly 7 cards, got {len(cards)}")

        # 确保查找表已初始化
        if LOOKUP_TABLE is None:
            initialize_lookup_table()

        best_strength = None

        # 枚举所有C(7,5)=21种组合
        for five_cards in combinations(cards, 5):
            # 计算key
            key = five_cards_to_key(list(five_cards))

            # 查表
            strength = LOOKUP_TABLE.get(key)

            if strength is None:
                # 回退
                from .evaluator import HandEvaluator
                strength = HandEvaluator.evaluate(list(five_cards))

            # 更新最佳
            if best_strength is None or strength > best_strength:
                best_strength = strength

        return best_strength


# ===== 便捷函数 =====

def evaluate_hand_fast(cards: List[Card]) -> HandStrength:
    """
    便捷函数: 快速评估手牌

    Args:
        cards: 5张或7张牌

    Returns:
        HandStrength对象
    """
    if len(cards) == 5:
        return FastHandEvaluator.evaluate(cards)
    elif len(cards) == 7:
        return FastHandEvaluator.evaluate_best_5(cards)
    else:
        raise ValueError(f"Must provide 5 or 7 cards, got {len(cards)}")


# ===== 初始化 =====

def precompute_if_needed():
    """检查并预计算查找表（如果需要）"""
    if not LOOKUP_TABLE_PATH.exists():
        print("=" * 60)
        print("首次运行检测到！")
        print("正在生成HandEvaluator查找表（约需1-2分钟）...")
        print("这只需要运行一次，后续会直接加载。")
        print("=" * 60)
        initialize_lookup_table()
        print("=" * 60)
        print("查找表生成完成！后续运行将直接加载。")
        print("=" * 60)
