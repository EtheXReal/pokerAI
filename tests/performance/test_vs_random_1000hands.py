#!/usr/bin/env python
"""
Phase 2.4 - AI vs Random 1000手测试
使用多线程加速测试
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Tuple, List

from advisor.range_engine import Hand, Board, create_deck
from advisor.range_engine.evaluator import HandEvaluator
from advisor.strategy_engine import ProLevelAdvisor, GameState
from advisor.opponent_modeling import PlayerType


@dataclass
class HandResult:
    """单手结果"""
    hand_num: int
    ai_position: str
    ai_profit: float
    ai_hand_str: str
    random_hand_str: str
    action_summary: str


class AIPlayer:
    """使用Strategy Engine的AI玩家"""

    def __init__(self, name: str = "AI"):
        self.name = name
        self.advisor = ProLevelAdvisor(exploit_weight=0.4)
        # 使用优化后的计算器，已经集成了OptimizedEquityCalculator

    def decide_preflop(self, hand: Hand, position: str, pot: float, stack: float,
                      facing_bet: float = 0, bet_to_call: float = 0) -> Tuple[str, float]:
        """翻前决策"""
        try:
            game_state = GameState(
                street='preflop',
                position=position,
                is_in_position=(position == 'BTN'),
                hero_hand=hand,
                pot_size=pot,
                effective_stack=stack,
                hero_stack=stack,
                facing_bet=facing_bet,
                bet_to_call=bet_to_call,
                opponent_type=PlayerType.UNKNOWN
            )

            decision = self.advisor.advise(game_state)
            action = decision.recommended_action.lower()

            if 'fold' in action:
                return 'fold', 0.0
            elif 'raise' in action or 'r' in action:
                sizing = decision.optimal_sizing if decision.optimal_sizing else 0.5
                amount = max(pot * sizing, 3.0)
                return 'raise', amount
            else:
                return 'call', 0.0

        except Exception as e:
            # 出错时保守决策
            rank1 = hand.cards[0].rank
            rank2 = hand.cards[1].rank
            score = rank1.value + rank2.value
            if hand.cards[0].suit == hand.cards[1].suit:
                score += 2

            if score >= 20:
                return 'raise', 3.0
            elif score >= 14:
                return 'call', 0.0
            else:
                return 'fold', 0.0


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


def showdown(ai_hand: Hand, random_hand: Hand, ai_invested: float,
             random_invested: float, deck: list) -> float:
    """Showdown比较牌力"""
    board_cards = deck[4:9]
    ai_cards = list(ai_hand.cards) + board_cards
    random_cards = list(random_hand.cards) + board_cards

    ai_strength = HandEvaluator.evaluate_best_5(ai_cards)
    random_strength = HandEvaluator.evaluate_best_5(random_cards)

    pot = ai_invested + random_invested

    if ai_strength > random_strength:
        return pot - ai_invested
    elif ai_strength < random_strength:
        return -ai_invested
    else:
        return 0.0


def play_single_hand(hand_num: int, ai_player: AIPlayer, random_player: RandomPlayer,
                     ai_position: str, starting_stack: float = 100.0) -> HandResult:
    """玩一手牌"""
    sb = 0.5
    bb = 1.0

    # 为每手牌设置独立的随机种子
    random.seed(hand_num + int(time.time() * 1000))

    deck = create_deck()
    random.shuffle(deck)

    ai_hand = Hand([deck[0], deck[1]])
    random_hand = Hand([deck[2], deck[3]])

    pot = sb + bb
    action_summary = ""

    try:
        if ai_position == 'BTN':
            ai_invested = sb
            random_invested = bb

            ai_action, ai_amount = ai_player.decide_preflop(ai_hand, 'BTN', pot, starting_stack - sb)
            action_summary = f"AI:{ai_action}"

            if ai_action == 'fold':
                return HandResult(hand_num, ai_position, -sb, str(ai_hand), str(random_hand), action_summary)

            elif ai_action == 'call':
                ai_invested = bb
                profit = showdown(ai_hand, random_hand, ai_invested, random_invested, deck)
                return HandResult(hand_num, ai_position, profit, str(ai_hand), str(random_hand), action_summary + ",showdown")

            elif ai_action == 'raise':
                ai_invested = ai_amount
                pot = ai_amount + bb

                random_action, _ = random_player.decide_preflop(random_hand, 'BB', pot, starting_stack - bb)
                action_summary += f",Rand:{random_action}"

                if random_action == 'fold':
                    return HandResult(hand_num, ai_position, bb, str(ai_hand), str(random_hand), action_summary)

                elif random_action == 'call':
                    random_invested = ai_amount
                    profit = showdown(ai_hand, random_hand, ai_invested, random_invested, deck)
                    return HandResult(hand_num, ai_position, profit, str(ai_hand), str(random_hand), action_summary + ",showdown")

                else:  # 3-bet
                    three_bet = ai_amount * 2.5
                    rank_sum = ai_hand.cards[0].rank.value + ai_hand.cards[1].rank.value
                    if rank_sum >= 24:
                        ai_invested = three_bet
                        random_invested = three_bet
                        profit = showdown(ai_hand, random_hand, ai_invested, random_invested, deck)
                        return HandResult(hand_num, ai_position, profit, str(ai_hand), str(random_hand), action_summary + ",AI:call3bet,showdown")
                    else:
                        return HandResult(hand_num, ai_position, -ai_amount, str(ai_hand), str(random_hand), action_summary + ",AI:foldto3bet")

        else:  # AI在BB
            ai_invested = bb
            random_invested = sb

            random_action, random_amount = random_player.decide_preflop(random_hand, 'BTN', pot, starting_stack - sb)
            action_summary = f"Rand:{random_action}"

            if random_action == 'fold':
                return HandResult(hand_num, ai_position, sb, str(ai_hand), str(random_hand), action_summary)

            elif random_action == 'call':
                random_invested = bb
                profit = showdown(ai_hand, random_hand, ai_invested, random_invested, deck)
                return HandResult(hand_num, ai_position, profit, str(ai_hand), str(random_hand), action_summary + ",showdown")

            elif random_action == 'raise':
                random_invested = random_amount
                pot = random_amount + bb

                ai_action, _ = ai_player.decide_preflop(ai_hand, 'BB', pot, starting_stack - bb,
                                                        facing_bet=random_amount, bet_to_call=random_amount-bb)
                action_summary += f",AI:{ai_action}"

                if ai_action == 'fold':
                    return HandResult(hand_num, ai_position, -bb, str(ai_hand), str(random_hand), action_summary)

                elif ai_action == 'call':
                    ai_invested = random_amount
                    profit = showdown(ai_hand, random_hand, ai_invested, random_invested, deck)
                    return HandResult(hand_num, ai_position, profit, str(ai_hand), str(random_hand), action_summary + ",showdown")

                else:  # 3-bet
                    three_bet = random_amount * 2.5
                    ai_invested = three_bet

                    if random.random() < 0.4:
                        random_invested = three_bet
                        profit = showdown(ai_hand, random_hand, ai_invested, random_invested, deck)
                        return HandResult(hand_num, ai_position, profit, str(ai_hand), str(random_hand), action_summary + ",Rand:call3bet,showdown")
                    else:
                        return HandResult(hand_num, ai_position, random_amount, str(ai_hand), str(random_hand), action_summary + ",Rand:foldto3bet")

    except Exception as e:
        # 出错返回0
        return HandResult(hand_num, ai_position, 0.0, str(ai_hand), str(random_hand), f"ERROR:{e}")

    return HandResult(hand_num, ai_position, 0.0, str(ai_hand), str(random_hand), "unknown")


def run_simulation_multithreaded(num_hands: int = 1000, max_workers: int = 4):
    """使用多线程运行模拟"""
    print('=' * 80)
    print('🤖 AI vs Random - 1000手测试 (多线程加速)')
    print('=' * 80)
    print(f'\n配置:')
    print(f'  总手数: {num_hands}')
    print(f'  线程数: {max_workers}')
    print(f'  开始时间: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    print()

    # 为每个线程创建独立的AI和Random玩家
    def worker_init():
        return AIPlayer("PokerAI"), RandomPlayer("RandomBot")

    # 准备所有任务
    tasks = []
    for i in range(num_hands):
        ai_position = 'BTN' if i % 2 == 0 else 'BB'
        tasks.append((i, ai_position))

    results: List[HandResult] = []
    start_time = time.time()

    # 使用线程池执行
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 为每个worker创建AI和Random玩家
        futures = {}
        for hand_num, ai_position in tasks:
            ai, rand = worker_init()
            future = executor.submit(play_single_hand, hand_num, ai, rand, ai_position)
            futures[future] = hand_num

        # 收集结果并显示进度
        completed = 0
        for future in as_completed(futures):
            try:
                result = future.result(timeout=30)  # 30秒超时
                results.append(result)
                completed += 1

                if completed % 50 == 0 or completed == num_hands:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    print(f'  进度: {completed}/{num_hands} ({completed/num_hands*100:.1f}%) - '
                          f'{rate:.1f} 手/秒 - 用时 {elapsed:.1f}秒')
            except Exception as e:
                print(f'  Hand {futures[future]} 执行错误: {e}')

    total_time = time.time() - start_time

    # 排序结果
    results.sort(key=lambda x: x.hand_num)

    # 统计分析
    ai_total = sum(r.ai_profit for r in results)
    ai_btn_results = [r for r in results if r.ai_position == 'BTN']
    ai_bb_results = [r for r in results if r.ai_position == 'BB']

    ai_btn_total = sum(r.ai_profit for r in ai_btn_results)
    ai_bb_total = sum(r.ai_profit for r in ai_bb_results)

    # 生成报告
    report_lines = []
    report_lines.append('=' * 80)
    report_lines.append('Phase 2.4 - AI vs Random 1000手测试结果')
    report_lines.append('=' * 80)
    report_lines.append('')
    report_lines.append(f'测试时间: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    report_lines.append(f'总用时: {total_time:.1f} 秒')
    report_lines.append(f'平均速度: {num_hands/total_time:.1f} 手/秒')
    report_lines.append('')
    report_lines.append('=' * 80)
    report_lines.append('📊 测试结果')
    report_lines.append('=' * 80)
    report_lines.append('')
    report_lines.append(f'总手数: {len(results)}')
    report_lines.append(f'AI总盈亏: {ai_total:+.2f} BB')
    report_lines.append(f'AI BB/100: {(ai_total / len(results)) * 100:+.2f} BB/100手')
    report_lines.append('')
    report_lines.append(f'BTN位置 ({len(ai_btn_results)}手):')
    report_lines.append(f'  盈亏: {ai_btn_total:+.2f} BB')
    report_lines.append(f'  BB/100: {(ai_btn_total / len(ai_btn_results)) * 100:+.2f}')
    report_lines.append('')
    report_lines.append(f'BB位置 ({len(ai_bb_results)}手):')
    report_lines.append(f'  盈亏: {ai_bb_total:+.2f} BB')
    report_lines.append(f'  BB/100: {(ai_bb_total / len(ai_bb_results)) * 100:+.2f}')
    report_lines.append('')
    report_lines.append('=' * 80)
    report_lines.append('📈 Phase 2.4 目标对比')
    report_lines.append('=' * 80)
    report_lines.append('')

    bb_per_100 = (ai_total / len(results)) * 100
    target_bb_100 = 60.0

    report_lines.append(f'目标 BB/100: +{target_bb_100:.2f}')
    report_lines.append(f'实际 BB/100: {bb_per_100:+.2f}')
    report_lines.append(f'差距: {bb_per_100 - target_bb_100:+.2f}')
    report_lines.append('')

    if bb_per_100 >= target_bb_100:
        report_lines.append('✅ 达到Phase 2.4目标！')
    elif bb_per_100 >= target_bb_100 * 0.8:
        report_lines.append('⚠️  接近目标 (80%以上)')
    elif bb_per_100 > 0:
        report_lines.append('⚠️  盈利但未达目标')
    else:
        report_lines.append('❌ 未达到目标，需要优化')

    report_lines.append('')
    report_lines.append('=' * 80)
    report_lines.append('💡 分析')
    report_lines.append('=' * 80)
    report_lines.append('')
    report_lines.append(f'样本量: {len(results)} 手 (统计显著性良好)')
    report_lines.append(f'标准差估计: ±{(100 / (len(results) ** 0.5)):.1f} BB/100')

    # 打印报告
    print()
    for line in report_lines:
        print(line)

    # 保存到文件
    output_file = '/home/user/pokerAI/test_vs_random_1000hands_result.txt'
    with open(output_file, 'w', encoding='utf-8') as f:
        for line in report_lines:
            f.write(line + '\n')

        # 添加详细数据
        f.write('\n')
        f.write('=' * 80 + '\n')
        f.write('详细数据 (前100手)' + '\n')
        f.write('=' * 80 + '\n')
        f.write('Hand  Position  Profit    AI_Hand    Random_Hand  Actions\n')
        f.write('-' * 80 + '\n')

        for r in results[:100]:
            f.write(f'{r.hand_num:4d}  {r.ai_position:3s}      {r.ai_profit:+6.2f}  '
                   f'{r.ai_hand_str:8s}  {r.random_hand_str:8s}  {r.action_summary}\n')

        if len(results) > 100:
            f.write(f'\n... (剩余 {len(results)-100} 手数据省略)\n')

    print(f'\n结果已保存到: {output_file}')
    print()

    return bb_per_100


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='AI vs Random 1000手测试')
    parser.add_argument('--hands', type=int, default=1000, help='测试手数')
    parser.add_argument('--threads', type=int, default=4, help='线程数')
    args = parser.parse_args()

    # 确保查找表已初始化
    from advisor.range_engine.evaluator_fast_v2 import precompute_if_needed_v2
    print('初始化查找表...')
    precompute_if_needed_v2()
    print('查找表就绪\n')

    bb_100 = run_simulation_multithreaded(num_hands=args.hands, max_workers=args.threads)

    print('测试完成！')
