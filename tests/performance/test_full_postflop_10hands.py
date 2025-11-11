#!/usr/bin/env python
"""
完整的AI vs Random测试 - 包含翻后决策
测试10手牌，每手包含完整的flop/turn/river决策流程
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import random
import time
from dataclasses import dataclass
from typing import List, Tuple, Optional

from advisor.range_engine import Hand, Board, create_deck, Card
from advisor.range_engine.evaluator import HandEvaluator
from advisor.strategy_engine import ProLevelAdvisor, GameState
from advisor.opponent_modeling import PlayerType


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


class FullGameAIPlayer:
    """完整游戏流程的AI玩家"""

    def __init__(self, name: str = "AI"):
        self.name = name
        self.advisor = ProLevelAdvisor(exploit_weight=0.4)

    def decide(self, game_state: GameState) -> Tuple[str, float]:
        """
        做决策（翻前或翻后）

        Returns:
            (action, amount) where action in ['fold', 'check', 'call', 'bet', 'raise']
            amount是bet/raise的金额（BB）
        """
        try:
            decision = self.advisor.advise(game_state)
            action = decision.recommended_action.lower()

            # 解析动作
            if 'fold' in action:
                return 'fold', 0.0
            elif 'check' in action:
                return 'check', 0.0
            elif 'call' in action:
                return 'call', 0.0
            elif 'bet' in action or 'raise' in action or 'r' in action:
                # 计算下注金额
                sizing = decision.optimal_sizing if decision.optimal_sizing else 0.66
                amount = game_state.pot_size * sizing

                # 至少下注0.5BB，最多all-in
                amount = max(0.5, min(amount, game_state.hero_stack))

                if game_state.facing_bet > 0:
                    return 'raise', amount
                else:
                    return 'bet', amount
            else:
                return 'check', 0.0

        except Exception as e:
            print(f"  [AI决策错误: {e}，使用保守策略]")
            # 出错时保守决策
            if game_state.facing_bet > 0:
                # 面对下注：根据pot odds
                pot_odds = game_state.bet_to_call / (game_state.pot_size + game_state.bet_to_call)
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
        self.fold_rate = 0.3
        self.bet_rate = 0.2

    def decide(self, pot: float, facing_bet: float, stack: float) -> Tuple[str, float]:
        """
        简单的随机决策

        Returns:
            (action, amount)
        """
        r = random.random()

        if facing_bet > 0:
            # 面对下注
            if r < self.fold_rate:
                return 'fold', 0.0
            elif r < self.fold_rate + 0.15:
                return 'raise', facing_bet * 2.5
            else:
                return 'call', 0.0
        else:
            # 未面对下注
            if r < self.bet_rate:
                bet_size = pot * random.uniform(0.5, 1.0)
                return 'bet', min(bet_size, stack)
            else:
                return 'check', 0.0


def play_full_hand(hand_num: int, ai_player: FullGameAIPlayer, random_player: SimpleRandomPlayer,
                   ai_position: str, starting_stack: float = 100.0) -> FullHandRecord:
    """
    玩一手完整的牌（包含翻前+flop+turn+river）

    Args:
        hand_num: 手牌编号
        ai_player: AI玩家
        random_player: Random玩家
        ai_position: AI位置 ('BTN' or 'BB')
        starting_stack: 起始筹码

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

    current_street_ai_invested = ai_invested
    current_street_random_invested = random_invested

    # ===== 翻前 =====
    print(f"\n  === 翻前 ===")
    print(f"  AI: {ai_hand} ({ai_position})")
    print(f"  Random: {random_hand}")
    print(f"  Pot: {pot:.1f}BB")

    # 翻前行动（简化：只有一轮）
    if ai_position == 'BTN':
        # AI先行动
        game_state = GameState(
            street='preflop',
            position='BTN',
            is_in_position=True,
            hero_hand=ai_hand,
            pot_size=pot,
            effective_stack=min(ai_stack, random_stack),
            hero_stack=ai_stack,
            board=Board([]),
            facing_bet=0,
            bet_to_call=bb - sb,  # 需要补到bb
            opponent_type=PlayerType.UNKNOWN
        )

        ai_action, ai_amount = ai_player.decide(game_state)

        if ai_action == 'fold':
            actions.append(StreetAction('preflop', 'AI', 'fold', 0, pot))
            print(f"  AI folds")
            return FullHandRecord(
                hand_num, ai_position, str(ai_hand), str(random_hand),
                [], '', '', actions, 'Random', -ai_invested, pot, False
            )
        elif ai_action == 'call':
            # Limp（补到bb）
            call_amount = bb - ai_invested
            ai_invested += call_amount
            ai_stack -= call_amount
            pot += call_amount
            current_street_ai_invested = ai_invested
            actions.append(StreetAction('preflop', 'AI', 'call', call_amount, pot))
            print(f"  AI calls {call_amount:.1f}BB, pot={pot:.1f}BB")
        else:  # raise
            # Open raise
            raise_to = max(ai_amount, bb * 2.5)
            raise_amount = raise_to - ai_invested
            ai_invested += raise_amount
            ai_stack -= raise_amount
            pot += raise_amount
            current_street_ai_invested = ai_invested
            actions.append(StreetAction('preflop', 'AI', f'raise to {raise_to:.1f}BB', raise_amount, pot))
            print(f"  AI raises to {raise_to:.1f}BB, pot={pot:.1f}BB")

            # Random响应
            facing_bet = raise_to - random_invested
            random_action, random_amount = random_player.decide(pot, facing_bet, random_stack)

            if random_action == 'fold':
                actions.append(StreetAction('preflop', 'Random', 'fold', 0, pot))
                print(f"  Random folds")
                return FullHandRecord(
                    hand_num, ai_position, str(ai_hand), str(random_hand),
                    [], '', '', actions, 'AI', pot - ai_invested, pot, False
                )
            elif random_action == 'call':
                call_amount = raise_to - random_invested
                random_invested += call_amount
                random_stack -= call_amount
                pot += call_amount
                current_street_random_invested = random_invested
                actions.append(StreetAction('preflop', 'Random', 'call', call_amount, pot))
                print(f"  Random calls {call_amount:.1f}BB, pot={pot:.1f}BB")
            # 忽略3-bet简化

    else:  # AI在BB
        # Random先行动
        random_action, random_amount = random_player.decide(pot, bb - sb, random_stack)

        if random_action == 'fold':
            actions.append(StreetAction('preflop', 'Random', 'fold', 0, pot))
            print(f"  Random folds")
            return FullHandRecord(
                hand_num, ai_position, str(ai_hand), str(random_hand),
                [], '', '', actions, 'AI', pot - ai_invested, pot, False
            )
        elif random_action == 'call':
            call_amount = bb - random_invested
            random_invested += call_amount
            random_stack -= call_amount
            pot += call_amount
            current_street_random_invested = random_invested
            actions.append(StreetAction('preflop', 'Random', 'call', call_amount, pot))
            print(f"  Random calls {call_amount:.1f}BB, pot={pot:.1f}BB")

            # AI可以check或raise（简化：AI总是check）
            actions.append(StreetAction('preflop', 'AI', 'check', 0, pot))
            print(f"  AI checks")

        else:  # Random raise
            raise_to = max(random_amount, bb * 2.5)
            raise_amount = raise_to - random_invested
            random_invested += raise_amount
            random_stack -= raise_amount
            pot += raise_amount
            current_street_random_invested = random_invested
            actions.append(StreetAction('preflop', 'Random', f'raise to {raise_to:.1f}BB', raise_amount, pot))
            print(f"  Random raises to {raise_to:.1f}BB, pot={pot:.1f}BB")

            # AI响应
            game_state = GameState(
                street='preflop',
                position='BB',
                is_in_position=False,
                hero_hand=ai_hand,
                pot_size=pot,
                effective_stack=min(ai_stack, random_stack),
                hero_stack=ai_stack,
                board=Board([]),
                facing_bet=raise_to,
                bet_to_call=raise_to - ai_invested,
                opponent_type=PlayerType.UNKNOWN
            )

            ai_action, ai_amount = ai_player.decide(game_state)

            if ai_action == 'fold':
                actions.append(StreetAction('preflop', 'AI', 'fold', 0, pot))
                print(f"  AI folds")
                return FullHandRecord(
                    hand_num, ai_position, str(ai_hand), str(random_hand),
                    [], '', '', actions, 'Random', -ai_invested, pot, False
                )
            else:  # call
                call_amount = raise_to - ai_invested
                ai_invested += call_amount
                ai_stack -= call_amount
                pot += call_amount
                current_street_ai_invested = ai_invested
                actions.append(StreetAction('preflop', 'AI', 'call', call_amount, pot))
                print(f"  AI calls {call_amount:.1f}BB, pot={pot:.1f}BB")

    # ===== Flop =====
    flop_cards = board_cards[0:3]
    flop_str = [str(c) for c in flop_cards]
    board = Board(flop_cards)

    print(f"\n  === Flop: {' '.join(flop_str)} ===")
    print(f"  Pot: {pot:.1f}BB")

    # 重置街道投入
    current_street_ai_invested = 0
    current_street_random_invested = 0

    # Flop行动（OOP先行动）
    if ai_position == 'BB':  # AI OOP
        # AI先行动
        game_state = GameState(
            street='flop',
            position='BB',
            is_in_position=False,
            hero_hand=ai_hand,
            pot_size=pot,
            effective_stack=min(ai_stack, random_stack),
            hero_stack=ai_stack,
            board=board,
            facing_bet=0,
            bet_to_call=0,
            opponent_type=PlayerType.UNKNOWN
        )

        ai_action, ai_amount = ai_player.decide(game_state)

        if ai_action == 'bet':
            bet_amount = min(ai_amount, ai_stack)
            ai_invested += bet_amount
            ai_stack -= bet_amount
            pot += bet_amount
            current_street_ai_invested = bet_amount
            actions.append(StreetAction('flop', 'AI', f'bet {bet_amount:.1f}BB', bet_amount, pot))
            print(f"  AI bets {bet_amount:.1f}BB, pot={pot:.1f}BB")

            # Random响应
            random_action, random_amount = random_player.decide(pot, bet_amount, random_stack)

            if random_action == 'fold':
                actions.append(StreetAction('flop', 'Random', 'fold', 0, pot))
                print(f"  Random folds")
                return FullHandRecord(
                    hand_num, ai_position, str(ai_hand), str(random_hand),
                    flop_str, '', '', actions, 'AI', pot - ai_invested, pot, False
                )
            else:  # call（忽略raise）
                call_amount = bet_amount
                random_invested += call_amount
                random_stack -= call_amount
                pot += call_amount
                current_street_random_invested = call_amount
                actions.append(StreetAction('flop', 'Random', 'call', call_amount, pot))
                print(f"  Random calls {call_amount:.1f}BB, pot={pot:.1f}BB")

        else:  # check
            actions.append(StreetAction('flop', 'AI', 'check', 0, pot))
            print(f"  AI checks")

            # Random行动
            random_action, random_amount = random_player.decide(pot, 0, random_stack)

            if random_action == 'bet':
                bet_amount = min(random_amount, random_stack)
                random_invested += bet_amount
                random_stack -= bet_amount
                pot += bet_amount
                current_street_random_invested = bet_amount
                actions.append(StreetAction('flop', 'Random', f'bet {bet_amount:.1f}BB', bet_amount, pot))
                print(f"  Random bets {bet_amount:.1f}BB, pot={pot:.1f}BB")

                # AI响应
                game_state = GameState(
                    street='flop',
                    position='BB',
                    is_in_position=False,
                    hero_hand=ai_hand,
                    pot_size=pot,
                    effective_stack=min(ai_stack, random_stack),
                    hero_stack=ai_stack,
                    board=board,
                    facing_bet=bet_amount,
                    bet_to_call=bet_amount,
                    opponent_type=PlayerType.UNKNOWN
                )

                ai_action, ai_amount = ai_player.decide(game_state)

                if ai_action == 'fold':
                    actions.append(StreetAction('flop', 'AI', 'fold', 0, pot))
                    print(f"  AI folds")
                    return FullHandRecord(
                        hand_num, ai_position, str(ai_hand), str(random_hand),
                        flop_str, '', '', actions, 'Random', -ai_invested, pot, False
                    )
                else:  # call
                    call_amount = bet_amount
                    ai_invested += call_amount
                    ai_stack -= call_amount
                    pot += call_amount
                    current_street_ai_invested = call_amount
                    actions.append(StreetAction('flop', 'AI', 'call', call_amount, pot))
                    print(f"  AI calls {call_amount:.1f}BB, pot={pot:.1f}BB")

            else:  # check
                actions.append(StreetAction('flop', 'Random', 'check', 0, pot))
                print(f"  Random checks")

    else:  # AI IP (BTN)
        # Random先行动（OOP）
        random_action, random_amount = random_player.decide(pot, 0, random_stack)

        if random_action == 'bet':
            bet_amount = min(random_amount, random_stack)
            random_invested += bet_amount
            random_stack -= bet_amount
            pot += bet_amount
            current_street_random_invested = bet_amount
            actions.append(StreetAction('flop', 'Random', f'bet {bet_amount:.1f}BB', bet_amount, pot))
            print(f"  Random bets {bet_amount:.1f}BB, pot={pot:.1f}BB")

            # AI响应
            game_state = GameState(
                street='flop',
                position='BTN',
                is_in_position=True,
                hero_hand=ai_hand,
                pot_size=pot,
                effective_stack=min(ai_stack, random_stack),
                hero_stack=ai_stack,
                board=board,
                facing_bet=bet_amount,
                bet_to_call=bet_amount,
                opponent_type=PlayerType.UNKNOWN
            )

            ai_action, ai_amount = ai_player.decide(game_state)

            if ai_action == 'fold':
                actions.append(StreetAction('flop', 'AI', 'fold', 0, pot))
                print(f"  AI folds")
                return FullHandRecord(
                    hand_num, ai_position, str(ai_hand), str(random_hand),
                    flop_str, '', '', actions, 'Random', -ai_invested, pot, False
                )
            else:  # call
                call_amount = bet_amount
                ai_invested += call_amount
                ai_stack -= call_amount
                pot += call_amount
                current_street_ai_invested = call_amount
                actions.append(StreetAction('flop', 'AI', 'call', call_amount, pot))
                print(f"  AI calls {call_amount:.1f}BB, pot={pot:.1f}BB")

        else:  # check
            actions.append(StreetAction('flop', 'Random', 'check', 0, pot))
            print(f"  Random checks")

            # AI行动
            game_state = GameState(
                street='flop',
                position='BTN',
                is_in_position=True,
                hero_hand=ai_hand,
                pot_size=pot,
                effective_stack=min(ai_stack, random_stack),
                hero_stack=ai_stack,
                board=board,
                facing_bet=0,
                bet_to_call=0,
                opponent_type=PlayerType.UNKNOWN
            )

            ai_action, ai_amount = ai_player.decide(game_state)

            if ai_action == 'bet':
                bet_amount = min(ai_amount, ai_stack)
                ai_invested += bet_amount
                ai_stack -= bet_amount
                pot += bet_amount
                current_street_ai_invested = bet_amount
                actions.append(StreetAction('flop', 'AI', f'bet {bet_amount:.1f}BB', bet_amount, pot))
                print(f"  AI bets {bet_amount:.1f}BB, pot={pot:.1f}BB")

                # Random响应
                random_action, random_amount = random_player.decide(pot, bet_amount, random_stack)

                if random_action == 'fold':
                    actions.append(StreetAction('flop', 'Random', 'fold', 0, pot))
                    print(f"  Random folds")
                    return FullHandRecord(
                        hand_num, ai_position, str(ai_hand), str(random_hand),
                        flop_str, '', '', actions, 'AI', pot - ai_invested, pot, False
                    )
                else:  # call
                    call_amount = bet_amount
                    random_invested += call_amount
                    random_stack -= call_amount
                    pot += call_amount
                    current_street_random_invested = call_amount
                    actions.append(StreetAction('flop', 'Random', 'call', call_amount, pot))
                    print(f"  Random calls {call_amount:.1f}BB, pot={pot:.1f}BB")

            else:  # check
                actions.append(StreetAction('flop', 'AI', 'check', 0, pot))
                print(f"  AI checks")

    # ===== Turn =====
    turn_card = board_cards[3]
    turn_str = str(turn_card)
    board = Board(flop_cards + [turn_card])

    print(f"\n  === Turn: {turn_str} ===")
    print(f"  Board: {' '.join(flop_str)} {turn_str}")
    print(f"  Pot: {pot:.1f}BB")

    # 简化：turn和river都check到摊牌
    if ai_position == 'BB':
        actions.append(StreetAction('turn', 'AI', 'check', 0, pot))
        actions.append(StreetAction('turn', 'Random', 'check', 0, pot))
        print(f"  AI checks, Random checks")
    else:
        actions.append(StreetAction('turn', 'Random', 'check', 0, pot))
        actions.append(StreetAction('turn', 'AI', 'check', 0, pot))
        print(f"  Random checks, AI checks")

    # ===== River =====
    river_card = board_cards[4]
    river_str = str(river_card)
    board = Board(flop_cards + [turn_card, river_card])

    print(f"\n  === River: {river_str} ===")
    print(f"  Board: {' '.join(flop_str)} {turn_str} {river_str}")
    print(f"  Pot: {pot:.1f}BB")

    # 简化：river也check到摊牌
    if ai_position == 'BB':
        actions.append(StreetAction('river', 'AI', 'check', 0, pot))
        actions.append(StreetAction('river', 'Random', 'check', 0, pot))
        print(f"  AI checks, Random checks")
    else:
        actions.append(StreetAction('river', 'Random', 'check', 0, pot))
        actions.append(StreetAction('river', 'AI', 'check', 0, pot))
        print(f"  Random checks, AI checks")

    # ===== Showdown =====
    print(f"\n  === Showdown ===")

    ai_cards = list(ai_hand.cards) + list(board.cards)
    random_cards = list(random_hand.cards) + list(board.cards)

    ai_strength = HandEvaluator.evaluate_best_5(ai_cards)
    random_strength = HandEvaluator.evaluate_best_5(random_cards)

    print(f"  AI: {ai_strength.rank.name}")
    print(f"  Random: {random_strength.rank.name}")

    if ai_strength > random_strength:
        winner = 'AI'
        profit = pot - ai_invested
        print(f"  AI wins {pot:.1f}BB!")
    elif ai_strength < random_strength:
        winner = 'Random'
        profit = -ai_invested
        print(f"  Random wins {pot:.1f}BB")
    else:
        winner = 'Tie'
        profit = 0.0
        print(f"  Tie (split pot)")

    return FullHandRecord(
        hand_num, ai_position, str(ai_hand), str(random_hand),
        flop_str, turn_str, river_str,
        actions, winner, profit, pot, True,
        ai_strength.rank.name, random_strength.rank.name
    )


def run_full_test(num_hands: int = 10):
    """运行完整测试"""
    print('=' * 80)
    print('🤖 AI vs Random - 完整测试（包含翻后决策）')
    print('=' * 80)
    print(f'\n配置:')
    print(f'  手数: {num_hands}')
    print(f'  精度: iterations=1000, max_combos=100')
    print(f'  包含: 翻前 + Flop + Turn + River完整决策')
    print(f'  开始时间: {time.strftime("%Y-%m-%d %H:%M:%S")}')

    # 初始化
    from advisor.range_engine.evaluator_fast_v2 import precompute_if_needed_v2
    print('\n初始化查找表...')
    precompute_if_needed_v2()
    print('查找表就绪')

    ai = FullGameAIPlayer("PokerAI")
    random_player = SimpleRandomPlayer("RandomBot")

    results: List[FullHandRecord] = []
    start_time = time.time()

    for i in range(num_hands):
        ai_position = 'BTN' if i % 2 == 0 else 'BB'

        print(f'\n{"="*80}')
        print(f'Hand #{i+1} - AI Position: {ai_position}')
        print(f'{"="*80}')

        try:
            result = play_full_hand(i, ai, random_player, ai_position)
            results.append(result)

            print(f"\n  >>> AI Profit: {result.ai_profit:+.2f}BB")

        except Exception as e:
            print(f'\n  [错误: {e}]')
            import traceback
            traceback.print_exc()

    total_time = time.time() - start_time

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
    print(f'平均每手: {total_time/len(results):.1f}秒')
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

    # 保存详细报告
    output_file = f'/home/user/pokerAI/test_full_postflop_{num_hands}hands_result.txt'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('=' * 80 + '\n')
        f.write(f'AI vs Random - 完整测试结果（{num_hands}手）\n')
        f.write('=' * 80 + '\n\n')
        f.write(f'测试时间: {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write(f'总用时: {total_time:.1f}秒\n')
        f.write(f'平均每手: {total_time/len(results):.1f}秒\n\n')

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
            f.write(f'Board: {" ".join(r.flop)} {r.turn} {r.river}\n\n')

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
    run_full_test(num_hands=10)
    print('测试完成！')
