#!/usr/bin/env python
"""
测试 Range 集合操作

验证功能:
- Range.intersect() - 交集
- Range.union() - 并集
- Range.subtract() - 差集
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest
from advisor.equity import Range


class TestRangeSetOperations(unittest.TestCase):
    """测试Range集合操作"""

    def test_intersect_basic(self):
        """测试基础交集操作"""
        range1 = Range.from_string("AA,KK,QQ,AKs")
        range2 = Range.from_string("QQ,JJ,AKs,AQs")

        overlap = range1.intersect(range2)

        # 共同部分: QQ, AKs
        # QQ = 6 combos, AKs = 4 combos
        self.assertEqual(len(overlap), 10, "Should have QQ (6) + AKs (4) = 10 combos")

        print(f"\nIntersection of (AA,KK,QQ,AKs) ∩ (QQ,JJ,AKs,AQs): {len(overlap)} combos")

    def test_intersect_no_overlap(self):
        """测试无交集的情况"""
        range1 = Range.from_string("AA,KK")
        range2 = Range.from_string("QQ,JJ")

        overlap = range1.intersect(range2)

        self.assertEqual(len(overlap), 0, "Should have no overlap")

        print(f"Intersection of (AA,KK) ∩ (QQ,JJ): {len(overlap)} combos (empty)")

    def test_intersect_identical(self):
        """测试相同范围的交集"""
        range1 = Range.from_string("AA,KK,QQ")
        range2 = Range.from_string("AA,KK,QQ")

        overlap = range1.intersect(range2)

        # 应该等于原范围
        self.assertEqual(len(overlap), len(range1))
        self.assertEqual(len(overlap), 18, "Should have 18 combos (3 pairs * 6)")

        print(f"Intersection of identical ranges: {len(overlap)} combos")

    def test_union_basic(self):
        """测试基础并集操作"""
        value_range = Range.from_string("AA,KK")
        bluff_range = Range.from_string("AKs,A5s")

        full_range = value_range.union(bluff_range)

        # AA = 6, KK = 6, AKs = 4, A5s = 4
        # Total = 20 combos
        self.assertEqual(len(full_range), 20, "Should have 20 combos")

        print(f"\nUnion of (AA,KK) ∪ (AKs,A5s): {len(full_range)} combos")

    def test_union_with_overlap(self):
        """测试有重叠的并集"""
        range1 = Range.from_string("AA,KK,QQ")
        range2 = Range.from_string("QQ,JJ,TT")

        merged = range1.union(range2)

        # AA,KK,QQ,JJ,TT = 5 pairs * 6 = 30 combos
        self.assertEqual(len(merged), 30, "Should have 30 combos (5 pairs)")

        print(f"Union of (AA,KK,QQ) ∪ (QQ,JJ,TT): {len(merged)} combos")

    def test_union_identical(self):
        """测试相同范围的并集"""
        range1 = Range.from_string("AA,KK")
        range2 = Range.from_string("AA,KK")

        merged = range1.union(range2)

        # 应该等于原范围
        self.assertEqual(len(merged), len(range1))
        self.assertEqual(len(merged), 12, "Should have 12 combos (2 pairs * 6)")

        print(f"Union of identical ranges: {len(merged)} combos")

    def test_subtract_basic(self):
        """测试基础差集操作"""
        open_range = Range.from_string("77+")  # 77到AA的对子
        weak_pairs = Range.from_string("77,88,99")

        vs_3bet = open_range.subtract(weak_pairs)

        # 77+ = 8 pairs = 48 combos
        # 减去77,88,99 = 3 pairs = 18 combos
        # 剩余 = 30 combos (TT,JJ,QQ,KK,AA)
        self.assertEqual(len(vs_3bet), 30, "Should have 30 combos (5 pairs)")

        print(f"\nSubtract (77+) - (77,88,99): {len(vs_3bet)} combos")

    def test_subtract_no_overlap(self):
        """测试无重叠的差集"""
        range1 = Range.from_string("AA,KK")
        range2 = Range.from_string("QQ,JJ")

        result = range1.subtract(range2)

        # 没有重叠，应该保持原样
        self.assertEqual(len(result), len(range1))
        self.assertEqual(len(result), 12, "Should have 12 combos (unchanged)")

        print(f"Subtract (AA,KK) - (QQ,JJ): {len(result)} combos (no change)")

    def test_subtract_complete(self):
        """测试完全移除的差集"""
        range1 = Range.from_string("AA,KK,QQ")
        range2 = Range.from_string("AA,KK,QQ")

        result = range1.subtract(range2)

        # 移除所有，应该为空
        self.assertEqual(len(result), 0, "Should be empty")

        print(f"Subtract identical ranges: {len(result)} combos (empty)")

    def test_complex_combination(self):
        """测试复杂的集合组合操作"""
        # UTG open range
        utg_open = Range.from_string("77+,AJs+,KQs")

        # 面对3-bet，移除弱手牌
        weak_hands = Range.from_string("77,88,99,AJs")
        vs_3bet_continue = utg_open.subtract(weak_hands)

        # 与premium range取交集
        premium = Range.from_string("QQ+,AK")
        premium_in_range = vs_3bet_continue.intersect(premium)

        print(f"\nComplex operations:")
        print(f"  UTG open: {len(utg_open)} combos")
        print(f"  After removing weak hands: {len(vs_3bet_continue)} combos")
        print(f"  Premium hands in range: {len(premium_in_range)} combos")

        # 验证结果合理
        self.assertGreater(len(vs_3bet_continue), 0, "Should have hands after removal")
        self.assertLess(len(vs_3bet_continue), len(utg_open), "Should be smaller than original")
        self.assertLessEqual(len(premium_in_range), len(vs_3bet_continue),
                            "Premium subset should be <= continue range")

    def test_range_narrowing(self):
        """测试根据对手行动缩窄范围"""
        # 初始范围：对手可能有的范围
        initial_range = Range.from_string("22+,ATs+,KTs+,QJs,AJo+,KQo")

        # Flop: 对手check，移除强牌
        strong_hands = Range.from_string("AA,KK,QQ")
        after_check = initial_range.subtract(strong_hands)

        # Turn: 对手bet，可能有的范围
        betting_range = Range.from_string("TT+,ATs+")
        possible_hands = after_check.intersect(betting_range)

        print(f"\nRange narrowing:")
        print(f"  Initial range: {len(initial_range)} combos")
        print(f"  After check (removed premiums): {len(after_check)} combos")
        print(f"  Possible betting hands: {len(possible_hands)} combos")

        self.assertLess(len(after_check), len(initial_range), "Range should narrow after check")
        self.assertLess(len(possible_hands), len(after_check), "Range should narrow further")

    def test_polarized_range_construction(self):
        """测试构建极化范围 (value + bluffs)"""
        # Value hands
        value = Range.from_string("AA,KK,QQ")

        # Bluff hands
        bluffs = Range.from_string("A5s,A4s,A3s,A2s")

        # 极化范围 = value ∪ bluffs
        polarized = value.union(bluffs)

        # Value: 18 combos, Bluffs: 16 combos
        # Total: 34 combos
        self.assertEqual(len(polarized), 34, "Should have 34 combos")

        print(f"\nPolarized range (value + bluffs): {len(polarized)} combos")

    def test_set_operations_preserve_independence(self):
        """测试集合操作不影响原始范围"""
        original = Range.from_string("AA,KK,QQ")
        other = Range.from_string("QQ,JJ")

        # 执行各种操作
        intersect_result = original.intersect(other)
        union_result = original.union(other)
        subtract_result = original.subtract(other)

        # 原始范围不应改变
        self.assertEqual(len(original), 18, "Original range should be unchanged")

        print(f"\nOriginal range preserved: {len(original)} combos")
        print(f"  After intersect: original still {len(original)} combos")
        print(f"  After union: original still {len(original)} combos")
        print(f"  After subtract: original still {len(original)} combos")


if __name__ == '__main__':
    unittest.main(verbosity=2)
