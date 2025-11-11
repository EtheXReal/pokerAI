#!/usr/bin/env python
"""
快速性能验证 - 50手测试，实时进度

用于快速验证AI是否能盈利，不追求精确的BB/100数值
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import random
import time
from advisor.range_engine import Hand, create_deck
from advisor.range_engine.evaluator import HandEvaluator
from advisor.strategy_engine import ProLevelAdvisor, GameState
from advisor.opponent_modeling import PlayerType


class FastAI:
    """极速AI（iterations=30）"""
    def __init__(self):
        self.advisor = ProLevelAdvisor(exploit_weight=0.4)
        self.advisor.equity_calculator.iterations = 30  # 极低，但够快

    def decide(self, hand: Hand, position: str, pot: float, stack: float, opp_type=None):
        try:
            gs = GameState(
                street='preflop', position=position,
                is_in_position=(position == 'BTN'),
                hero_hand=hand, pot_size=pot,
                effective_stack=stack, hero_stack=stack,
                opponent_type=opp_type or PlayerType.UNKNOWN
            )
            decision = self.advisor.advise(gs)
            action = decision.recommended_action.lower()

            if 'fold' in action:
                return 'fold', 0.0
            elif 'raise' in action or 'r' in action:
                return 'raise', max(3.0, pot * 0.5)
            else:
                return 'call', 0.0
        except:
            # Fallback
            rank_sum = hand.cards[0].rank.value + hand.cards[1].rank.value
            if rank_sum >= 20: return 'raise', 3.0
            elif rank_sum >= 14: return 'call', 0.0
            else: return 'fold', 0.0


class RandomBot:
    def decide(self, hand, position, pot, stack):
        r = random.random()
        if r < 0.4: return 'fold', 0.0
        elif r < 0.55: return 'raise', 3.0
        else: return 'call', 0.0


class SimpleBot:
    def decide(self, hand, position, pot, stack):
        r1, r2 = hand.cards[0].rank.value, hand.cards[1].rank.value
        if r1 == r2 and r1 >= 10: return 'raise', 3.0
        if max(r1, r2) == 14 and min(r1, r2) >= 12: return 'raise', 3.0
        if max(r1, r2) >= 11: return 'call', 0.0
        return 'fold', 0.0


def showdown(ai_hand, opp_hand, ai_inv, opp_inv, deck):
    board = deck[4:9]
    ai_str = HandEvaluator.evaluate_best_5(list(ai_hand.cards) + board)
    opp_str = HandEvaluator.evaluate_best_5(list(opp_hand.cards) + board)
    if ai_str > opp_str: return opp_inv
    elif ai_str < opp_str: return -ai_inv
    else: return 0.0


def play_hand(ai, opponent, ai_pos):
    sb, bb = 0.5, 1.0
    deck = create_deck()
    random.shuffle(deck)
    ai_hand, opp_hand = Hand([deck[0], deck[1]]), Hand([deck[2], deck[3]])

    if ai_pos == 'BTN':
        ai_inv, opp_inv = sb, bb
        ai_act, ai_amt = ai.decide(ai_hand, 'BTN', sb + bb, 100 - sb)
        if ai_act == 'fold': return -sb
        elif ai_act == 'call':
            ai_inv = bb
            return showdown(ai_hand, opp_hand, ai_inv, opp_inv, deck)
        else:  # raise
            ai_inv = ai_amt
            opp_act, _ = opponent.decide(opp_hand, 'BB', ai_amt + bb, 100 - bb)
            if opp_act == 'fold': return bb
            else:
                opp_inv = ai_amt
                return showdown(ai_hand, opp_hand, ai_inv, opp_inv, deck)
    else:  # BB
        ai_inv, opp_inv = bb, sb
        opp_act, opp_amt = opponent.decide(opp_hand, 'BTN', sb + bb, 100 - sb)
        if opp_act == 'fold': return sb
        elif opp_act == 'call':
            opp_inv = bb
            return showdown(ai_hand, opp_hand, ai_inv, opp_inv, deck)
        else:  # raise
            opp_inv = opp_amt
            ai_act, _ = ai.decide(ai_hand, 'BB', opp_amt + bb, 100 - bb)
            if ai_act == 'fold': return -bb
            else:
                ai_inv = opp_amt
                return showdown(ai_hand, opp_hand, ai_inv, opp_inv, deck)


def quick_test(opponent, name, hands=50):
    """快速测试"""
    print(f"\n{'='*60}")
    print(f"🎯 vs {name} ({hands}手快速测试)")
    print(f"{'='*60}")

    ai = FastAI()
    total = 0.0
    start = time.time()

    for i in range(hands):
        ai_pos = 'BTN' if i % 2 == 0 else 'BB'
        result = play_hand(ai, opponent, ai_pos)
        total += result

        # 实时进度
        if (i + 1) % 10 == 0 or i == hands - 1:
            bb100 = (total / (i + 1)) * 100
            elapsed = time.time() - start
            speed = (i + 1) / elapsed if elapsed > 0 else 0
            remaining = (hands - i - 1) / speed if speed > 0 else 0

            print(f"  [{i+1:3d}/{hands}] "
                  f"盈亏: {total:+6.2f}BB  "
                  f"BB/100: {bb100:+6.2f}  "
                  f"速度: {speed:.1f}手/秒  "
                  f"剩余: {remaining:.0f}秒", end='\r')

    print()  # 换行
    elapsed = time.time() - start
    bb100 = (total / hands) * 100

    print(f"\n📊 结果:")
    print(f"  总手数: {hands}")
    print(f"  总盈亏: {total:+.2f}BB")
    print(f"  BB/100: {bb100:+.2f}")
    print(f"  用时: {elapsed:.1f}秒 ({hands/elapsed:.1f}手/秒)")

    if bb100 > 10:
        print(f"  评价: ✅ 优秀 (盈利)")
    elif bb100 > 0:
        print(f"  评价: ✅ 盈利")
    elif bb100 > -10:
        print(f"  评价: ⚠️  小亏")
    else:
        print(f"  评价: ❌ 亏损")

    return bb100


def main():
    print("="*60)
    print("🚀 快速性能验证 (iterations=30, 极速模式)")
    print("="*60)
    print("\n注意: 这是快速验证，不追求精确数值")
    print("仅用于验证AI是否能基本盈利\n")

    results = {}

    # vs Random
    results['Random'] = quick_test(RandomBot(), "Random", 50)

    # vs SimpleBot
    results['SimpleBot'] = quick_test(SimpleBot(), "SimpleBot", 50)

    # 总结
    print(f"\n{'='*60}")
    print("📈 快速验证总结")
    print(f"{'='*60}")
    print(f"\nvs Random:    {results['Random']:+6.2f} BB/100")
    print(f"vs SimpleBot: {results['SimpleBot']:+6.2f} BB/100")

    wins = sum(1 for v in results.values() if v > 0)
    print(f"\n盈利对手数: {wins}/{len(results)}")

    if wins == len(results):
        print("\n✅ 快速验证通过：AI对所有对手都盈利")
    elif wins > 0:
        print("\n⚠️  快速验证部分通过：AI对部分对手盈利")
    else:
        print("\n❌ 快速验证失败：AI对所有对手都亏损")

    print("\n说明:")
    print("- iterations=30（极低），结果有较大方差")
    print("- 仅50手样本，统计意义有限")
    print("- 仅用于快速验证AI基本可行性")
    print("- 精确性能需要运行完整测试（1000手，iterations=100+）")


if __name__ == '__main__':
    main()
