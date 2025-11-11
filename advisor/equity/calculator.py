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


    def calculate_range_vs_range(
        self,
        hero_range: 'Range',
        villain_range: 'Range',
        board: Optional[Board] = None,
        iterations: Optional[int] = None,
        sample_size: Optional[int] = None
    ) -> EquityResult:
        """
        计算 Range vs Range 的Equity

        由于range vs range可能有大量组合，使用采样方法:
        1. 从各range中随机采样hand combos
        2. 对每个组合计算equity
        3. 加权平均

        Args:
            hero_range: 我方range
            villain_range: 对手range
            board: 公共牌 (可选)
            iterations: 每个对抗的模拟次数
            sample_size: 采样大小 (None=计算所有组合)

        Returns:
            加权平均的EquityResult
        """
        if board is None:
            board = Board([])

        if iterations is None:
            iterations = self.iterations

        # 移除死牌
        dead_cards = set(board.cards)
        hero_valid = hero_range.remove_dead_cards(dead_cards)
        villain_valid = villain_range.remove_dead_cards(dead_cards)

        hero_hands = hero_valid.to_hands()
        villain_hands = villain_valid.to_hands()

        if not hero_hands or not villain_hands:
            raise ValueError("No valid hand combinations after removing dead cards")

        # 决定采样还是全部计算
        total_combos = len(hero_hands) * len(villain_hands)

        if sample_size is None or sample_size >= total_combos:
            # 计算所有组合 - 对每个hero hand vs villain range
            total_wins = 0.0
            total_ties = 0.0
            total_losses = 0.0

            for hero_hand in hero_hands:
                result = self.calculate_vs_range(hero_hand, villain_hands, board, iterations)
                total_wins += result.win
                total_ties += result.tie
                total_losses += result.loss

            num_hero = len(hero_hands)
            return EquityResult(
                win=total_wins / num_hero,
                tie=total_ties / num_hero,
                loss=total_losses / num_hero,
                iterations=iterations * total_combos
            )

        # 采样计算
        total_wins = 0.0
        total_ties = 0.0
        total_losses = 0.0
        valid_samples = 0

        for _ in range(sample_size):
            # 随机选择组合
            hero_hand = random.choice(hero_hands)
            villain_hand = random.choice(villain_hands)

            # 检查是否有重复牌
            if hero_hand.to_cards_set() & villain_hand.to_cards_set():
                continue

            try:
                result = self.calculate_equity(hero_hand, villain_hand, board, iterations)
                total_wins += result.win
                total_ties += result.tie
                total_losses += result.loss
                valid_samples += 1
            except ValueError:
                continue

        if valid_samples == 0:
            raise ValueError("No valid samples found")

        return EquityResult(
            win=total_wins / valid_samples,
            tie=total_ties / valid_samples,
            loss=total_losses / valid_samples,
            iterations=iterations * valid_samples
        )

    def calculate_multiway(
        self,
        hero_hand: Hand,
        villain_ranges: List['Range'],
        board: Optional[Board] = None,
        iterations: Optional[int] = None,
        sample_size: int = 500
    ) -> EquityResult:
        """
        计算多人底池equity (3人或更多玩家)

        在多人底池中，hero需要击败所有对手才能赢得底池。
        如果有平局，pot按平局人数平分。

        Args:
            hero_hand: 我方手牌
            villain_ranges: 多个对手的范围列表 (2个或更多)
            board: 公共牌 (可选)
            iterations: 每次采样的模拟次数 (可选)
            sample_size: 采样大小 (多人底池使用采样以加速)

        Returns:
            EquityResult对象

        Example:
            # 3人底池
            hero = Hand.from_str("AsAh")
            v1_range = Range.from_string("KK,QQ")
            v2_range = Range.from_string("AKs,AQs")

            calc = EquityCalculator()
            result = calc.calculate_multiway(
                hero,
                [v1_range, v2_range],
                Board.from_str("")
            )
            # AA在heads-up是82%，3人约65%
        """
        if len(villain_ranges) < 2:
            raise ValueError("Multiway equity requires at least 2 villain ranges")

        if board is None:
            board = Board([])

        if iterations is None:
            iterations = self.iterations

        # 移除死牌
        dead_cards = set(hero_hand.cards) | set(board.cards)

        villain_hands_lists = []
        for vrange in villain_ranges:
            valid_range = vrange.remove_dead_cards(dead_cards)
            villain_hands_lists.append(valid_range.to_hands())

        # 检查是否有空范围
        if any(not hands for hands in villain_hands_lists):
            raise ValueError("One or more villain ranges became empty after removing dead cards")

        wins = 0.0
        ties = 0.0
        losses = 0.0
        valid_samples = 0

        for _ in range(sample_size):
            # 为每个对手随机选择hand
            villain_hands = []
            used_cards = set(hero_hand.cards) | set(board.cards)
            success = True

            for hands_list in villain_hands_lists:
                # 找到不冲突的hands
                available = [
                    h for h in hands_list
                    if not (h.to_cards_set() & used_cards)
                ]

                if not available:
                    success = False
                    break

                villain_hand = random.choice(available)
                villain_hands.append(villain_hand)
                used_cards |= villain_hand.to_cards_set()

            if not success:
                continue

            # 为这个组合运行Monte Carlo模拟
            sample_wins = 0
            sample_ties = 0
            sample_losses = 0

            for _ in range(iterations):
                # 创建可用牌组
                deck = create_deck()
                all_used = used_cards.copy()
                available_cards = [c for c in deck if c not in all_used]

                # 发出剩余公共牌
                cards_needed = 5 - len(board.cards)
                random_board = random.sample(available_cards, cards_needed)
                full_board_cards = list(board.cards) + random_board

                # 评估所有玩家
                hero_cards = list(hero_hand.cards) + full_board_cards
                hero_strength = HandEvaluator.evaluate_best_5(hero_cards)

                villain_strengths = []
                for vh in villain_hands:
                    v_cards = list(vh.cards) + full_board_cards
                    v_strength = HandEvaluator.evaluate_best_5(v_cards)
                    villain_strengths.append(v_strength)

                # 找到最佳villain strength
                best_villain_strength = max(villain_strengths)

                # 判断结果
                if hero_strength > best_villain_strength:
                    sample_wins += 1
                elif hero_strength == best_villain_strength:
                    # 平局：计算有多少人和hero一样强
                    num_winners = 1 + sum(1 for vs in villain_strengths if vs == hero_strength)
                    sample_ties += 1.0 / num_winners
                else:
                    sample_losses += 1

            # 累加这个采样的结果
            wins += sample_wins / iterations
            ties += sample_ties / iterations
            losses += sample_losses / iterations
            valid_samples += 1

        if valid_samples == 0:
            raise ValueError("No valid hand combinations found in multiway pot")

        return EquityResult(
            win=wins / valid_samples,
            tie=ties / valid_samples,
            loss=losses / valid_samples,
            iterations=iterations * valid_samples
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
