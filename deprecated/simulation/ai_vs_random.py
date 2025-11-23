#!/usr/bin/env python
"""
AI vs Random 对局测试

测试Strategy Engine对抗随机玩家的表现
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import random
from dataclasses import dataclass

from poker_core import Hand, Board, create_deck
from poker_core.evaluator import HandEvaluator
from advisor.strategy_engine import ProLevelAdvisor, GameState
from advisor.opponent_modeling import PlayerType


class AIPlayer:
    """使用Strategy Engine的AI玩家（简化版）"""

    def __init__(self, name: str = "AI"):
        self.name = name
        # 使用极低的迭代次数加速（仅用于测试）
        self.advisor = ProLevelAdvisor(exploit_weight=0.4)
        self.advisor.equity_calculator.iterations = 100  # 极低迭代数快速测试

    def decide_preflop(self, hand: Hand, position: str, pot: float, stack: float) -> tuple[str, float]:
        """
        翻前决策（简化版）

        Returns:
            (action, amount) - 'fold', 'call', 'raise' 和金额
        """
        try:
            # 构造GameState
            game_state = GameState(
                street='preflop',
                position=position,
                is_in_position=(position == 'BTN'),
                hero_hand=hand,
                pot_size=pot,
                effective_stack=stack,
                hero_stack=stack,
                opponent_type=PlayerType.UNKNOWN  # 随机对手
            )

            decision = self.advisor.advise(game_state)

            # 解析推荐动作
            action = decision.recommended_action.lower()

            if 'fold' in action:
                return 'fold', 0.0
            elif 'raise' in action or 'r' in action:
                # 提取sizing（如果有）
                sizing = decision.optimal_sizing if decision.optimal_sizing else 0.5
                amount = pot * sizing
                return 'raise', max(3.0, amount)  # 至少3BB
            else:
                return 'call', 0.0

        except Exception as e:
            # 出错时保守决策
            print(f"AI决策错误: {e}")
            # 简单策略：强牌raise，中等牌call，弱牌fold
            rank1 = hand.cards[0].rank
            rank2 = hand.cards[1].rank

            # 简化评分
            score = rank1.value + rank2.value
            if hand.cards[0].suit == hand.cards[1].suit:
                score += 2  # 同花加分

            if score >= 20:  # 强牌 (TT+, AK等)
                return 'raise', 3.0
            elif score >= 14:  # 中等牌
                return 'call', 0.0
            else:
                return 'fold', 0.0


class RandomPlayer:
    """随机决策玩家"""

    def __init__(self, name: str = "Random", fold_rate: float = 0.4, raise_rate: float = 0.15):
        self.name = name
        self.fold_rate = fold_rate
        self.raise_rate = raise_rate

    def decide_preflop(self, hand: Hand, position: str, pot: float, stack: float) -> tuple[str, float]:
        """随机决策"""
        r = random.random()

        if r < self.fold_rate:
            return 'fold', 0.0
        elif r < self.fold_rate + self.raise_rate:
            return 'raise', random.uniform(2.5, 4.0)
        else:
            return 'call', 0.0


def play_preflop_hand(ai_player: AIPlayer,
                      random_player: RandomPlayer,
                      ai_position: str,
                      starting_stack: float = 100.0) -> float:
    """
    玩一手翻前牌（简化版）

    Args:
        ai_player: AI玩家
        random_player: Random玩家
        ai_position: AI的位置 ('BTN' 或 'BB')
        starting_stack: 起始筹码

    Returns:
        AI的盈亏（BB为单位）
    """
    sb = 0.5
    bb = 1.0

    # 发牌
    deck = create_deck()
    random.shuffle(deck)

    ai_hand = Hand([deck[0], deck[1]])
    random_hand = Hand([deck[2], deck[3]])

    pot = sb + bb

    # BTN先行动
    if ai_position == 'BTN':
        # AI在BTN
        ai_invested = sb
        random_invested = bb

        ai_action, ai_amount = ai_player.decide_preflop(ai_hand, 'BTN', pot, starting_stack - sb)

        if ai_action == 'fold':
            return -sb  # AI弃牌输小盲

        elif ai_action == 'call':
            # AI跟注到BB
            ai_invested = bb
            # Showdown
            return showdown(ai_hand, random_hand, ai_invested, random_invested, deck)

        elif ai_action == 'raise':
            # AI加注
            ai_invested = ai_amount
            pot = ai_amount + bb

            # Random响应
            random_action, _ = random_player.decide_preflop(random_hand, 'BB', pot, starting_stack - bb)

            if random_action == 'fold':
                return bb  # Random弃牌，AI赢得BB

            elif random_action == 'call':
                # Random跟注
                random_invested = ai_amount
                return showdown(ai_hand, random_hand, ai_invested, random_invested, deck)

            else:  # raise (3-bet)
                # Random 3-bet，AI简化处理：强牌call，其他fold
                three_bet = ai_amount * 2.5
                pot = ai_amount + three_bet

                # AI对3-bet的响应（简化：基于手牌强度）
                rank_sum = ai_hand.cards[0].rank.value + ai_hand.cards[1].rank.value
                if rank_sum >= 24:  # QQ+, AK
                    # Call 3-bet
                    ai_invested = three_bet
                    random_invested = three_bet
                    return showdown(ai_hand, random_hand, ai_invested, random_invested, deck)
                else:
                    # Fold to 3-bet
                    return -ai_amount

    else:  # AI在BB
        ai_invested = bb
        random_invested = sb

        # Random在BTN先行动
        random_action, random_amount = random_player.decide_preflop(random_hand, 'BTN', pot, starting_stack - sb)

        if random_action == 'fold':
            return sb  # Random弃牌，AI赢得小盲

        elif random_action == 'call':
            # Random跟注，AI可以check或raise
            # 简化：AI总是check到showdown
            random_invested = bb
            return showdown(ai_hand, random_hand, ai_invested, random_invested, deck)

        elif random_action == 'raise':
            # Random加注
            random_invested = random_amount
            pot = random_amount + bb

            # AI响应
            ai_action, _ = ai_player.decide_preflop(ai_hand, 'BB', pot, starting_stack - bb)

            if ai_action == 'fold':
                return -bb  # AI弃牌输大盲

            elif ai_action == 'call':
                # AI跟注
                ai_invested = random_amount
                return showdown(ai_hand, random_hand, ai_invested, random_invested, deck)

            else:  # raise (3-bet)
                # AI 3-bet
                three_bet = random_amount * 2.5
                ai_invested = three_bet
                pot = three_bet + random_amount

                # Random响应（简化：概率call/fold）
                if random.random() < 0.4:  # 40% call
                    random_invested = three_bet
                    return showdown(ai_hand, random_hand, ai_invested, random_invested, deck)
                else:
                    # Random fold
                    return random_amount

    return 0.0


def showdown(ai_hand: Hand, random_hand: Hand, ai_invested: float, random_invested: float, deck: list) -> float:
    """
    Showdown比较牌力

    Returns:
        AI的盈亏
    """
    # 发出公共牌
    board_cards = deck[4:9]

    ai_cards = list(ai_hand.cards) + board_cards
    random_cards = list(random_hand.cards) + board_cards

    ai_strength = HandEvaluator.evaluate_best_5(ai_cards)
    random_strength = HandEvaluator.evaluate_best_5(random_cards)

    pot = ai_invested + random_invested

    if ai_strength > random_strength:
        return pot - ai_invested  # AI赢
    elif ai_strength < random_strength:
        return -ai_invested  # AI输
    else:
        return 0.0  # 平局


def run_simulation(num_hands: int = 50, verbose: bool = True):
    """运行模拟"""
    print('=' * 70)
    print('🤖 AI vs Random 对局模拟')
    print('=' * 70)

    ai = AIPlayer("PokerAI")
    random_player = RandomPlayer("RandomBot")

    ai_total = 0.0
    ai_btn_total = 0.0
    ai_bb_total = 0.0

    ai_btn_hands = 0
    ai_bb_hands = 0

    for i in range(num_hands):
        # 轮流做BTN
        ai_position = 'BTN' if i % 2 == 0 else 'BB'

        try:
            result = play_preflop_hand(ai, random_player, ai_position)
            ai_total += result

            if ai_position == 'BTN':
                ai_btn_total += result
                ai_btn_hands += 1
            else:
                ai_bb_total += result
                ai_bb_hands += 1

            if verbose and (i + 1) % 10 == 0:
                print(f"Hand {i+1:3d}: AI累计 {ai_total:+7.2f}BB  "
                      f"(本手 {result:+5.2f}BB, {ai_position})")

        except Exception as e:
            print(f"Hand {i+1} 错误: {e}")
            continue

    # 统计
    print('\n' + '=' * 70)
    print('📊 模拟结果')
    print('=' * 70)

    print(f'\n总手数: {num_hands}')
    print(f'AI总盈亏: {ai_total:+.2f}BB')
    print(f'AI bb/100: {(ai_total / num_hands) * 100:+.2f}BB/100手')

    if ai_btn_hands > 0:
        print(f'\nBTN位置 ({ai_btn_hands}手):')
        print(f'  盈亏: {ai_btn_total:+.2f}BB')
        print(f'  bb/100: {(ai_btn_total / ai_btn_hands) * 100:+.2f}')

    if ai_bb_hands > 0:
        print(f'\nBB位置 ({ai_bb_hands}手):')
        print(f'  盈亏: {ai_bb_total:+.2f}BB')
        print(f'  bb/100: {(ai_bb_total / ai_bb_hands) * 100:+.2f}')

    # 评估
    print('\n' + '=' * 70)
    print('💡 评估')
    print('=' * 70)

    bb_per_100 = (ai_total / num_hands) * 100

    if bb_per_100 > 10:
        print('✅ AI表现优秀 (> 10bb/100)！')
    elif bb_per_100 > 5:
        print('✅ AI表现良好 (5-10bb/100)')
    elif bb_per_100 > 0:
        print('⚠️  AI略有盈利 (0-5bb/100)，可以改进')
    elif bb_per_100 > -5:
        print('⚠️  AI略有亏损 (0 to -5bb/100)，需要优化')
    else:
        print('❌ AI表现较差 (< -5bb/100)，需要检查逻辑')

    print('\n注意: 样本量较小，结果有方差。需要至少1000手以上才能得出可靠结论。')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='AI vs Random对局模拟')
    parser.add_argument('--hands', type=int, default=50, help='模拟手数')
    parser.add_argument('--verbose', action='store_true', default=True, help='详细输出')
    args = parser.parse_args()

    run_simulation(num_hands=args.hands, verbose=args.verbose)
