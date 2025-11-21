#!/usr/bin/env python
"""
优化的Equity计算器 (Optimized Equity Calculator)

这是对原始EquityCalculator的替换，使用V2评估器 + 多线程加速
与原始API完全兼容，可以直接替换使用
"""
from __future__ import annotations
from typing import List, Optional
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

from .cards import Hand, Board, create_deck, validate_no_duplicates
from .calculator import EquityResult  # 复用原始的结果类
from .evaluator_fast_v2 import UltraFastHandEvaluator, precompute_if_needed_v2


class OptimizedEquityCalculator:
    """
    优化的Equity计算器

    使用V2评估器 + 多线程，大幅提速同时保持精度
    API与原始EquityCalculator完全兼容
    """

    def __init__(self, iterations: int = 1000, max_workers: int = None):
        """
        Args:
            iterations: 蒙特卡洛模拟次数
            max_workers: 线程池大小（None=自动，通常为CPU核心数）
        """
        self.iterations = iterations
        self.max_workers = max_workers or min(4, os.cpu_count() or 1)  # 默认最多4线程

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
        计算 Hand vs Range 的Equity (多线程加速)

        与原始API完全兼容
        """
        if not villain_range:
            raise ValueError("Villain range cannot be empty")

        if board is None:
            board = Board([])

        if iterations is None:
            iterations = self.iterations

        # 过滤有效的villain hands
        valid_villain_hands = []
        for villain_hand in villain_range:
            try:
                validate_no_duplicates(hero_hand, board)
                validate_no_duplicates(villain_hand, board)

                if not (hero_hand.to_cards_set() & villain_hand.to_cards_set()):
                    valid_villain_hands.append(villain_hand)
            except ValueError:
                continue

        if not valid_villain_hands:
            raise ValueError("No valid combinations in villain range")

        # 单线程处理小范围（避免线程开销）
        if len(valid_villain_hands) <= 5:
            total_wins = 0.0
            total_ties = 0.0
            total_losses = 0.0

            for villain_hand in valid_villain_hands:
                result = self.calculate_equity(hero_hand, villain_hand, board, iterations)
                total_wins += result.win
                total_ties += result.tie
                total_losses += result.loss

            return EquityResult(
                win=total_wins / len(valid_villain_hands),
                tie=total_ties / len(valid_villain_hands),
                loss=total_losses / len(valid_villain_hands),
                iterations=iterations * len(valid_villain_hands)
            )

        # 多线程处理大范围
        def calc_equity_worker(villain_hand):
            try:
                result = self.calculate_equity(hero_hand, villain_hand, board, iterations)
                return (result.win, result.tie, result.loss)
            except Exception:
                return None

        total_wins = 0.0
        total_ties = 0.0
        total_losses = 0.0
        success_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(calc_equity_worker, vh): vh for vh in valid_villain_hands}

            for future in as_completed(futures):
                result = future.result()
                if result:
                    total_wins += result[0]
                    total_ties += result[1]
                    total_losses += result[2]
                    success_count += 1

        if success_count == 0:
            raise ValueError("No valid calculations completed")

        # 平均equity
        return EquityResult(
            win=total_wins / success_count,
            tie=total_ties / success_count,
            loss=total_losses / success_count,
            iterations=iterations * success_count
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
