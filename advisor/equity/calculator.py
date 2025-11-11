#!/usr/bin/env python
"""
Equity计算器 (Equity Calculator)

使用蒙特卡洛模拟计算手牌胜率:
- Hand vs Hand
- Hand vs Range
- Range vs Range (future)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Set, FrozenSet
import random
from itertools import combinations

from .cards import Card, Hand, Board, create_deck, validate_no_duplicates
from .evaluator import HandEvaluator, HandStrength


@dataclass
class EquityResult:
    """
    Equity计算结果

    Attributes:
        win: 获胜概率 (0.0 - 1.0)
        tie: 平局概率
        loss: 失败概率
        iterations: 模拟次数
    """
    win: float
    tie: float
    loss: float
    iterations: int

    @property
    def equity(self) -> float:
        """总Equity (获胜 + 平局/2)"""
        return self.win + self.tie / 2.0

    def __str__(self) -> str:
        return (f"Equity: {self.equity:.1%} "
                f"(Win: {self.win:.1%}, Tie: {self.tie:.1%}, Loss: {self.loss:.1%})")

    def __repr__(self) -> str:
        return f"EquityResult(equity={self.equity:.3f}, iterations={self.iterations})"


class EquityCalculator:
    """
    Equity计算器

    使用蒙特卡洛模拟计算手牌胜率
    """

    def __init__(self, iterations: int = 10000):
        """
        Args:
            iterations: 蒙特卡洛模拟次数 (默认10000)
        """
        self.iterations = iterations

    def calculate_equity(
        self,
        hero_hand: Hand,
        villain_hand: Hand,
        board: Optional[Board] = None,
        iterations: Optional[int] = None
    ) -> EquityResult:
        """
        计算 Hand vs Hand 的Equity

        Args:
            hero_hand: 我方手牌
            villain_hand: 对手手牌
            board: 公共牌 (可选，默认为空)
            iterations: 模拟次数 (可选，默认使用构造器中的值)

        Returns:
            EquityResult对象

        Example:
            calc = EquityCalculator(iterations=10000)
            result = calc.calculate_equity(
                Hand.from_str("AsKs"),
                Hand.from_str("QhQd"),
                Board.from_str("")
            )
            print(result.equity)  # ~0.46
        """
        if board is None:
            board = Board([])

        if iterations is None:
            iterations = self.iterations

        # 验证没有重复牌
        validate_no_duplicates(hero_hand, board)
        validate_no_duplicates(villain_hand, board)

        # 检查两手牌没有重复
        if hero_hand.to_cards_set() & villain_hand.to_cards_set():
            raise ValueError(f"Hero and villain hands overlap: {hero_hand} vs {villain_hand}")

        # 创建可用牌组 (移除已知牌)
        deck = create_deck()
        used_cards = set(hero_hand.cards) | set(villain_hand.cards) | set(board.cards)
        available_cards = [c for c in deck if c not in used_cards]

        # 需要发多少张公共牌
        cards_needed = 5 - len(board.cards)

        wins = 0
        ties = 0
        losses = 0

        for _ in range(iterations):
            # 随机发出剩余公共牌
            random_board = random.sample(available_cards, cards_needed)
            full_board_cards = list(board.cards) + random_board

            # 评估双方最佳5张牌
            hero_cards = list(hero_hand.cards) + full_board_cards
            villain_cards = list(villain_hand.cards) + full_board_cards

            hero_strength = HandEvaluator.evaluate_best_5(hero_cards)
            villain_strength = HandEvaluator.evaluate_best_5(villain_cards)

            # 比较强度
            if hero_strength > villain_strength:
                wins += 1
            elif hero_strength == villain_strength:
                ties += 1
            else:
                losses += 1

        return EquityResult(
            win=wins / iterations,
            tie=ties / iterations,
            loss=losses / iterations,
            iterations=iterations
        )

    def calculate_vs_range(
        self,
        hero_hand: Hand,
        villain_range: List[Hand],
        board: Optional[Board] = None,
        iterations: Optional[int] = None
    ) -> EquityResult:
        """
        计算 Hand vs Range 的Equity

        对range中的每手牌计算equity，然后加权平均

        Args:
            hero_hand: 我方手牌
            villain_range: 对手range (手牌列表)
            board: 公共牌 (可选)
            iterations: 每个对抗的模拟次数

        Returns:
            加权平均的EquityResult

        Example:
            calc = EquityCalculator(iterations=5000)
            villain_range = [
                Hand.from_str("QhQd"),
                Hand.from_str("JhJd"),
                Hand.from_str("ThTd"),
            ]
            result = calc.calculate_vs_range(
                Hand.from_str("AsKs"),
                villain_range,
                Board.from_str("")
            )
        """
        if not villain_range:
            raise ValueError("Villain range cannot be empty")

        if board is None:
            board = Board([])

        if iterations is None:
            iterations = self.iterations

        total_wins = 0.0
        total_ties = 0.0
        total_losses = 0.0
        valid_combos = 0

        # 对range中每手牌计算equity
        for villain_hand in villain_range:
            # 检查是否有重复牌 (如果有，跳过)
            try:
                validate_no_duplicates(hero_hand, board)
                validate_no_duplicates(villain_hand, board)

                if hero_hand.to_cards_set() & villain_hand.to_cards_set():
                    continue  # 跳过重复的组合

            except ValueError:
                continue  # 跳过无效组合

            # 计算vs这手牌的equity
            result = self.calculate_equity(hero_hand, villain_hand, board, iterations)

            total_wins += result.win
            total_ties += result.tie
            total_losses += result.loss
            valid_combos += 1

        if valid_combos == 0:
            raise ValueError("No valid combinations in villain range")

        # 平均equity
        return EquityResult(
            win=total_wins / valid_combos,
            tie=total_ties / valid_combos,
            loss=total_losses / valid_combos,
            iterations=iterations * valid_combos
        )


def quick_equity(
    hero: str,
    villain: str,
    board: str = "",
    iterations: int = 10000
) -> EquityResult:
    """
    便捷函数: 快速计算equity

    Args:
        hero: 我方手牌字符串，如 "AsKs"
        villain: 对手手牌字符串，如 "QhQd"
        board: 公共牌字符串，如 "Js9h2d" (可选)
        iterations: 模拟次数

    Returns:
        EquityResult对象

    Example:
        result = quick_equity("AsKs", "QhQd", "", 10000)
        print(f"AKs vs QQ equity: {result.equity:.1%}")
    """
    hero_hand = Hand.from_str(hero)
    villain_hand = Hand.from_str(villain)
    board_obj = Board.from_str(board) if board else Board([])

    calc = EquityCalculator(iterations=iterations)
    return calc.calculate_equity(hero_hand, villain_hand, board_obj)
