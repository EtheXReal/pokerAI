#!/usr/bin/env python
"""
advisor_v2 vs Random 详细测试
包含完整的行动记录、牌面、下注金额等详细信息
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import random
import time
from dataclasses import dataclass
from typing import Tuple, List, Optional

from advisor.range_engine import Hand, create_deck, Card
from advisor.range_engine.evaluator import HandEvaluator
from advisor.strategy_engine.gto_baseline import Position

# advisor_v2 imports
from advisor_v2.integration.decision_integrator import DecisionIntegrator
from advisor_v2.analysis.range_engine import RangeEngine
from advisor_v2.analysis.equity_engine import EquityEngine
from advisor_v2.analysis.board_analyzer import BoardAnalyzer
from advisor_v2.strategy.gto_strategy import GTOStrategy


@dataclass
class MockGameState:
    """简化的GameState用于advisor_v2"""
    street: str
    position: str
    is_in_position: bool
    hero_hand: Hand
    pot_size: float
    effective_stack: float
    hero_stack: float
    board: Optional[List[Card]] = None
    action_history: Optional[List[str]] = None
    facing_bet: Optional[float] = None
    bet_to_call: Optional[float] = None
    min_raise: Optional[float] = None
    num_opponents: int = 1
    opponent_stats: Optional[any] = None
    opponent_type: Optional[any] = None
    tournament: bool = False
    bubble: bool = False


@dataclass
class ActionDetail:
    """行动详情"""
    player: str
    action: str  # fold/call/raise
    amount: float
    pot_after: float
    reasoning: str = ""  # advisor_v2可以添加决策原因


@dataclass
class HandDetail:
    """单手详细记录"""
    hand_num: int
    ai_position: str
    ai_hand: str
    random_hand: str
    actions: List[ActionDetail]
    board: List[str]  # flop, turn, river
    ai_profit: float
    winner: str
    showdown: bool
    ai_final_hand_strength: str = ""
    random_final_hand_strength: str = ""


class AdvisorV2Player:
    """使用advisor_v2的AI玩家（详细版）"""

    def __init__(self, name: str = "AdvisorV2"):
        self.name = name
        # 初始化advisor_v2模块
        self.range_engine = RangeEngine()
        self.equity_engine = EquityEngine(cache_size=1000)
        self.board_analyzer = BoardAnalyzer()
        self.strategy = GTOStrategy()

        self.integrator = DecisionIntegrator(
            range_engine=self.range_engine,
            equity_engine=self.equity_engine,
            board_analyzer=self.board_analyzer,
            strategy=self.strategy
        )

    def decide_preflop(self, hand: Hand, position: str, pot: float, stack: float,
                      facing_bet: float = 0, bet_to_call: float = 0) -> Tuple[str, float, str]:
        """
        翻前决策

        Returns:
            (action, amount, reasoning)
        """
        try:
            # 构建GameState
            action_history = []
            if facing_bet > 0:
                action_history = ['raise']  # opponent raised

            game_state = MockGameState(
                street='preflop',
                position=position,
                is_in_position=(position == 'BTN'),
                hero_hand=hand,
                pot_size=pot,
                effective_stack=stack,
                hero_stack=stack,
                facing_bet=facing_bet,
                bet_to_call=bet_to_call,
                action_history=action_history
            )

            # 决策
            trace = self.integrator.decide(game_state)

            action = trace.selected_action.action
            amount = trace.selected_action.amount

            # 构建reasoning
            reasoning = f"range_pct={trace.gto_decision.key_factors.get('range_percentile', 0):.2f}"
            if 'pot_odds' in trace.gto_decision.key_factors:
                reasoning += f", pot_odds={trace.gto_decision.key_factors['pot_odds']:.2f}"

            # 转换为实际下注金额
            if action == 'raise' or action == 'bet':
                # amount是pot fraction，转换为实际金额
                actual_amount = max(pot * amount, 3.0)  # 至少3BB
                return action, actual_amount, reasoning
            elif action == 'call':
                return 'call', 0.0, reasoning
            else:  # fold or check
                return 'fold', 0.0, reasoning

        except Exception as e:
            # 出错时fallback到简单策略
            rank1 = hand.cards[0].rank.value
            rank2 = hand.cards[1].rank.value
            score = rank1 + rank2
            if hand.cards[0].suit == hand.cards[1].suit:
                score += 2

            if score >= 20:
                return 'raise', 3.0, f"fallback:score={score}"
            elif score >= 14:
                return 'call', 0.0, f"fallback:score={score}"
            else:
                return 'fold', 0.0, f"fallback:score={score}"


class RandomPlayer:
    """随机决策玩家"""

    def __init__(self, name: str = "Random", fold_rate: float = 0.4, raise_rate: float = 0.15):
        self.name = name
        self.fold_rate = fold_rate
        self.raise_rate = raise_rate

    def decide_preflop(self, hand: Hand, position: str, pot: float, stack: float) -> Tuple[str, float]:
        """随机决策"""
        r = random.random()
        if r < self.fold_rate:
            return 'fold', 0.0
        elif r < self.fold_rate + self.raise_rate:
            return 'raise', random.uniform(2.5, 4.0)
        else:
            return 'call', 0.0


def format_card_list(cards: List[Card]) -> str:
    """格式化牌列表"""
    return ' '.join(str(c) for c in cards)


def play_single_hand_detailed(hand_num: int, ai_player: AdvisorV2Player, random_player: RandomPlayer,
                              ai_position: str, starting_stack: float = 100.0) -> HandDetail:
    """玩一手牌并记录详细信息"""
    sb = 0.5
    bb = 1.0

    # 为每手牌设置独立的随机种子
    random.seed(hand_num + int(time.time() * 1000))

    deck = create_deck()
    random.shuffle(deck)

    ai_hand = Hand([deck[0], deck[1]])
    random_hand = Hand([deck[2], deck[3]])
    board_cards = deck[4:9]

    pot = sb + bb
    actions: List[ActionDetail] = []
    board_shown = []
    showdown = False
    winner = ""
    ai_final_strength = ""
    random_final_strength = ""

    try:
        if ai_position == 'BTN':
            # AI在BTN，先行动
            ai_invested = sb
            random_invested = bb

            # AI决策
            ai_action, ai_amount, ai_reasoning = ai_player.decide_preflop(ai_hand, 'BTN', pot, starting_stack - sb)

            if ai_action == 'fold':
                actions.append(ActionDetail("AI", "fold", 0, pot, ai_reasoning))
                profit = -sb
                winner = "Random"
                return HandDetail(hand_num, ai_position, str(ai_hand), str(random_hand),
                                actions, board_shown, profit, winner, showdown)

            elif ai_action == 'call':
                ai_invested = bb
                pot = sb + bb
                actions.append(ActionDetail("AI", "call", bb - sb, pot, ai_reasoning))

                # 去showdown
                showdown = True
                board_shown = [format_card_list(board_cards[:3]), str(board_cards[3]), str(board_cards[4])]

                ai_cards = list(ai_hand.cards) + board_cards
                random_cards = list(random_hand.cards) + board_cards

                ai_strength = HandEvaluator.evaluate_best_5(ai_cards)
                random_strength = HandEvaluator.evaluate_best_5(random_cards)

                ai_final_strength = f"{ai_strength.rank.name}"
                random_final_strength = f"{random_strength.rank.name}"

                if ai_strength > random_strength:
                    profit = pot - ai_invested
                    winner = "AI"
                elif ai_strength < random_strength:
                    profit = -ai_invested
                    winner = "Random"
                else:
                    profit = 0.0
                    winner = "Tie"

                return HandDetail(hand_num, ai_position, str(ai_hand), str(random_hand),
                                actions, board_shown, profit, winner, showdown,
                                ai_final_strength, random_final_strength)

            elif ai_action == 'raise':
                ai_invested = ai_amount
                pot = ai_amount + bb
                actions.append(ActionDetail("AI", f"raise to {ai_amount:.1f}BB", ai_amount, pot, ai_reasoning))

                # Random响应
                random_action, random_amount = random_player.decide_preflop(random_hand, 'BB', pot, starting_stack - bb)

                if random_action == 'fold':
                    actions.append(ActionDetail("Random", "fold", 0, pot))
                    profit = bb
                    winner = "AI"
                    return HandDetail(hand_num, ai_position, str(ai_hand), str(random_hand),
                                    actions, board_shown, profit, winner, showdown)

                elif random_action == 'call':
                    random_invested = ai_amount
                    pot = ai_amount * 2
                    actions.append(ActionDetail("Random", f"call {ai_amount - bb:.1f}BB", ai_amount, pot))

                    # 去showdown
                    showdown = True
                    board_shown = [format_card_list(board_cards[:3]), str(board_cards[3]), str(board_cards[4])]

                    ai_cards = list(ai_hand.cards) + board_cards
                    random_cards = list(random_hand.cards) + board_cards

                    ai_strength = HandEvaluator.evaluate_best_5(ai_cards)
                    random_strength = HandEvaluator.evaluate_best_5(random_cards)

                    ai_final_strength = f"{ai_strength.rank.name}"
                    random_final_strength = f"{random_strength.rank.name}"

                    if ai_strength > random_strength:
                        profit = pot - ai_invested
                        winner = "AI"
                    elif ai_strength < random_strength:
                        profit = -ai_invested
                        winner = "Random"
                    else:
                        profit = 0.0
                        winner = "Tie"

                    return HandDetail(hand_num, ai_position, str(ai_hand), str(random_hand),
                                    actions, board_shown, profit, winner, showdown,
                                    ai_final_strength, random_final_strength)

                else:  # Random 3-bet
                    three_bet = ai_amount * 2.5
                    pot = ai_amount + three_bet
                    actions.append(ActionDetail("Random", f"3-bet to {three_bet:.1f}BB", three_bet, pot))

                    # AI对3-bet的响应（简化：基于手牌强度）
                    rank_sum = ai_hand.cards[0].rank.value + ai_hand.cards[1].rank.value
                    if rank_sum >= 24:  # QQ+, AK
                        # Call 3-bet
                        ai_invested = three_bet
                        random_invested = three_bet
                        pot = three_bet * 2
                        actions.append(ActionDetail("AI", f"call {three_bet - ai_amount:.1f}BB", three_bet, pot, "premium_hand"))

                        # 去showdown
                        showdown = True
                        board_shown = [format_card_list(board_cards[:3]), str(board_cards[3]), str(board_cards[4])]

                        ai_cards = list(ai_hand.cards) + board_cards
                        random_cards = list(random_hand.cards) + board_cards

                        ai_strength = HandEvaluator.evaluate_best_5(ai_cards)
                        random_strength = HandEvaluator.evaluate_best_5(random_cards)

                        ai_final_strength = f"{ai_strength.rank.name}"
                        random_final_strength = f"{random_strength.rank.name}"

                        if ai_strength > random_strength:
                            profit = pot - ai_invested
                            winner = "AI"
                        elif ai_strength < random_strength:
                            profit = -ai_invested
                            winner = "Random"
                        else:
                            profit = 0.0
                            winner = "Tie"

                        return HandDetail(hand_num, ai_position, str(ai_hand), str(random_hand),
                                        actions, board_shown, profit, winner, showdown,
                                        ai_final_strength, random_final_strength)
                    else:
                        # Fold to 3-bet
                        actions.append(ActionDetail("AI", "fold to 3-bet", 0, pot, "non_premium"))
                        profit = -ai_amount
                        winner = "Random"
                        return HandDetail(hand_num, ai_position, str(ai_hand), str(random_hand),
                                        actions, board_shown, profit, winner, showdown)

        else:  # AI在BB
            ai_invested = bb
            random_invested = sb

            # Random在BTN先行动
            random_action, random_amount = random_player.decide_preflop(random_hand, 'BTN', pot, starting_stack - sb)

            if random_action == 'fold':
                actions.append(ActionDetail("Random", "fold", 0, pot))
                profit = sb
                winner = "AI"
                return HandDetail(hand_num, ai_position, str(ai_hand), str(random_hand),
                                actions, board_shown, profit, winner, showdown)

            elif random_action == 'call':
                random_invested = bb
                pot = bb * 2
                actions.append(ActionDetail("Random", f"call {bb - sb:.1f}BB", bb, pot))

                # AI可以check或raise，简化：总是check
                actions.append(ActionDetail("AI", "check", 0, pot))

                # 去showdown
                showdown = True
                board_shown = [format_card_list(board_cards[:3]), str(board_cards[3]), str(board_cards[4])]

                ai_cards = list(ai_hand.cards) + board_cards
                random_cards = list(random_hand.cards) + board_cards

                ai_strength = HandEvaluator.evaluate_best_5(ai_cards)
                random_strength = HandEvaluator.evaluate_best_5(random_cards)

                ai_final_strength = f"{ai_strength.rank.name}"
                random_final_strength = f"{random_strength.rank.name}"

                if ai_strength > random_strength:
                    profit = pot - ai_invested
                    winner = "AI"
                elif ai_strength < random_strength:
                    profit = -ai_invested
                    winner = "Random"
                else:
                    profit = 0.0
                    winner = "Tie"

                return HandDetail(hand_num, ai_position, str(ai_hand), str(random_hand),
                                actions, board_shown, profit, winner, showdown,
                                ai_final_strength, random_final_strength)

            elif random_action == 'raise':
                random_invested = random_amount
                pot = random_amount + bb
                actions.append(ActionDetail("Random", f"raise to {random_amount:.1f}BB", random_amount, pot))

                # AI响应
                ai_action, _, ai_reasoning = ai_player.decide_preflop(ai_hand, 'BB', pot, starting_stack - bb,
                                                        facing_bet=random_amount, bet_to_call=random_amount-bb)

                if ai_action == 'fold':
                    actions.append(ActionDetail("AI", "fold", 0, pot, ai_reasoning))
                    profit = -bb
                    winner = "Random"
                    return HandDetail(hand_num, ai_position, str(ai_hand), str(random_hand),
                                    actions, board_shown, profit, winner, showdown)

                elif ai_action == 'call':
                    ai_invested = random_amount
                    pot = random_amount * 2
                    actions.append(ActionDetail("AI", f"call {random_amount - bb:.1f}BB", random_amount, pot, ai_reasoning))

                    # 去showdown
                    showdown = True
                    board_shown = [format_card_list(board_cards[:3]), str(board_cards[3]), str(board_cards[4])]

                    ai_cards = list(ai_hand.cards) + board_cards
                    random_cards = list(random_hand.cards) + board_cards

                    ai_strength = HandEvaluator.evaluate_best_5(ai_cards)
                    random_strength = HandEvaluator.evaluate_best_5(random_cards)

                    ai_final_strength = f"{ai_strength.rank.name}"
                    random_final_strength = f"{random_strength.rank.name}"

                    if ai_strength > random_strength:
                        profit = pot - ai_invested
                        winner = "AI"
                    elif ai_strength < random_strength:
                        profit = -ai_invested
                        winner = "Random"
                    else:
                        profit = 0.0
                        winner = "Tie"

                    return HandDetail(hand_num, ai_position, str(ai_hand), str(random_hand),
                                    actions, board_shown, profit, winner, showdown,
                                    ai_final_strength, random_final_strength)

                else:  # AI 3-bet
                    three_bet = random_amount * 2.5
                    ai_invested = three_bet
                    pot = three_bet + random_amount
                    actions.append(ActionDetail("AI", f"3-bet to {three_bet:.1f}BB", three_bet, pot, ai_reasoning))

                    # Random响应（简化：概率call/fold）
                    if random.random() < 0.4:  # 40% call
                        random_invested = three_bet
                        pot = three_bet * 2
                        actions.append(ActionDetail("Random", f"call {three_bet - random_amount:.1f}BB", three_bet, pot))

                        # 去showdown
                        showdown = True
                        board_shown = [format_card_list(board_cards[:3]), str(board_cards[3]), str(board_cards[4])]

                        ai_cards = list(ai_hand.cards) + board_cards
                        random_cards = list(random_hand.cards) + board_cards

                        ai_strength = HandEvaluator.evaluate_best_5(ai_cards)
                        random_strength = HandEvaluator.evaluate_best_5(random_cards)

                        ai_final_strength = f"{ai_strength.rank.name}"
                        random_final_strength = f"{random_strength.rank.name}"

                        if ai_strength > random_strength:
                            profit = pot - ai_invested
                            winner = "AI"
                        elif ai_strength < random_strength:
                            profit = -ai_invested
                            winner = "Random"
                        else:
                            profit = 0.0
                            winner = "Tie"

                        return HandDetail(hand_num, ai_position, str(ai_hand), str(random_hand),
                                        actions, board_shown, profit, winner, showdown,
                                        ai_final_strength, random_final_strength)
                    else:
                        # Random fold
                        actions.append(ActionDetail("Random", "fold to 3-bet", 0, pot))
                        profit = random_amount
                        winner = "AI"
                        return HandDetail(hand_num, ai_position, str(ai_hand), str(random_hand),
                                        actions, board_shown, profit, winner, showdown)

    except Exception as e:
        # 出错返回默认结果
        actions.append(ActionDetail("ERROR", f"Exception: {e}", 0, pot))
        return HandDetail(hand_num, ai_position, str(ai_hand), str(random_hand),
                        actions, board_shown, 0.0, "Error", False)

    # 不应该到这里
    return HandDetail(hand_num, ai_position, str(ai_hand), str(random_hand),
                    actions, board_shown, 0.0, "Unknown", False)


def run_detailed_test(num_hands: int = 32, output_file: str = 'v2test1.txt'):
    """运行详细测试"""
    print('=' * 80)
    print('🤖 advisor_v2 vs Random - 详细测试（每手牌完整记录）')
    print('=' * 80)
    print(f'\n配置:')
    print(f'  总手数: {num_hands}')
    print(f'  架构: advisor_v2 range-based决策')
    print(f'  开始时间: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    print()

    # 确保查找表已初始化
    from advisor.range_engine.evaluator_fast_v2 import precompute_if_needed_v2
    print('初始化查找表...')
    precompute_if_needed_v2()
    print('查找表就绪\n')

    ai = AdvisorV2Player("AdvisorV2")
    random_player = RandomPlayer("RandomBot")

    results: List[HandDetail] = []
    start_time = time.time()

    for i in range(num_hands):
        ai_position = 'BTN' if i % 2 == 0 else 'BB'

        print(f'  玩手牌 {i+1}/{num_hands}...', end='', flush=True)
        hand_start = time.time()

        result = play_single_hand_detailed(i, ai, random_player, ai_position)
        results.append(result)

        hand_time = time.time() - hand_start
        print(f' 完成 ({hand_time:.2f}秒)')

    total_time = time.time() - start_time

    # 统计分析
    ai_total = sum(r.ai_profit for r in results)
    ai_btn_results = [r for r in results if r.ai_position == 'BTN']
    ai_bb_results = [r for r in results if r.ai_position == 'BB']

    ai_btn_total = sum(r.ai_profit for r in ai_btn_results)
    ai_bb_total = sum(r.ai_profit for r in ai_bb_results)

    # 生成详细报告
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('=' * 80 + '\n')
        f.write('advisor_v2 vs Random 详细测试结果\n')
        f.write('=' * 80 + '\n\n')
        f.write(f'测试时间: {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write(f'总用时: {total_time:.1f} 秒\n')
        f.write(f'平均速度: {num_hands/total_time:.2f} 手/秒\n')
        f.write(f'架构: advisor_v2 (RangeEngine → EquityEngine → BoardAnalyzer → GTOStrategy)\n')
        f.write('\n')
        f.write('=' * 80 + '\n')
        f.write('📊 测试结果汇总\n')
        f.write('=' * 80 + '\n\n')
        f.write(f'总手数: {len(results)}\n')
        f.write(f'AI总盈亏: {ai_total:+.2f} BB\n')
        f.write(f'AI BB/100: {(ai_total / len(results)) * 100:+.2f} BB/100手\n\n')
        f.write(f'BTN位置 ({len(ai_btn_results)}手):\n')
        f.write(f'  盈亏: {ai_btn_total:+.2f} BB\n')
        f.write(f'  BB/100: {(ai_btn_total / len(ai_btn_results)) * 100:+.2f}\n\n')
        f.write(f'BB位置 ({len(ai_bb_results)}手):\n')
        f.write(f'  盈亏: {ai_bb_total:+.2f} BB\n')
        f.write(f'  BB/100: {(ai_bb_total / len(ai_bb_results)) * 100:+.2f}\n\n')

        f.write('=' * 80 + '\n')
        f.write('📋 每手详细记录\n')
        f.write('=' * 80 + '\n\n')

        for r in results:
            f.write(f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n')
            f.write(f'Hand #{r.hand_num + 1} - AI Position: {r.ai_position}\n')
            f.write(f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n')

            f.write(f'起手牌:\n')
            f.write(f'  AI Hand:     {r.ai_hand}\n')
            f.write(f'  Random Hand: {r.random_hand}\n\n')

            f.write(f'行动序列:\n')
            for action in r.actions:
                if action.reasoning:
                    f.write(f'  {action.player:8s} -> {action.action:25s} | Pot: {action.pot_after:.1f}BB | {action.reasoning}\n')
                else:
                    f.write(f'  {action.player:8s} -> {action.action:25s} | Pot: {action.pot_after:.1f}BB\n')
            f.write('\n')

            if r.showdown and r.board:
                f.write(f'公共牌:\n')
                if len(r.board) >= 1:
                    f.write(f'  Flop:  {r.board[0]}\n')
                if len(r.board) >= 2:
                    f.write(f'  Turn:  {r.board[1]}\n')
                if len(r.board) >= 3:
                    f.write(f'  River: {r.board[2]}\n')
                f.write('\n')

                f.write(f'最终牌力:\n')
                f.write(f'  AI:     {r.ai_final_hand_strength}\n')
                f.write(f'  Random: {r.random_final_hand_strength}\n\n')

            f.write(f'结果:\n')
            f.write(f'  Winner: {r.winner}\n')
            f.write(f'  AI Profit: {r.ai_profit:+.2f} BB\n\n')

    print()
    print('=' * 80)
    print('📊 测试结果汇总')
    print('=' * 80)
    print()
    print(f'总手数: {len(results)}')
    print(f'AI总盈亏: {ai_total:+.2f} BB')
    print(f'AI BB/100: {(ai_total / len(results)) * 100:+.2f} BB/100手')
    print()
    print(f'BTN位置 ({len(ai_btn_results)}手):')
    print(f'  盈亏: {ai_btn_total:+.2f} BB')
    print(f'  BB/100: {(ai_btn_total / len(ai_btn_results)) * 100:+.2f}')
    print()
    print(f'BB位置 ({len(ai_bb_results)}手):')
    print(f'  盈亏: {ai_bb_total:+.2f} BB')
    print(f'  BB/100: {(ai_bb_total / len(ai_bb_results)) * 100:+.2f}')
    print()
    print(f'详细结果已保存到: {output_file}')
    print()

    return ai_total / len(results) * 100


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='advisor_v2 vs Random 详细测试')
    parser.add_argument('--hands', type=int, default=32, help='测试手数（默认32）')
    parser.add_argument('--output', type=str, default='v2test1.txt', help='输出文件（默认v2test1.txt）')
    args = parser.parse_args()

    bb_100 = run_detailed_test(num_hands=args.hands, output_file=args.output)

    print('=' * 80)
    print('✅ 测试完成！')
    print('=' * 80)
    print(f'\nadvisor_v2 (range-based): {bb_100:+.2f} BB/100')
    print()
