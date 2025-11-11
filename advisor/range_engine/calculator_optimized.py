#!/usr/bin/env python
"""
优化的Equity计算器 (Optimized Equity Calculator)

这是对原始EquityCalculator的替换，使用V2评估器
与原始API完全兼容，可以直接替换使用
"""
from __future__ import annotations
from typing import List, Optional
import random

from .cards import Hand, Board, create_deck, validate_no_duplicates
from .calculator import EquityResult  # 复用原始的结果类
from .evaluator_fast_v2 import UltraFastHandEvaluator, precompute_if_needed_v2


class OptimizedEquityCalculator:
    """
    优化的Equity计算器

    使用V2评估器，速度提升5-8x
    API与原始EquityCalculator完全兼容
    """

    def __init__(self, iterations: int = 1000):
        """
        Args:
            iterations: 蒙特卡洛模拟次数
        """
        self.iterations = iterations

        # 确保查找表已初始化
        precompute_if_needed_v2()

    def calculate_equity(
        self,
        hero_hand: Hand,
        villain_hand: Hand,
        board: Optional[Board] = None,
        iterations: Optional[int] = None
    ) -> EquityResult:
        """
        计算 Hand vs Hand 的Equity

        与原始API完全兼容
        """
        if board is None:
            board = Board([])

        if iterations is None:
            iterations = self.iterations

        # 验证没有重复牌
        validate_no_duplicates(hero_hand, board)
        validate_no_duplicates(villain_hand, board)

        if hero_hand.to_cards_set() & villain_hand.to_cards_set():
            raise ValueError(f"Hero and villain hands overlap")

        # 创建可用牌组
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

            # 评估双方（使用V2评估器，整数score比较）
            hero_cards = list(hero_hand.cards) + full_board_cards
            villain_cards = list(villain_hand.cards) + full_board_cards

            hero_score = UltraFastHandEvaluator.evaluate_best_5_score(hero_cards)
            villain_score = UltraFastHandEvaluator.evaluate_best_5_score(villain_cards)

            # 整数比较（更快）
            if hero_score > villain_score:
                wins += 1
            elif hero_score == villain_score:
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

        与原始API完全兼容
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
            # 检查是否有重复牌
            try:
                validate_no_duplicates(hero_hand, board)
                validate_no_duplicates(villain_hand, board)

                if hero_hand.to_cards_set() & villain_hand.to_cards_set():
                    continue  # 跳过重复的组合

            except ValueError:
                continue

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

        与原始API完全兼容
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
            raise ValueError("No valid hand combinations")

        total_combos = len(hero_hands) * len(villain_hands)

        if sample_size is None or sample_size >= total_combos:
            # 计算所有组合
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
        else:
            # 采样计算
            total_wins = 0.0
            total_ties = 0.0
            total_losses = 0.0
            valid_samples = 0

            for _ in range(sample_size):
                hero_hand = random.choice(hero_hands)
                villain_hand = random.choice(villain_hands)

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
