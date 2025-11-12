#!/usr/bin/env python
"""
advisor_v2完整翻后测试 - 真正的德州扑克
包含完整的preflop/flop/turn/river决策流程，支持多轮加注

与test_advisor_v2_vs_random_32hands.py的关键区别：
- 旧测试：只有翻前决策，然后直接showdown（假扑克）
- 新测试：完整的4个街道决策（真扑克）

这才是advisor_v2需要的测试，因为：
- EquityEngine需要board来计算equity
- BoardAnalyzer需要board来分析texture
- Range advantage分析需要翻后的equity分布
- 支持多轮加注（bet → raise → 3-bet → 4-bet...）
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import random
import time
from dataclasses import dataclass
from typing import List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from advisor.range_engine import Hand, Board, create_deck, Card
from advisor.range_engine.evaluator import HandEvaluator
from advisor.strategy_engine import GameState
from advisor.opponent_modeling import PlayerType
from advisor_v2.integration.decision_integrator import DecisionIntegrator
from advisor_v2.analysis.range_engine import RangeEngine
from advisor_v2.analysis.equity_engine import EquityEngine
from advisor_v2.analysis.board_analyzer import BoardAnalyzer
from advisor_v2.strategy.gto_strategy import GTOStrategy


@dataclass
class StreetAction:
    """单个街道的行动记录"""
    street: str  # preflop/flop/turn/river
    player: str
    action: str  # fold/check/call/bet/raise
    amount: float
    pot_after: float


@dataclass
class FullHandRecord:
    """完整手牌记录"""
    hand_num: int
    ai_position: str
    ai_hand_str: str
    random_hand_str: str

    # 公共牌
    flop: List[str]
    turn: str
    river: str

    # 所有行动
    actions: List[StreetAction]

    # 结果
    winner: str
    ai_profit: float
    final_pot: float

    # 如果到showdown
    showdown: bool
    ai_final_strength: str = ""
    random_final_strength: str = ""


class AdvisorV2Player:
    """使用DecisionIntegrator的AI玩家"""

    def __init__(self, name: str = "AdvisorV2"):
        self.name = name
        # 初始化advisor_v2组件
        self.range_engine = RangeEngine()
        self.equity_engine = EquityEngine()
        self.board_analyzer = BoardAnalyzer()
        self.gto_strategy = GTOStrategy()
        self.integrator = DecisionIntegrator(
            range_engine=self.range_engine,
            equity_engine=self.equity_engine,
            board_analyzer=self.board_analyzer,
            strategy=self.gto_strategy
        )

    def decide(self, street: str, position: str, hand: Hand, board: Board,
               pot_size: float, effective_stack: float, hero_stack: float,
               facing_bet: float, bet_to_call: float) -> Tuple[str, float]:
        """
        做决策（任何街道）

        Returns:
            (action, amount) where action in ['fold', 'check', 'call', 'bet', 'raise']
        """
        try:
            # 构建GameState（advisor的）
            game_state = GameState(
                street=street,
                position=position,
                is_in_position=(position == 'BTN'),
                hero_hand=hand,
                pot_size=pot_size,
                effective_stack=effective_stack,
                hero_stack=hero_stack,
                board=board,
                facing_bet=facing_bet,
                bet_to_call=bet_to_call,
                opponent_type=PlayerType.UNKNOWN
            )

            # 使用DecisionIntegrator决策
            trace = self.integrator.decide(game_state)

            # 使用DecisionIntegrator的select_action进行GTO随机采样
            # 这是正确的GTO实现：按概率分布随机选择，而不是"选最高概率"
            selected_action = self.integrator.select_action(trace.gto_decision)

            action_type = selected_action.action
            amount = selected_action.amount

            # 将amount转换为实际BB（如果是bet/raise）
            if action_type in ['bet', 'raise']:
                # amount是pot_fraction，需要转换为实际金额
                if amount > 0:
                    actual_amount = pot_size * amount
                else:
                    actual_amount = pot_size * 0.66  # 默认值

                # 限制在stack范围内
                actual_amount = max(0.5, min(actual_amount, hero_stack))
                return action_type, actual_amount
            else:
                return action_type, 0.0

        except Exception as e:
            print(f"  [AI决策错误: {e}，使用保守策略]")
            import traceback
            traceback.print_exc()

            # 出错时保守决策
            if facing_bet > 0:
                # 面对下注：根据pot odds
                pot_odds = bet_to_call / (pot_size + bet_to_call)
                if pot_odds < 0.33:  # 好的赔率
                    return 'call', 0.0
                else:
                    return 'fold', 0.0
            else:
                # 未面对下注：check
                return 'check', 0.0


class SimpleRandomPlayer:
    """简单的随机玩家"""

    def __init__(self, name: str = "Random"):
        self.name = name

    def decide(self, pot: float, facing_bet: float, stack: float) -> Tuple[str, float]:
        """
        随机决策 - 所有street一致
        - 不facing bet: 1/3 bet, 2/3 check
        - facing bet: 1/5 raise, 2/5 call, 2/5 fold （更合理的分布）

        Returns:
            (action, amount)
        """
        r = random.random()

        if facing_bet > 0:
            # 面对下注: 1/5 raise, 2/5 call, 2/5 fold
            if r < 0.2:
                # Raise: 随机尺度 2.0-3.5x
                raise_size = facing_bet * random.uniform(2.0, 3.5)
                return 'raise', min(raise_size, stack)
            elif r < 0.6:
                # Call: 跟注
                return 'call', 0.0
            else:
                # Fold
                return 'fold', 0.0
        else:
            # 未面对下注: 1/3 bet, 2/3 check
            if r < 1.0 / 3.0:
                # Bet: 随机尺度 0.33-1.0 pot
                bet_size = pot * random.uniform(0.33, 1.0)
                return 'bet', min(bet_size, stack)
            else:
                return 'check', 0.0


def run_betting_round(
    street: str,
    ai_player: AdvisorV2Player,
    random_player: SimpleRandomPlayer,
    ai_position: str,
    ai_hand: Hand,
    random_hand: Hand,
    board: Board,
    pot: float,
    ai_stack: float,
    random_stack: float,
    ai_invested: float,
    random_invested: float,
    actions: List[StreetAction],
    verbose: bool = True
) -> Tuple[Optional[str], float, float, float, float, float]:
    """
    运行一个完整的betting round（支持多轮加注）

    Returns:
        (winner, pot, ai_stack, random_stack, ai_invested, random_invested)
        winner: 'AI', 'Random', or None (继续游戏)
    """
    # 确定谁先行动（OOP先行动）
    ai_acts_first = (ai_position == 'BB')

    # 当前街道的投入（用于计算facing bet）
    street_ai_invested = 0
    street_random_invested = 0

    # 行动循环
    last_aggressor = None  # 最后一个下注/加注的人
    num_actions = 0
    max_actions = 20  # 防止无限循环

    while num_actions < max_actions:
        num_actions += 1

        # 确定当前行动的玩家
        if num_actions == 1:
            current_player = 'AI' if ai_acts_first else 'Random'
        else:
            # 轮流行动
            if actions[-1].player == 'AI':
                current_player = 'Random'
            else:
                current_player = 'AI'

        # 计算facing bet
        if current_player == 'AI':
            facing_bet = street_random_invested
            to_call = max(0, street_random_invested - street_ai_invested)
        else:
            facing_bet = street_ai_invested
            to_call = max(0, street_ai_invested - street_random_invested)

        # 获取决策
        if current_player == 'AI':
            action_type, amount = ai_player.decide(
                street=street,
                position=ai_position,
                hand=ai_hand,
                board=board,
                pot_size=pot,
                effective_stack=min(ai_stack, random_stack),
                hero_stack=ai_stack,
                facing_bet=facing_bet,
                bet_to_call=to_call
            )
        else:
            action_type, amount = random_player.decide(pot, facing_bet, random_stack)

        # 处理action
        if action_type == 'fold':
            actions.append(StreetAction(street, current_player, 'fold', 0, pot))
            if verbose:
                print(f"  {current_player} folds")
            winner = 'Random' if current_player == 'AI' else 'AI'
            return (winner, pot, ai_stack, random_stack, ai_invested, random_invested)

        elif action_type == 'check':
            actions.append(StreetAction(street, current_player, 'check', 0, pot))
            if verbose:
                print(f"  {current_player} checks")

            # 如果双方都check，结束这个street
            if len(actions) >= 2 and actions[-2].action == 'check' and actions[-2].street == street:
                return (None, pot, ai_stack, random_stack, ai_invested, random_invested)

            # 如果是第一个行动的人check，继续
            continue

        elif action_type == 'call':
            if current_player == 'AI':
                call_amount = to_call
                ai_invested += call_amount
                ai_stack -= call_amount
                street_ai_invested += call_amount
            else:
                call_amount = to_call
                random_invested += call_amount
                random_stack -= call_amount
                street_random_invested += call_amount

            pot += call_amount
            actions.append(StreetAction(street, current_player, 'call', call_amount, pot))
            if verbose:
                print(f"  {current_player} calls {call_amount:.1f}BB, pot={pot:.1f}BB")

            # Call结束这个betting round
            return (None, pot, ai_stack, random_stack, ai_invested, random_invested)

        elif action_type == 'bet':
            bet_amount = min(amount, ai_stack if current_player == 'AI' else random_stack)

            if current_player == 'AI':
                ai_invested += bet_amount
                ai_stack -= bet_amount
                street_ai_invested += bet_amount
            else:
                random_invested += bet_amount
                random_stack -= bet_amount
                street_random_invested += bet_amount

            pot += bet_amount
            actions.append(StreetAction(street, current_player, f'bet {bet_amount:.1f}BB', bet_amount, pot))
            if verbose:
                print(f"  {current_player} bets {bet_amount:.1f}BB, pot={pot:.1f}BB")

            last_aggressor = current_player
            continue

        elif action_type == 'raise':
            # amount是"想要raise的增量金额"（相对于pot或facing bet）
            # 需要投入 = call amount + raise amount

            # 先计算需要call多少
            call_amt = to_call

            # 计算raise的增量（限制在剩余stack范围内）
            current_stack = ai_stack if current_player == 'AI' else random_stack
            raise_amt = min(amount, current_stack - call_amt)
            if raise_amt < 0:
                raise_amt = 0

            # 总共需要投入
            total_amt = call_amt + raise_amt

            if current_player == 'AI':
                ai_invested += total_amt
                ai_stack -= total_amt
                street_ai_invested += total_amt
            else:
                random_invested += total_amt
                random_stack -= total_amt
                street_random_invested += total_amt

            pot += total_amt

            # raise到的总额是：原facing_bet + raise增量
            raise_to = facing_bet + raise_amt

            actions.append(StreetAction(street, current_player, f'raise to {raise_to:.1f}BB', total_amt, pot))
            if verbose:
                print(f"  {current_player} raises to {raise_to:.1f}BB, pot={pot:.1f}BB")

            last_aggressor = current_player
            continue

    # 如果达到max_actions，结束（防御性代码）
    if verbose:
        print(f"  [Warning: Reached max actions in betting round]")
    return (None, pot, ai_stack, random_stack, ai_invested, random_invested)


def play_full_hand(hand_num: int, ai_player: AdvisorV2Player, random_player: SimpleRandomPlayer,
                   ai_position: str, starting_stack: float = 100.0, verbose: bool = True) -> FullHandRecord:
    """
    玩一手完整的牌（包含翻前+flop+turn+river，支持多轮加注）

    Args:
        hand_num: 手牌编号
        ai_player: AI玩家
        random_player: Random玩家
        ai_position: AI位置 ('BTN' or 'BB')
        starting_stack: 起始筹码
        verbose: 是否打印详细信息

    Returns:
        FullHandRecord
    """
    sb = 0.5
    bb = 1.0

    # 设置随机种子
    random.seed(hand_num + int(time.time() * 1000))

    # 发牌
    deck = create_deck()
    random.shuffle(deck)

    ai_hand = Hand([deck[0], deck[1]])
    random_hand = Hand([deck[2], deck[3]])
    board_cards = deck[4:9]  # flop[0:3], turn[3], river[4]

    # 初始化
    ai_stack = starting_stack
    random_stack = starting_stack
    pot = sb + bb
    actions: List[StreetAction] = []

    # 盲注投入
    if ai_position == 'BTN':
        ai_invested = sb
        random_invested = bb
        ai_stack -= sb
        random_stack -= bb
    else:
        ai_invested = bb
        random_invested = sb
        ai_stack -= bb
        random_stack -= sb

    if verbose:
        print(f"\n  === 翻前 ===")
        print(f"  AI: {ai_hand} ({ai_position})")
        print(f"  Random: {random_hand}")
        print(f"  Pot: {pot:.1f}BB")

    # ===== 翻前 =====
    winner, pot, ai_stack, random_stack, ai_invested, random_invested = run_betting_round(
        street='preflop',
        ai_player=ai_player,
        random_player=random_player,
        ai_position=ai_position,
        ai_hand=ai_hand,
        random_hand=random_hand,
        board=Board([]),
        pot=pot,
        ai_stack=ai_stack,
        random_stack=random_stack,
        ai_invested=ai_invested,
        random_invested=random_invested,
        actions=actions,
        verbose=verbose
    )

    if winner:
        profit = pot - ai_invested if winner == 'AI' else -ai_invested
        return FullHandRecord(
            hand_num, ai_position, str(ai_hand), str(random_hand),
            [], '', '', actions, winner, profit, pot, False
        )

    # ===== Flop =====
    flop_cards = board_cards[0:3]
    flop_str = [str(c) for c in flop_cards]
    board = Board(flop_cards)

    if verbose:
        print(f"\n  === Flop: {' '.join(flop_str)} ===")
        print(f"  Pot: {pot:.1f}BB")

    winner, pot, ai_stack, random_stack, ai_invested, random_invested = run_betting_round(
        street='flop',
        ai_player=ai_player,
        random_player=random_player,
        ai_position=ai_position,
        ai_hand=ai_hand,
        random_hand=random_hand,
        board=board,
        pot=pot,
        ai_stack=ai_stack,
        random_stack=random_stack,
        ai_invested=ai_invested,
        random_invested=random_invested,
        actions=actions,
        verbose=verbose
    )

    if winner:
        profit = pot - ai_invested if winner == 'AI' else -ai_invested
        return FullHandRecord(
            hand_num, ai_position, str(ai_hand), str(random_hand),
            flop_str, '', '', actions, winner, profit, pot, False
        )

    # ===== Turn =====
    turn_card = board_cards[3]
    turn_str = str(turn_card)
    board = Board(flop_cards + [turn_card])

    if verbose:
        print(f"\n  === Turn: {turn_str} ===")
        print(f"  Board: {' '.join(flop_str)} {turn_str}")
        print(f"  Pot: {pot:.1f}BB")

    winner, pot, ai_stack, random_stack, ai_invested, random_invested = run_betting_round(
        street='turn',
        ai_player=ai_player,
        random_player=random_player,
        ai_position=ai_position,
        ai_hand=ai_hand,
        random_hand=random_hand,
        board=board,
        pot=pot,
        ai_stack=ai_stack,
        random_stack=random_stack,
        ai_invested=ai_invested,
        random_invested=random_invested,
        actions=actions,
        verbose=verbose
    )

    if winner:
        profit = pot - ai_invested if winner == 'AI' else -ai_invested
        return FullHandRecord(
            hand_num, ai_position, str(ai_hand), str(random_hand),
            flop_str, turn_str, '', actions, winner, profit, pot, False
        )

    # ===== River =====
    river_card = board_cards[4]
    river_str = str(river_card)
    board = Board(board_cards)

    if verbose:
        print(f"\n  === River: {river_str} ===")
        print(f"  Board: {' '.join(flop_str)} {turn_str} {river_str}")
        print(f"  Pot: {pot:.1f}BB")

    winner, pot, ai_stack, random_stack, ai_invested, random_invested = run_betting_round(
        street='river',
        ai_player=ai_player,
        random_player=random_player,
        ai_position=ai_position,
        ai_hand=ai_hand,
        random_hand=random_hand,
        board=board,
        pot=pot,
        ai_stack=ai_stack,
        random_stack=random_stack,
        ai_invested=ai_invested,
        random_invested=random_invested,
        actions=actions,
        verbose=verbose
    )

    if winner:
        profit = pot - ai_invested if winner == 'AI' else -ai_invested
        return FullHandRecord(
            hand_num, ai_position, str(ai_hand), str(random_hand),
            flop_str, turn_str, river_str, actions, winner, profit, pot, False
        )

    # ===== Showdown =====
    if verbose:
        print(f"\n  === Showdown ===")

    ai_cards = list(ai_hand.cards) + list(board.cards)
    random_cards = list(random_hand.cards) + list(board.cards)

    ai_strength = HandEvaluator.evaluate_best_5(ai_cards)
    random_strength = HandEvaluator.evaluate_best_5(random_cards)

    if verbose:
        print(f"  AI: {ai_strength.rank.name}")
        print(f"  Random: {random_strength.rank.name}")

    if ai_strength > random_strength:
        winner = 'AI'
        profit = pot - ai_invested
        if verbose:
            print(f"  AI wins {pot:.1f}BB!")
    elif ai_strength < random_strength:
        winner = 'Random'
        profit = -ai_invested
        if verbose:
            print(f"  Random wins {pot:.1f}BB")
    else:
        winner = 'Tie'
        profit = 0.0
        if verbose:
            print(f"  Tie (split pot)")

    return FullHandRecord(
        hand_num, ai_position, str(ai_hand), str(random_hand),
        flop_str, turn_str, river_str,
        actions, winner, profit, pot, True,
        ai_strength.rank.name, random_strength.rank.name
    )


def run_test(num_hands: int = 32, num_threads: int = 4, verbose: bool = False):
    """运行完整测试"""
    print('=' * 80)
    print('🤖 advisor_v2 vs Random - 完整翻后测试（真扑克 + 多轮加注）')
    print('=' * 80)
    print(f'\n配置:')
    print(f'  手数: {num_hands}')
    print(f'  线程数: {num_threads}')
    print(f'  包含: 翻前 + Flop + Turn + River 完整决策')
    print(f'  支持: 多轮加注（bet → raise → 3-bet → 4-bet...）')
    print(f'  架构: DecisionIntegrator (RangeEngine + EquityEngine + BoardAnalyzer + GTOStrategy)')
    print(f'  开始时间: {time.strftime("%Y-%m-%d %H:%M:%S")}')

    # 初始化
    print('\n初始化advisor_v2组件...')
    start_time = time.time()

    ai = AdvisorV2Player("AdvisorV2")
    random_player = SimpleRandomPlayer("RandomBot")

    results: List[FullHandRecord] = []

    # 多线程执行
    def process_hand(i):
        ai_position = 'BTN' if i % 2 == 0 else 'BB'
        if verbose:
            print(f'\n{"="*80}')
            print(f'Hand #{i+1} - AI Position: {ai_position}')
            print(f'{"="*80}')

        try:
            result = play_full_hand(i, ai, random_player, ai_position, verbose=verbose)
            if verbose:
                print(f"\n  >>> AI Profit: {result.ai_profit:+.2f}BB")
            return result
        except Exception as e:
            print(f'\n  [Hand #{i+1} 错误: {e}]')
            import traceback
            traceback.print_exc()
            return None

    print(f'\n开始执行 {num_hands} 手牌测试...')
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = {executor.submit(process_hand, i): i for i in range(num_hands)}

        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
                if not verbose:
                    # 非verbose模式下显示进度
                    if len(results) % 10 == 0:
                        print(f'  进度: {len(results)}/{num_hands} 手完成')

    total_time = time.time() - start_time

    # 排序结果（多线程导致顺序混乱）
    results.sort(key=lambda r: r.hand_num)

    # 统计
    ai_total = sum(r.ai_profit for r in results)
    ai_btn_results = [r for r in results if r.ai_position == 'BTN']
    ai_bb_results = [r for r in results if r.ai_position == 'BB']

    ai_btn_total = sum(r.ai_profit for r in ai_btn_results) if ai_btn_results else 0
    ai_bb_total = sum(r.ai_profit for r in ai_bb_results) if ai_bb_results else 0

    # 输出结果
    print('\n' + '=' * 80)
    print('📊 测试结果汇总')
    print('=' * 80)
    print(f'\n总手数: {len(results)}')
    print(f'总用时: {total_time:.1f}秒')
    print(f'平均每手: {total_time/len(results):.2f}秒')
    print(f'\nAI总盈亏: {ai_total:+.2f} BB')
    print(f'AI BB/100: {(ai_total / len(results)) * 100:+.2f} BB/100手')

    if ai_btn_results:
        print(f'\nBTN位置 ({len(ai_btn_results)}手):')
        print(f'  盈亏: {ai_btn_total:+.2f} BB')
        print(f'  BB/100: {(ai_btn_total / len(ai_btn_results)) * 100:+.2f}')

    if ai_bb_results:
        print(f'\nBB位置 ({len(ai_bb_results)}手):')
        print(f'  盈亏: {ai_bb_total:+.2f} BB')
        print(f'  BB/100: {(ai_bb_total / len(ai_bb_results)) * 100:+.2f}')

    # 对比旧测试（假扑克）
    print('\n' + '=' * 80)
    print('🔍 完整测试 vs 简化测试对比')
    print('=' * 80)
    print(f'\n本测试（完整多轮加注）:')
    print(f'  整体 BB/100: {(ai_total / len(results)) * 100:+.2f}')
    print(f'  BTN BB/100:  {(ai_btn_total / len(ai_btn_results)) * 100:+.2f}')
    print(f'  BB BB/100:   {(ai_bb_total / len(ai_bb_results)) * 100:+.2f}')
    print(f'\n简化测试（单轮行动）:')
    print(f'  整体 BB/100: +633.44  (修复EquityEngine后的单轮测试)')
    print(f'  BTN BB/100:  +1078.07')
    print(f'  BB BB/100:   +188.81')

    # 保存详细报告
    output_file = f'/home/user/pokerAI/test_advisor_v2_full_postflop_{num_hands}hands_result.txt'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('=' * 80 + '\n')
        f.write(f'advisor_v2 vs Random - 完整翻后测试结果（{num_hands}手）\n')
        f.write('=' * 80 + '\n\n')
        f.write(f'测试时间: {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write(f'总用时: {total_time:.1f}秒\n')
        f.write(f'平均每手: {total_time/len(results):.2f}秒\n\n')

        f.write('=' * 80 + '\n')
        f.write('📊 结果汇总\n')
        f.write('=' * 80 + '\n\n')
        f.write(f'总手数: {len(results)}\n')
        f.write(f'AI总盈亏: {ai_total:+.2f} BB\n')
        f.write(f'AI BB/100: {(ai_total / len(results)) * 100:+.2f} BB/100手\n\n')

        if ai_btn_results:
            f.write(f'BTN位置 ({len(ai_btn_results)}手): {ai_btn_total:+.2f} BB, ')
            f.write(f'BB/100: {(ai_btn_total / len(ai_btn_results)) * 100:+.2f}\n')
        if ai_bb_results:
            f.write(f'BB位置 ({len(ai_bb_results)}手): {ai_bb_total:+.2f} BB, ')
            f.write(f'BB/100: {(ai_bb_total / len(ai_bb_results)) * 100:+.2f}\n')

        f.write('\n' + '=' * 80 + '\n')
        f.write('📋 详细记录\n')
        f.write('=' * 80 + '\n\n')

        for r in results:
            f.write(f'Hand #{r.hand_num + 1} - AI Position: {r.ai_position}\n')
            f.write(f'AI: {r.ai_hand_str}, Random: {r.random_hand_str}\n')
            if r.flop:
                f.write(f'Board: {" ".join(r.flop)} {r.turn} {r.river}\n\n')
            else:
                f.write('Board: (preflop fold)\n\n')

            f.write('Actions:\n')
            for action in r.actions:
                f.write(f'  [{action.street}] {action.player}: {action.action} (pot={action.pot_after:.1f}BB)\n')

            f.write(f'\nResult: {r.winner} wins, AI profit: {r.ai_profit:+.2f}BB\n')
            if r.showdown:
                f.write(f'Showdown: AI={r.ai_final_strength}, Random={r.random_final_strength}\n')
            f.write('\n' + '-' * 80 + '\n\n')

    print(f'\n详细结果已保存到: {output_file}')
    print()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='advisor_v2完整翻后测试')
    parser.add_argument('--hands', type=int, default=32, help='测试手数（默认32）')
    parser.add_argument('--threads', type=int, default=4, help='线程数（默认4）')
    parser.add_argument('--verbose', action='store_true', help='详细输出模式')
    args = parser.parse_args()

    run_test(num_hands=args.hands, num_threads=args.threads, verbose=args.verbose)
    print('测试完成！')
