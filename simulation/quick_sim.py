#!/usr/bin/env python
"""
快速对局模拟 - 使用简单策略验证框架

不使用完整Strategy Engine，用简化规则快速测试
"""
import sys
sys.path.append('/home/user/pokerAI')

import random
from advisor.range_engine import Hand, Board, create_deck
from advisor.range_engine.evaluator import HandEvaluator, Rank


def hand_strength_score(hand: Hand) -> int:
    """简单的手牌强度评分"""
    rank1 = hand.cards[0].rank
    rank2 = hand.cards[1].rank

    score = rank1.value + rank2.value

    # 对子加分
    if rank1 == rank2:
        score += 10

    # 同花加分
    if hand.cards[0].suit == hand.cards[1].suit:
        score += 2

    # 连张加分
    if abs(rank1.value - rank2.value) == 1:
        score += 1

    return score


class SimpleStrategyPlayer:
    """使用简单策略的玩家"""

    def __init__(self, name: str):
        self.name = name

    def decide(self, hand: Hand, position: str) -> tuple[str, float]:
        """
        简单策略决策

        Returns:
            (action, raise_amount)
        """
        score = hand_strength_score(hand)

        # 决策阈值
        if position == 'BTN':
            # BTN更激进
            if score >= 24:  # 强牌 (JJ+, AK, AQ等)
                return 'raise', 3.5
            elif score >= 18:  # 中等牌 (77+, KQ, AJ等)
                if random.random() < 0.7:
                    return 'call', 0.0
                else:
                    return 'raise', 3.0
            elif score >= 14:  # 弱牌 (22+, suited connectors等)
                if random.random() < 0.4:
                    return 'call', 0.0
                else:
                    return 'fold', 0.0
            else:
                return 'fold', 0.0

        else:  # BB
            # BB稍保守
            if score >= 24:  # 强牌
                return 'raise', 3.5
            elif score >= 20:  # 中等强牌
                if random.random() < 0.8:
                    return 'call', 0.0
                else:
                    return 'raise', 3.0
            elif score >= 16:  # 中等牌
                return 'call', 0.0
            else:
                if random.random() < 0.7:
                    return 'fold', 0.0
                else:
                    return 'call', 0.0


class RandomPlayer:
    """随机策略玩家"""

    def __init__(self, name: str, fold_rate: float = 0.5, raise_rate: float = 0.15):
        self.name = name
        self.fold_rate = fold_rate
        self.raise_rate = raise_rate

    def decide(self, hand: Hand, position: str) -> tuple[str, float]:
        """随机决策"""
        r = random.random()

        if r < self.fold_rate:
            return 'fold', 0.0
        elif r < self.fold_rate + self.raise_rate:
            return 'raise', random.uniform(2.5, 4.0)
        else:
            return 'call', 0.0


def play_hand(p1, p2, p1_position: str) -> float:
    """
    玩一手牌

    Returns:
        p1的盈亏
    """
    sb = 0.5
    bb = 1.0

    # 发牌
    deck = create_deck()
    random.shuffle(deck)

    p1_hand = Hand([deck[0], deck[1]])
    p2_hand = Hand([deck[2], deck[3]])

    p1_invested = sb if p1_position == 'BTN' else bb
    p2_invested = bb if p1_position == 'BTN' else sb

    # BTN先行动
    if p1_position == 'BTN':
        p1_action, p1_amount = p1.decide(p1_hand, 'BTN')

        if p1_action == 'fold':
            return -sb
        elif p1_action == 'call':
            p1_invested = bb
            return showdown(p1_hand, p2_hand, p1_invested, p2_invested, deck)
        else:  # raise
            p1_invested = p1_amount
            pot = p1_amount + bb

            # P2响应
            p2_action, p2_amount = p2.decide(p2_hand, 'BB')

            if p2_action == 'fold':
                return bb
            elif p2_action == 'call':
                p2_invested = p1_amount
                return showdown(p1_hand, p2_hand, p1_invested, p2_invested, deck)
            else:  # raise (3-bet)
                three_bet = p1_amount * 2.5
                p2_invested = three_bet

                # P1对3-bet的响应（简化：基于手牌强度）
                score1 = hand_strength_score(p1_hand)
                if score1 >= 26:  # 超强牌call
                    p1_invested = three_bet
                    return showdown(p1_hand, p2_hand, p1_invested, p2_invested, deck)
                else:  # 否则fold
                    return -p1_amount

    else:  # P1在BB
        p2_action, p2_amount = p2.decide(p2_hand, 'BTN')

        if p2_action == 'fold':
            return sb
        elif p2_action == 'call':
            p2_invested = bb
            return showdown(p1_hand, p2_hand, p1_invested, p2_invested, deck)
        else:  # raise
            p2_invested = p2_amount
            pot = p2_amount + bb

            # P1响应
            p1_action, p1_amount = p1.decide(p1_hand, 'BB')

            if p1_action == 'fold':
                return -bb
            elif p1_action == 'call':
                p1_invested = p2_amount
                return showdown(p1_hand, p2_hand, p1_invested, p2_invested, deck)
            else:  # raise (3-bet)
                three_bet = p2_amount * 2.5
                p1_invested = three_bet

                # P2对3-bet的响应
                score2 = hand_strength_score(p2_hand)
                if score2 >= 26 or random.random() < 0.3:
                    p2_invested = three_bet
                    return showdown(p1_hand, p2_hand, p1_invested, p2_invested, deck)
                else:
                    return p2_amount


def showdown(p1_hand: Hand, p2_hand: Hand, p1_invested: float, p2_invested: float, deck: list) -> float:
    """Showdown"""
    board_cards = deck[4:9]

    p1_cards = list(p1_hand.cards) + board_cards
    p2_cards = list(p2_hand.cards) + board_cards

    p1_strength = HandEvaluator.evaluate_best_5(p1_cards)
    p2_strength = HandEvaluator.evaluate_best_5(p2_cards)

    pot = p1_invested + p2_invested

    if p1_strength > p2_strength:
        return pot - p1_invested
    elif p1_strength < p2_strength:
        return -p1_invested
    else:
        return 0.0


def run_simulation(num_hands: int = 100):
    """运行快速模拟"""
    print('=' * 70)
    print('🎲 快速对局模拟')
    print('=' * 70)

    p1 = SimpleStrategyPlayer("SimpleAI")
    p2 = RandomPlayer("RandomBot", fold_rate=0.5, raise_rate=0.15)

    p1_total = 0.0
    p1_btn_total = 0.0
    p1_bb_total = 0.0

    btn_hands = 0
    bb_hands = 0

    print(f'\n模拟 {num_hands} 手牌...\n')

    for i in range(num_hands):
        p1_position = 'BTN' if i % 2 == 0 else 'BB'

        try:
            result = play_hand(p1, p2, p1_position)
            p1_total += result

            if p1_position == 'BTN':
                p1_btn_total += result
                btn_hands += 1
            else:
                p1_bb_total += result
                bb_hands += 1

            if (i + 1) % 20 == 0:
                print(f"Hand {i+1:3d}/{num_hands}: SimpleAI累计 {p1_total:+7.2f}BB  "
                      f"({p1_total/(i+1)*100:+6.1f}bb/100)")

        except Exception as e:
            print(f"Hand {i+1} 错误: {e}")
            continue

    # 结果
    print('\n' + '=' * 70)
    print('📊 模拟结果')
    print('=' * 70)

    print(f'\n总手数: {num_hands}')
    print(f'SimpleAI 总盈亏: {p1_total:+.2f}BB')
    print(f'SimpleAI bb/100: {(p1_total / num_hands) * 100:+.2f}BB/100手')

    if btn_hands > 0:
        print(f'\nBTN位置 ({btn_hands}手):')
        print(f'  盈亏: {p1_btn_total:+.2f}BB')
        print(f'  bb/100: {(p1_btn_total / btn_hands) * 100:+.2f}')

    if bb_hands > 0:
        print(f'\nBB位置 ({bb_hands}手):')
        print(f'  盈亏: {p1_bb_total:+.2f}BB')
        print(f'  bb/100: {(p1_bb_total / bb_hands) * 100:+.2f}')

    # 评估
    print('\n' + '=' * 70)
    print('💡 评估')
    print('=' * 70)

    bb_per_100 = (p1_total / num_hands) * 100

    print(f'\nSimpleAI (简单策略) vs RandomBot:')
    if bb_per_100 > 15:
        print(f'✅ 表现优秀 ({bb_per_100:+.1f}bb/100)')
    elif bb_per_100 > 5:
        print(f'✅ 表现良好 ({bb_per_100:+.1f}bb/100)')
    elif bb_per_100 > 0:
        print(f'✅ 盈利 ({bb_per_100:+.1f}bb/100)')
    else:
        print(f'❌ 亏损 ({bb_per_100:+.1f}bb/100) - 策略需要改进')

    print(f'\n说明: 这只是简化测试，使用基于手牌强度的简单规则。')
    print(f'完整Strategy Engine会考虑位置、对手类型、GTO+Exploit等因素。')


if __name__ == '__main__':
    run_simulation(num_hands=100)
