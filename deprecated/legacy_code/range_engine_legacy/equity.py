"""
范围 Equity 计算

支持:
1. Hand vs Range equity
2. Range vs Range equity
3. 多对手 equity (3+人底池)

使用Monte Carlo采样加速计算
"""
import random
from typing import List, Optional
from treys import Card, Evaluator
from .range import Range


class EquityCalculator:
    """Equity计算器"""

    def __init__(self):
        self.evaluator = Evaluator()
        self.deck = [Card.new(r + s) for r in '23456789TJQKA' for s in 'shdc']

    def hand_vs_range(
        self,
        hero_hand: List[int],
        villain_range: Range,
        board: List[int],
        nsamples: int = 500
    ) -> float:
        """
        计算 手牌 vs 范围 的equity

        Args:
            hero_hand: 我方手牌 [Card, Card] (treys格式)
            villain_range: 对手范围
            board: 公共牌 (可以是0/3/4/5张)
            nsamples: 采样数

        Returns:
            equity (0.0-1.0)
        """
        # 移除已知牌
        dead_cards = self._to_card_strings(hero_hand + board)
        villain_range.remove_dead_cards(dead_cards)

        villain_combos = villain_range.to_list()
        if not villain_combos:
            return 1.0  # 对手没有合法combo

        wins = 0
        ties = 0
        total = 0

        for _ in range(nsamples):
            # 随机选择对手combo
            villain_combo = random.choice(villain_combos)
            villain_hand = self._parse_combo(villain_combo)

            # 模拟发牌到河牌
            final_board = self._complete_board(board, hero_hand + villain_hand)

            # 比较牌力
            hero_score = self.evaluator.evaluate(hero_hand, final_board)
            villain_score = self.evaluator.evaluate(villain_hand, final_board)

            if hero_score < villain_score:  # treys: 越小越好
                wins += 1
            elif hero_score == villain_score:
                ties += 1

            total += 1

        return (wins + ties * 0.5) / total if total > 0 else 0.5

    def range_vs_range(
        self,
        hero_range: Range,
        villain_range: Range,
        board: List[int],
        nsamples: int = 500
    ) -> float:
        """
        计算 范围 vs 范围 的equity

        采样方法:
        1. 从hero范围随机选combo
        2. 从villain范围随机选combo (移除冲突)
        3. 模拟到河牌比较

        Args:
            hero_range: 我方范围
            villain_range: 对手范围
            board: 公共牌
            nsamples: 采样数

        Returns:
            equity (0.0-1.0)
        """
        dead_cards = self._to_card_strings(board)
        hero_range.remove_dead_cards(dead_cards)
        villain_range.remove_dead_cards(dead_cards)

        hero_combos = hero_range.to_list()
        villain_combos = villain_range.to_list()

        if not hero_combos:
            return 0.0
        if not villain_combos:
            return 1.0

        wins = 0
        ties = 0
        total = 0

        for _ in range(nsamples):
            # 随机选择双方combo
            hero_combo = random.choice(hero_combos)
            hero_hand = self._parse_combo(hero_combo)

            # 移除与hero冲突的villain combos
            villain_available = [
                c for c in villain_combos
                if not self._combo_conflicts(c, hero_combo)
            ]

            if not villain_available:
                continue

            villain_combo = random.choice(villain_available)
            villain_hand = self._parse_combo(villain_combo)

            # 模拟发牌
            final_board = self._complete_board(board, hero_hand + villain_hand)

            # 比较牌力
            hero_score = self.evaluator.evaluate(hero_hand, final_board)
            villain_score = self.evaluator.evaluate(villain_hand, final_board)

            if hero_score < villain_score:
                wins += 1
            elif hero_score == villain_score:
                ties += 1

            total += 1

        return (wins + ties * 0.5) / total if total > 0 else 0.5

    def multiway_equity(
        self,
        hero_hand: List[int],
        villain_ranges: List[Range],
        board: List[int],
        nsamples: int = 300
    ) -> float:
        """
        多人底池equity计算

        Args:
            hero_hand: 我方手牌
            villain_ranges: 多个对手的范围列表
            board: 公共牌
            nsamples: 采样数 (多人底池计算量大，减少采样)

        Returns:
            equity (0.0-1.0)
        """
        dead_cards = self._to_card_strings(hero_hand + board)

        # 移除死牌
        for vrange in villain_ranges:
            vrange.remove_dead_cards(dead_cards)

        villain_combos_list = [vr.to_list() for vr in villain_ranges]

        # 检查是否有空范围
        if any(not combos for combos in villain_combos_list):
            return 1.0

        wins = 0
        ties = 0
        total = 0

        for _ in range(nsamples):
            # 为每个对手随机选combo
            villain_hands = []
            used_cards = set(self._to_card_strings(hero_hand))

            success = True
            for combos in villain_combos_list:
                available = [
                    c for c in combos
                    if not any(c[i:i+2] in used_cards for i in [0, 2])
                ]

                if not available:
                    success = False
                    break

                combo = random.choice(available)
                villain_hands.append(self._parse_combo(combo))
                used_cards.add(combo[0:2])
                used_cards.add(combo[2:4])

            if not success:
                continue

            # 模拟发牌
            all_hands = [hand for hand in villain_hands]
            all_hands_flat = [card for hand in all_hands for card in hand]
            final_board = self._complete_board(board, hero_hand + all_hands_flat)

            # 评估所有玩家
            hero_score = self.evaluator.evaluate(hero_hand, final_board)
            villain_scores = [
                self.evaluator.evaluate(vh, final_board)
                for vh in villain_hands
            ]

            # 判断胜负
            best_villain = min(villain_scores)

            if hero_score < best_villain:
                wins += 1
            elif hero_score == best_villain:
                # 平局需要分pot
                num_winners = 1 + sum(1 for s in villain_scores if s == hero_score)
                ties += 1.0 / num_winners
            # else: hero输了

            total += 1

        return (wins + ties) / total if total > 0 else 0.0

    # ===== 辅助方法 =====

    def _complete_board(self, board: List[int], dead_cards: List[int]) -> List[int]:
        """
        发牌到河牌 (5张)

        Args:
            board: 当前公共牌
            dead_cards: 不能发的牌

        Returns:
            完整的5张公共牌
        """
        if len(board) >= 5:
            return board[:5]

        available = [c for c in self.deck if c not in dead_cards and c not in board]
        needed = 5 - len(board)

        if len(available) < needed:
            # 不够牌了 (理论上不应该发生)
            return board

        return board + random.sample(available, needed)

    def _parse_combo(self, combo: str) -> List[int]:
        """
        解析combo字符串为treys Card

        Args:
            combo: "AcKd" 格式

        Returns:
            [Card, Card]
        """
        return [
            Card.new(combo[0:2]),
            Card.new(combo[2:4])
        ]

    def _to_card_strings(self, cards: List[int]) -> List[str]:
        """
        转换treys Card为字符串

        Args:
            cards: [Card, Card, ...]

        Returns:
            ["Ac", "Kd", ...]
        """
        return [Card.int_to_str(c) for c in cards]

    def _combo_conflicts(self, combo1: str, combo2: str) -> bool:
        """
        检查两个combo是否有重复的牌

        Args:
            combo1: "AcKd"
            combo2: "AhQs"

        Returns:
            True if conflict
        """
        cards1 = {combo1[0:2], combo1[2:4]}
        cards2 = {combo2[0:2], combo2[2:4]}
        return bool(cards1 & cards2)


# ===== 示例用法 =====

if __name__ == '__main__':
    from .range import Range

    calc = EquityCalculator()

    # 测试 Hand vs Range
    print("=== Hand vs Range ===")
    hero_hand = [Card.new('As'), Card.new('Kd')]
    villain_range = Range("QQ,JJ,TT,AQs,AJs,KQs")
    board = [Card.new('Ah'), Card.new('Ts'), Card.new('3c')]

    equity = calc.hand_vs_range(hero_hand, villain_range, board, nsamples=1000)
    print(f"AsKd vs {villain_range} on AhTs3c: {equity:.3f}")

    # 测试 Range vs Range
    print("\n=== Range vs Range ===")
    hero_range = Range("AA,KK,AKs")
    villain_range = Range("QQ,JJ,TT,99")
    board = []

    equity = calc.range_vs_range(hero_range, villain_range, board, nsamples=1000)
    print(f"{hero_range} vs {villain_range} preflop: {equity:.3f}")
    print("Expected: ~0.80 (AA/KK/AK dominate QQ-99)")

    # 测试多人底池
    print("\n=== Multiway Equity ===")
    hero_hand = [Card.new('As'), Card.new('Ah')]
    v1_range = Range("KK,QQ")
    v2_range = Range("AKs,AQs")
    board = []

    equity = calc.multiway_equity(hero_hand, [v1_range, v2_range], board, nsamples=500)
    print(f"AA vs [KK,QQ] vs [AKs,AQs] preflop: {equity:.3f}")
    print("Expected: ~0.65 (AA strong但面对2个对手equity下降)")
