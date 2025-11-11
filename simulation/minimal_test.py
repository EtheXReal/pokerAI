#!/usr/bin/env python
"""
最小化测试 - 完全跳过ProLevelAdvisor，直接用hand strength
10秒内完成100手
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import random
import time
from advisor.range_engine import Hand, create_deck
from advisor.range_engine.evaluator import HandEvaluator
from advisor.strategy_engine.hand_strength import calculate_preflop_hand_strength


class MinimalAI:
    """最简AI - 仅用hand strength"""
    def decide(self, hand: Hand, position: str):
        strength = calculate_preflop_hand_strength(hand)

        if position == 'BTN':
            if strength >= 0.70: return 'raise', 3.0
            elif strength >= 0.50: return 'call', 0.0
            else: return 'fold', 0.0
        else:  # BB
            if strength >= 0.75: return 'raise', 3.0
            elif strength >= 0.55: return 'call', 0.0
            else: return 'fold', 0.0


class RandomBot:
    def decide(self, hand, position):
        r = random.random()
        if r < 0.4: return 'fold', 0.0
        elif r < 0.55: return 'raise', 3.0
        else: return 'call', 0.0


class SimpleBot:
    def decide(self, hand, position):
        r1, r2 = hand.cards[0].rank.value, hand.cards[1].rank.value
        if r1 == r2 and r1 >= 10: return 'raise', 3.0
        if max(r1, r2) == 14 and min(r1, r2) >= 12: return 'raise', 3.0
        if max(r1, r2) >= 11: return 'call', 0.0
        return 'fold', 0.0


def showdown(ai_hand, opp_hand, deck):
    board = deck[4:9]
    ai_str = HandEvaluator.evaluate_best_5(list(ai_hand.cards) + board)
    opp_str = HandEvaluator.evaluate_best_5(list(opp_hand.cards) + board)
    if ai_str > opp_str: return 1
    elif ai_str < opp_str: return -1
    else: return 0


def play_hand(ai, opponent, ai_pos):
    sb, bb = 0.5, 1.0
    deck = create_deck()
    random.shuffle(deck)
    ai_hand = Hand([deck[0], deck[1]])
    opp_hand = Hand([deck[2], deck[3]])

    if ai_pos == 'BTN':
        ai_inv, opp_inv = sb, bb
        ai_act, ai_amt = ai.decide(ai_hand, 'BTN')

        if ai_act == 'fold': return -sb
        elif ai_act == 'call':
            ai_inv = bb
            winner = showdown(ai_hand, opp_hand, deck)
            return winner * bb if winner != 0 else 0.0
        else:  # raise
            ai_inv = ai_amt
            opp_act, _ = opponent.decide(opp_hand, 'BB')
            if opp_act == 'fold': return bb
            else:
                opp_inv = ai_amt
                winner = showdown(ai_hand, opp_hand, deck)
                return winner * ai_amt if winner != 0 else 0.0
    else:  # BB
        ai_inv, opp_inv = bb, sb
        opp_act, opp_amt = opponent.decide(opp_hand, 'BTN')

        if opp_act == 'fold': return sb
        elif opp_act == 'call':
            opp_inv = bb
            winner = showdown(ai_hand, opp_hand, deck)
            return winner * bb if winner != 0 else 0.0
        else:  # raise
            opp_inv = opp_amt
            ai_act, _ = ai.decide(ai_hand, 'BB')
            if ai_act == 'fold': return -bb
            else:
                ai_inv = opp_amt
                winner = showdown(ai_hand, opp_hand, deck)
                return winner * opp_amt if winner != 0 else 0.0


def quick_test(opponent, name, hands=100):
    print(f"\n{'='*60}")
    print(f"🎯 vs {name}")
    print(f"{'='*60}")

    ai = MinimalAI()
    total = 0.0
    start = time.time()

    for i in range(hands):
        ai_pos = 'BTN' if i % 2 == 0 else 'BB'
        result = play_hand(ai, opponent, ai_pos)
        total += result

        if (i + 1) % 20 == 0:
            bb100 = (total / (i + 1)) * 100
            elapsed = time.time() - start
            speed = (i + 1) / elapsed
            print(f"  [{i+1:3d}/{hands}] 盈亏: {total:+6.2f}BB  BB/100: {bb100:+7.2f}  速度: {speed:.0f}手/秒")

    elapsed = time.time() - start
    bb100 = (total / hands) * 100

    print(f"\n📊 vs {name} 结果:")
    print(f"  手数: {hands}  盈亏: {total:+.2f}BB  BB/100: {bb100:+.2f}")
    print(f"  用时: {elapsed:.1f}秒 ({hands/elapsed:.0f}手/秒)")
    print(f"  状态: {'✅ 盈利' if bb100 > 0 else '❌ 亏损'}")

    return bb100


def main():
    print("="*60)
    print("⚡ 最小化性能验证（无equity计算）")
    print("="*60)
    print("\n说明: 仅用hand strength，极速测试\n")

    start_total = time.time()
    results = {}

    results['Random'] = quick_test(RandomBot(), "Random", 100)
    results['SimpleBot'] = quick_test(SimpleBot(), "SimpleBot", 100)

    elapsed_total = time.time() - start_total

    print(f"\n{'='*60}")
    print("📈 测试总结")
    print(f"{'='*60}")
    print(f"\nvs Random:    {results['Random']:+7.2f} BB/100")
    print(f"vs SimpleBot: {results['SimpleBot']:+7.2f} BB/100")

    wins = sum(1 for v in results.values() if v > 0)
    print(f"\n盈利对手数: {wins}/{len(results)}")
    print(f"总用时: {elapsed_total:.1f}秒")

    if wins == len(results):
        print("\n✅ 验证通过：AI对所有对手都盈利")
    elif wins > 0:
        print("\n⚠️  部分通过：AI对部分对手盈利")
    else:
        print("\n❌ 验证失败：AI未能盈利")


if __name__ == '__main__':
    main()
