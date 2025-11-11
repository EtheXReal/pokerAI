#!/usr/bin/env python
"""
测试Range的"+"符号解析功能

验证是否正确实现:
- "77+" (对子范围)
- "A5s+" (同花范围)
- "ATo+" (非同花范围)
- 组合表达式
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import unittest
from advisor.equity import Range


class TestRangePlusNotation(unittest.TestCase):
    """测试Range的+符号解析"""

    def test_pair_plus_77(self):
        """测试 "77+" - 应该包含77,88,99,TT,JJ,QQ,KK,AA"""
        range_obj = Range.from_string("77+")
        combos = list(range_obj)

        # 8种对子 * 6种组合 = 48 combos
        self.assertEqual(len(combos), 48,
                        f"77+ should have 48 combos, got {len(combos)}")

        # 验证包含AA (应该有6种组合)
        aa_combos = [c for c in combos
                    if c.hand.cards[0].rank.value == 14 and c.hand.cards[1].rank.value == 14]
        self.assertEqual(len(aa_combos), 6, "AA should have 6 combos")

        # 验证包含77 (应该有6种组合)
        sevens_combos = [c for c in combos
                        if c.hand.cards[0].rank.value == 7 and c.hand.cards[1].rank.value == 7]
        self.assertEqual(len(sevens_combos), 6, "77 should have 6 combos")

        # 验证不包含66
        sixes_combos = [c for c in combos
                       if c.hand.cards[0].rank.value == 6 and c.hand.cards[1].rank.value == 6]
        self.assertEqual(len(sixes_combos), 0, "Should not contain 66")

    def test_pair_plus_qq(self):
        """测试 "QQ+" - 应该包含QQ,KK,AA"""
        range_obj = Range.from_string("QQ+")
        combos = list(range_obj)

        # 3种对子 * 6种组合 = 18 combos
        self.assertEqual(len(combos), 18,
                        f"QQ+ should have 18 combos, got {len(combos)}")

    def test_suited_plus_a5s(self):
        """测试 "A5s+" - 应该包含A5s,A6s,A7s,A8s,A9s,ATs,AJs,AQs,AKs"""
        range_obj = Range.from_string("A5s+")
        combos = list(range_obj)

        # 9种kicker * 4种花色 = 36 combos
        self.assertEqual(len(combos), 36,
                        f"A5s+ should have 36 combos, got {len(combos)}")

        # 验证都是同花 (card1和card2花色相同)
        for combo in combos:
            self.assertEqual(combo.hand.cards[0].suit, combo.hand.cards[1].suit,
                           f"Combo {combo} should be suited")

        # 验证都是Ace high
        for combo in combos:
            self.assertEqual(combo.hand.cards[0].rank.value, 14,
                           f"Combo {combo} should have Ace as high card")

        # 验证包含A5s
        a5s_combos = [c for c in combos
                     if c.hand.cards[0].rank.value == 14 and c.hand.cards[1].rank.value == 5
                     and c.hand.cards[0].suit == c.hand.cards[1].suit]
        self.assertEqual(len(a5s_combos), 4, "Should have 4 A5s combos (one per suit)")

        # 验证不包含A4s
        a4s_combos = [c for c in combos
                     if c.hand.cards[0].rank.value == 14 and c.hand.cards[1].rank.value == 4
                     and c.hand.cards[0].suit == c.hand.cards[1].suit]
        self.assertEqual(len(a4s_combos), 0, "Should not contain A4s")

    def test_offsuit_plus_ato(self):
        """测试 "ATo+" - 应该包含ATo,AJo,AQo,AKo"""
        range_obj = Range.from_string("ATo+")
        combos = list(range_obj)

        # 4种kicker * 12种花色组合 = 48 combos
        self.assertEqual(len(combos), 48,
                        f"ATo+ should have 48 combos, got {len(combos)}")

        # 验证都是非同花
        for combo in combos:
            self.assertNotEqual(combo.hand.cards[0].suit, combo.hand.cards[1].suit,
                              f"Combo {combo} should be offsuit")

        # 验证都是Ace high
        for combo in combos:
            self.assertEqual(combo.hand.cards[0].rank.value, 14,
                           f"Combo {combo} should have Ace as high card")

        # 验证包含ATo (应该有12种组合)
        ato_combos = [c for c in combos
                     if c.hand.cards[0].rank.value == 14 and c.hand.cards[1].rank.value == 10
                     and c.hand.cards[0].suit != c.hand.cards[1].suit]
        self.assertEqual(len(ato_combos), 12, "Should have 12 ATo combos")

    def test_combined_notation(self):
        """测试组合表达式 "QQ+,AK" """
        range_obj = Range.from_string("QQ+,AK")
        combos = list(range_obj)

        # QQ+ = 18 combos (QQ,KK,AA)
        # AK = 16 combos (4 suited + 12 offsuit)
        # Total = 34 combos
        self.assertEqual(len(combos), 34,
                        f"QQ+,AK should have 34 combos, got {len(combos)}")

    def test_tight_utg_range(self):
        """测试紧的UTG范围 "77+,A9s+,KTs+,QJs,AJo+,KQo" """
        range_obj = Range.from_string("77+,A9s+,KTs+,QJs,AJo+,KQo")
        combos = list(range_obj)

        # 这是一个大约12-15%的范围
        # 总共1326个combo，12%约159个
        self.assertGreater(len(combos), 130, "UTG range should have >130 combos")
        self.assertLess(len(combos), 200, "UTG range should have <200 combos")

        print(f"\nUTG tight range: {len(combos)} combos ({len(combos)/1326*100:.1f}% of all hands)")

    def test_premium_range(self):
        """测试premium范围 (使用helper函数)"""
        from advisor.equity.range import create_premium_range

        range_obj = create_premium_range()
        combos = list(range_obj)

        # QQ+,AK = 34 combos
        self.assertEqual(len(combos), 34,
                        f"Premium range should have 34 combos, got {len(combos)}")

    def test_broadway_range(self):
        """测试broadway范围 (使用helper函数)"""
        from advisor.equity.range import create_broadw_range

        range_obj = create_broadw_range()
        combos = list(range_obj)

        # TT+,ATs+,ATo+,KQs,KQo
        # TT+ = 30 combos (TT,JJ,QQ,KK,AA)
        # ATs+ = 16 combos (AT,AJ,AQ,AK suited)
        # ATo+ = 48 combos
        # KQs = 4 combos
        # KQo = 12 combos
        # Total = 110 combos
        self.assertEqual(len(combos), 110,
                        f"Broadway range should have 110 combos, got {len(combos)}")

    def test_any_pair_range(self):
        """测试所有对子 "22+" """
        from advisor.equity.range import create_any_pair_range

        range_obj = create_any_pair_range()
        combos = list(range_obj)

        # 13种对子 * 6种组合 = 78 combos
        self.assertEqual(len(combos), 78,
                        f"22+ should have 78 combos, got {len(combos)}")

    def test_single_pair_aa(self):
        """测试单个对子 "AA" (无+符号)"""
        range_obj = Range.from_string("AA")
        combos = list(range_obj)

        # AA = 6 combos
        self.assertEqual(len(combos), 6,
                        f"AA should have 6 combos, got {len(combos)}")

    def test_single_hand_aks(self):
        """测试单个手牌 "AKs" (无+符号)"""
        range_obj = Range.from_string("AKs")
        combos = list(range_obj)

        # AKs = 4 combos
        self.assertEqual(len(combos), 4,
                        f"AKs should have 4 combos, got {len(combos)}")

    def test_single_hand_ako(self):
        """测试单个手牌 "AKo" (无+符号)"""
        range_obj = Range.from_string("AKo")
        combos = list(range_obj)

        # AKo = 12 combos
        self.assertEqual(len(combos), 12,
                        f"AKo should have 12 combos, got {len(combos)}")


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)
