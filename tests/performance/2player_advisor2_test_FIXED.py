#!/usr/bin/env python
"""
2人对局advisor_v2测试 - 真正的德州扑克 - 修复版本

修复内容：
1. 修复raise amount语义混乱问题
2. 修复all-in后仍然记录action的问题
3. 添加all-in状态跟踪，跳过已all-in玩家的betting round
4. 修复uncalled bet处理逻辑
5. 修复筹码不足最小加注时的处理
6. 添加详细的调试日志
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

# 导入对手玩家接口
from tests.performance.opponent_players import OpponentPlayer, create_opponent


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
            amount: 对于bet/raise，是raise增量（不是raise to的总额）
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
                # 返回raise增量（不是raise to的总额）
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


def run_betting_round(
    street: str,
    ai_player: AdvisorV2Player,
    opponent_player: OpponentPlayer,
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
    verbose: bool = True,
    debug: bool = False  # 新增：调试模式
) -> Tuple[Optional[str], float, float, float, float, float]:
    """
    运行一个完整的betting round（支持多轮加注）

    Returns:
        (winner, pot, ai_stack, random_stack, ai_invested, random_invested)
        winner: 'AI', 'Random', or None (继续游戏)
    """
    # 确定谁先行动
    # Preflop: BTN先行动（2人对局中BTN=SB，需要补齐或raise）
    # Flop/Turn/River: OOP先行动（BB先动）
    if street == 'preflop':
        ai_acts_first = (ai_position == 'BTN')
    else:
        ai_acts_first = (ai_position == 'BB')

    # 当前街道的投入（用于计算facing bet）
    if street == 'preflop':
        street_ai_invested = ai_invested
        street_random_invested = random_invested
    else:
        street_ai_invested = 0
        street_random_invested = 0

    # 行动循环
    last_aggressor = None
    last_raise_increment = 1.0  # 最小加注增量，初始为1BB
    num_actions = 0
    max_actions = 20

    # All-in阈值
    ALLIN_THRESHOLD = 1.0

    if debug:
        print(f"\n  [DEBUG] === Starting {street} betting round ===")
        print(f"  [DEBUG] Pot: {pot:.1f}BB")
        print(f"  [DEBUG] AI stack: {ai_stack:.1f}BB, invested this street: {street_ai_invested:.1f}BB")
        print(f"  [DEBUG] Random stack: {random_stack:.1f}BB, invested this street: {street_random_invested:.1f}BB")

    # 修复点1: 检查是否有玩家已经all-in（筹码<=阈值）
    ai_is_allin = (ai_stack <= ALLIN_THRESHOLD)
    random_is_allin = (random_stack <= ALLIN_THRESHOLD)

    if ai_is_allin and random_is_allin:
        if verbose:
            print(f"  [Both players all-in, skipping betting round]")
        return (None, pot, ai_stack, random_stack, ai_invested, random_invested)

    while num_actions < max_actions:
        num_actions += 1

        # 重新检查all-in状态（可能在本轮中改变）
        ai_is_allin = (ai_stack <= ALLIN_THRESHOLD)
        random_is_allin = (random_stack <= ALLIN_THRESHOLD)

        # 修复点2: 如果双方都all-in且投入相等，结束betting
        if ai_is_allin and random_is_allin:
            if abs(street_ai_invested - street_random_invested) < 0.01:
                if verbose:
                    print(f"  [Both players all-in with equal investment, ending betting round]")
                return (None, pot, ai_stack, random_stack, ai_invested, random_invested)

        # 确定当前行动的玩家
        if num_actions == 1:
            current_player = 'AI' if ai_acts_first else 'Random'
        else:
            # 轮流行动
            if actions[-1].player == 'AI':
                current_player = 'Random'
            else:
                current_player = 'AI'

        # 获取当前玩家的stack和状态
        current_stack = ai_stack if current_player == 'AI' else random_stack
        current_is_allin = ai_is_allin if current_player == 'AI' else random_is_allin

        # 修复点3: 如果当前玩家已经all-in，跳过其行动
        if current_is_allin:
            # 检查对手是否也已投入相等金额
            if current_player == 'AI':
                opponent_invested = street_random_invested
                current_invested = street_ai_invested
            else:
                opponent_invested = street_ai_invested
                current_invested = street_random_invested

            # 如果对手投入更多，对手需要行动
            if opponent_invested > current_invested + 0.01:
                # 切换到对手
                if current_player == 'AI':
                    current_player = 'Random'
                    current_stack = random_stack
                    current_is_allin = random_is_allin
                else:
                    current_player = 'AI'
                    current_stack = ai_stack
                    current_is_allin = ai_is_allin
            else:
                # 双方投入相等，结束betting round
                if verbose:
                    print(f"  [One player all-in, bets equal, ending betting round]")
                return (None, pot, ai_stack, random_stack, ai_invested, random_invested)

        # 计算facing bet和to_call
        if current_player == 'AI':
            facing_bet = street_random_invested
            to_call = max(0, street_random_invested - street_ai_invested)
        else:
            facing_bet = street_ai_invested
            to_call = max(0, street_ai_invested - street_random_invested)

        if debug:
            print(f"\n  [DEBUG] Action #{num_actions}, {current_player} to act")
            print(f"  [DEBUG] Facing bet: {facing_bet:.1f}BB, to_call: {to_call:.1f}BB")
            print(f"  [DEBUG] {current_player} stack: {current_stack:.1f}BB, is_allin: {current_is_allin}")

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
            action_type, amount = opponent_player.decide(pot, facing_bet, random_stack)

        if debug:
            print(f"  [DEBUG] Decision: {action_type}, amount: {amount:.1f}BB")

        # === Action规范化和验证 ===
        # 1. 如果面对下注，"bet"应该是"raise"
        if to_call > 0.01 and action_type == 'bet':
            action_type = 'raise'
            if verbose:
                print(f"  [Normalized: bet -> raise (facing {to_call:.1f}BB)]")

        # 2. 如果不面对下注，"raise"应该是"bet"
        if to_call <= 0.01 and action_type == 'raise':
            action_type = 'bet'
            if verbose:
                print(f"  [Normalized: raise -> bet (no bet to raise)]")

        # 3. 验证action合法性
        if action_type == 'check' and to_call > 0.01:
            if verbose:
                print(f"  [Invalid: check when facing {to_call:.1f}BB, forcing fold]")
            action_type = 'fold'

        if action_type == 'fold' and to_call <= 0.01:
            if verbose:
                print(f"  [Invalid: fold when can check free, forcing check]")
            action_type = 'check'

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
            if len(actions) >= 2 and actions[-2].action.startswith('check') and actions[-2].street == street:
                return (None, pot, ai_stack, random_stack, ai_invested, random_invested)

            continue

        elif action_type == 'call':
            # 计算实际call金额（不能超过stack）
            call_amount = min(to_call, current_stack)

            if call_amount <= 0.01:
                # 实际上是check
                actions.append(StreetAction(street, current_player, 'check', 0, pot))
                if verbose:
                    print(f"  {current_player} checks (call 0)")
                if len(actions) >= 2 and actions[-2].action.startswith('check') and actions[-2].street == street:
                    return (None, pot, ai_stack, random_stack, ai_invested, random_invested)
                continue

            # 执行call
            if current_player == 'AI':
                ai_invested += call_amount
                ai_stack -= call_amount
                street_ai_invested += call_amount
            else:
                random_invested += call_amount
                random_stack -= call_amount
                street_random_invested += call_amount

            pot += call_amount

            # All-in判断
            is_allin = (current_stack - call_amount <= ALLIN_THRESHOLD)

            # 修复点4: 如果是all-in call且未完全call对手的bet，退回uncalled bet
            if is_allin and call_amount < to_call - 0.01:
                uncalled_bet = to_call - call_amount
                if verbose:
                    print(f"  [All-in call: returning {uncalled_bet:.1f}BB uncalled bet to opponent]")

                if current_player == 'AI':
                    random_stack += uncalled_bet
                    random_invested -= uncalled_bet
                    street_random_invested -= uncalled_bet
                    pot -= uncalled_bet
                else:
                    ai_stack += uncalled_bet
                    ai_invested -= uncalled_bet
                    street_ai_invested -= uncalled_bet
                    pot -= uncalled_bet

            # 记录action
            if is_allin:
                actions.append(StreetAction(street, current_player, f'call {call_amount:.1f}BB (all-in)', call_amount, pot))
                if verbose:
                    print(f"  {current_player} calls {call_amount:.1f}BB (all-in), pot={pot:.1f}BB")
            else:
                actions.append(StreetAction(street, current_player, 'call', call_amount, pot))
                if verbose:
                    print(f"  {current_player} calls {call_amount:.1f}BB, pot={pot:.1f}BB")

            if debug:
                print(f"  [DEBUG] After call: pot={pot:.1f}BB, AI stack={ai_stack:.1f}BB, Random stack={random_stack:.1f}BB")

            return (None, pot, ai_stack, random_stack, ai_invested, random_invested)

        elif action_type == 'bet':
            # Bet只在不面对下注时有效
            bet_amount = min(amount, current_stack)

            # 防止0BB或过小的bet
            if bet_amount < 0.5:
                if verbose:
                    print(f"  [Bet amount too small ({bet_amount:.2f}BB), checking instead]")
                actions.append(StreetAction(street, current_player, 'check', 0, pot))
                if verbose:
                    print(f"  {current_player} checks")
                if len(actions) >= 2 and actions[-2].action.startswith('check') and actions[-2].street == street:
                    return (None, pot, ai_stack, random_stack, ai_invested, random_invested)
                continue

            if current_player == 'AI':
                ai_invested += bet_amount
                ai_stack -= bet_amount
                street_ai_invested += bet_amount
            else:
                random_invested += bet_amount
                random_stack -= bet_amount
                street_random_invested += bet_amount

            pot += bet_amount
            last_raise_increment = bet_amount

            # All-in判断
            is_allin = (current_stack - bet_amount <= ALLIN_THRESHOLD)

            # 记录action
            if is_allin:
                actions.append(StreetAction(street, current_player, f'bet {bet_amount:.1f}BB (all-in)', bet_amount, pot))
                if verbose:
                    print(f"  {current_player} bets {bet_amount:.1f}BB (all-in), pot={pot:.1f}BB")
            else:
                actions.append(StreetAction(street, current_player, f'bet {bet_amount:.1f}BB', bet_amount, pot))
                if verbose:
                    print(f"  {current_player} bets {bet_amount:.1f}BB, pot={pot:.1f}BB")

            if debug:
                print(f"  [DEBUG] After bet: pot={pot:.1f}BB, AI stack={ai_stack:.1f}BB, Random stack={random_stack:.1f}BB")

            last_aggressor = current_player
            continue

        elif action_type == 'raise':
            # 先计算需要call多少
            call_amt = to_call

            # 如果筹码不足以call，转为all-in call或fold
            if current_stack < call_amt:
                if current_stack > ALLIN_THRESHOLD:
                    # 筹码不足以完成call，但可以all-in call
                    if verbose:
                        print(f"  [Insufficient chips for raise, all-in calling instead]")
                    call_amount = current_stack

                    if current_player == 'AI':
                        ai_invested += call_amount
                        ai_stack -= call_amount
                        street_ai_invested += call_amount
                    else:
                        random_invested += call_amount
                        random_stack -= call_amount
                        street_random_invested += call_amount

                    pot += call_amount

                    # 退回对手未被call的部分
                    uncalled_bet = call_amt - call_amount
                    if verbose:
                        print(f"  [All-in call: returning {uncalled_bet:.1f}BB uncalled bet to opponent]")

                    if current_player == 'AI':
                        random_stack += uncalled_bet
                        random_invested -= uncalled_bet
                        street_random_invested -= uncalled_bet
                        pot -= uncalled_bet
                    else:
                        ai_stack += uncalled_bet
                        ai_invested -= uncalled_bet
                        street_ai_invested -= uncalled_bet
                        pot -= uncalled_bet

                    actions.append(StreetAction(street, current_player, f'call {call_amount:.1f}BB (all-in)', call_amount, pot))
                    if verbose:
                        print(f"  {current_player} calls {call_amount:.1f}BB (all-in), pot={pot:.1f}BB")
                    return (None, pot, ai_stack, random_stack, ai_invested, random_invested)
                else:
                    # 没有筹码了，fold
                    if verbose:
                        print(f"  [No chips to raise, folding]")
                    actions.append(StreetAction(street, current_player, 'fold', 0, pot))
                    if verbose:
                        print(f"  {current_player} folds")
                    winner = 'Random' if current_player == 'AI' else 'AI'
                    return (winner, pot, ai_stack, random_stack, ai_invested, random_invested)

            # 修复点5: 统一amount语义为raise增量
            # amount已经是raise增量（不是raise to的总额）
            raise_amt = min(amount, current_stack - call_amt)

            # All-in判断
            is_allin = (current_stack - call_amt - raise_amt <= ALLIN_THRESHOLD)

            # 计算raise to的总额
            raise_to = facing_bet + raise_amt

            # 计算最小加注金额
            min_raise_to = facing_bet + last_raise_increment

            if debug:
                print(f"  [DEBUG] Raise attempt: call_amt={call_amt:.1f}BB, raise_amt={raise_amt:.1f}BB")
                print(f"  [DEBUG] raise_to={raise_to:.1f}BB, min_raise_to={min_raise_to:.1f}BB, is_allin={is_allin}")

            # 修复点6: 正确处理筹码不足最小加注的情况
            if raise_to < min_raise_to - 0.01:
                # 不满足最小加注
                if is_allin:
                    # All-in但不足最小加注
                    # 德州扑克规则：允许这个all-in，但不重新开启加注轮
                    if verbose:
                        print(f"  [All-in below min raise: {raise_to:.1f}BB < {min_raise_to:.1f}BB, allowing all-in raise but no re-open]")

                    # 执行all-in raise（投入全部筹码）
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
                    last_raise_increment = raise_amt  # 虽然不重新开启，但记录增量

                    actions.append(StreetAction(street, current_player, f'raise to {raise_to:.1f}BB (all-in)', total_amt, pot))
                    if verbose:
                        print(f"  {current_player} raises to {raise_to:.1f}BB (all-in), pot={pot:.1f}BB")

                    if debug:
                        print(f"  [DEBUG] After all-in raise: pot={pot:.1f}BB, AI stack={ai_stack:.1f}BB, Random stack={random_stack:.1f}BB")

                    last_aggressor = current_player
                    continue
                else:
                    # 不是all-in且不满足最小加注，转为call
                    if verbose:
                        print(f"  [Raise below minimum: {raise_to:.1f}BB < {min_raise_to:.1f}BB, calling instead]")
                    call_amount = call_amt

                    if current_player == 'AI':
                        ai_invested += call_amount
                        ai_stack -= call_amount
                        street_ai_invested += call_amount
                    else:
                        random_invested += call_amount
                        random_stack -= call_amount
                        street_random_invested += call_amount

                    pot += call_amount
                    actions.append(StreetAction(street, current_player, 'call', call_amount, pot))
                    if verbose:
                        print(f"  {current_player} calls {call_amount:.1f}BB, pot={pot:.1f}BB")
                    return (None, pot, ai_stack, random_stack, ai_invested, random_invested)

            # 如果raise_amt过小，转为call
            if raise_amt < 0.5 and not is_allin:
                if verbose:
                    print(f"  [Raise amount too small, calling instead]")
                call_amount = call_amt

                if current_player == 'AI':
                    ai_invested += call_amount
                    ai_stack -= call_amount
                    street_ai_invested += call_amount
                else:
                    random_invested += call_amount
                    random_stack -= call_amount
                    street_random_invested += call_amount

                pot += call_amount
                actions.append(StreetAction(street, current_player, 'call', call_amount, pot))
                if verbose:
                    print(f"  {current_player} calls {call_amount:.1f}BB, pot={pot:.1f}BB")
                return (None, pot, ai_stack, random_stack, ai_invested, random_invested)

            # 正常的raise
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
            last_raise_increment = raise_amt

            # 记录action
            if is_allin:
                actions.append(StreetAction(street, current_player, f'raise to {raise_to:.1f}BB (all-in)', total_amt, pot))
                if verbose:
                    print(f"  {current_player} raises to {raise_to:.1f}BB (all-in), pot={pot:.1f}BB")
            else:
                actions.append(StreetAction(street, current_player, f'raise to {raise_to:.1f}BB', total_amt, pot))
                if verbose:
                    print(f"  {current_player} raises to {raise_to:.1f}BB, pot={pot:.1f}BB")

            if debug:
                print(f"  [DEBUG] After raise: pot={pot:.1f}BB, AI stack={ai_stack:.1f}BB, Random stack={random_stack:.1f}BB")

            last_aggressor = current_player
            continue

    # 如果达到max_actions，结束
    if verbose:
        print(f"  [Warning: Reached max actions in betting round]")
    return (None, pot, ai_stack, random_stack, ai_invested, random_invested)


def play_full_hand(hand_num: int, ai_player: AdvisorV2Player, opponent_player: OpponentPlayer,
                   ai_position: str, starting_stack: float = 100.0, verbose: bool = True,
                   base_seed: int = 42, debug: bool = False) -> FullHandRecord:
    """
    玩一手完整的牌（包含翻前+flop+turn+river，支持多轮加注）
    """
    sb = 0.5
    bb = 1.0

    # 设置随机种子
    random.seed(base_seed * 10000 + hand_num)

    # 发牌
    deck = create_deck()
    random.shuffle(deck)

    ai_hand = Hand([deck[0], deck[1]])
    random_hand = Hand([deck[2], deck[3]])
    board_cards = deck[4:9]

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
        opponent_player=opponent_player,
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
        verbose=verbose,
        debug=debug
    )

    if winner:
        profit = pot - ai_invested if winner == 'AI' else -ai_invested
        return FullHandRecord(
            hand_num, ai_position, str(ai_hand), str(random_hand),
            [], '', '', actions, winner, profit, pot, False
        )

    # 修复点7: 在每个街道开始前检查all-in状态
    ALLIN_THRESHOLD = 1.0
    ai_is_allin = (ai_stack <= ALLIN_THRESHOLD)
    random_is_allin = (random_stack <= ALLIN_THRESHOLD)

    # ===== Flop =====
    flop_cards = board_cards[0:3]
    flop_str = [str(c) for c in flop_cards]
    board = Board(flop_cards)

    if verbose:
        print(f"\n  === Flop: {' '.join(flop_str)} ===")
        print(f"  Pot: {pot:.1f}BB")
        if ai_is_allin or random_is_allin:
            print(f"  [Note: At least one player is all-in]")

    # 修复点8: 如果双方都all-in，跳过betting round
    if not (ai_is_allin and random_is_allin):
        winner, pot, ai_stack, random_stack, ai_invested, random_invested = run_betting_round(
            street='flop',
            ai_player=ai_player,
            opponent_player=opponent_player,
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
            verbose=verbose,
            debug=debug
        )

        if winner:
            profit = pot - ai_invested if winner == 'AI' else -ai_invested
            return FullHandRecord(
                hand_num, ai_position, str(ai_hand), str(random_hand),
                flop_str, '', '', actions, winner, profit, pot, False
            )

    # 更新all-in状态
    ai_is_allin = (ai_stack <= ALLIN_THRESHOLD)
    random_is_allin = (random_stack <= ALLIN_THRESHOLD)

    # ===== Turn =====
    turn_card = board_cards[3]
    turn_str = str(turn_card)
    board = Board(flop_cards + [turn_card])

    if verbose:
        print(f"\n  === Turn: {turn_str} ===")
        print(f"  Board: {' '.join(flop_str)} {turn_str}")
        print(f"  Pot: {pot:.1f}BB")
        if ai_is_allin or random_is_allin:
            print(f"  [Note: At least one player is all-in]")

    if not (ai_is_allin and random_is_allin):
        winner, pot, ai_stack, random_stack, ai_invested, random_invested = run_betting_round(
            street='turn',
            ai_player=ai_player,
            opponent_player=opponent_player,
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
            verbose=verbose,
            debug=debug
        )

        if winner:
            profit = pot - ai_invested if winner == 'AI' else -ai_invested
            return FullHandRecord(
                hand_num, ai_position, str(ai_hand), str(random_hand),
                flop_str, turn_str, '', actions, winner, profit, pot, False
            )

    # 更新all-in状态
    ai_is_allin = (ai_stack <= ALLIN_THRESHOLD)
    random_is_allin = (random_stack <= ALLIN_THRESHOLD)

    # ===== River =====
    river_card = board_cards[4]
    river_str = str(river_card)
    board = Board(board_cards)

    if verbose:
        print(f"\n  === River: {river_str} ===")
        print(f"  Board: {' '.join(flop_str)} {turn_str} {river_str}")
        print(f"  Pot: {pot:.1f}BB")
        if ai_is_allin or random_is_allin:
            print(f"  [Note: At least one player is all-in]")

    if not (ai_is_allin and random_is_allin):
        winner, pot, ai_stack, random_stack, ai_invested, random_invested = run_betting_round(
            street='river',
            ai_player=ai_player,
            opponent_player=opponent_player,
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
            verbose=verbose,
            debug=debug
        )

        if winner:
            profit = pot - ai_invested if winner == 'AI' else -ai_invested
            return FullHandRecord(
                hand_num, ai_position, str(ai_hand), str(random_hand),
                flop_str, turn_str, river_str, actions, winner, profit, pot, False
            )

    # 修复点9: Uncalled bet处理 - 检查river结束后是否有uncalled bet
    ai_is_allin = (ai_stack <= ALLIN_THRESHOLD)
    random_is_allin = (random_stack <= ALLIN_THRESHOLD)

    # 如果一方all-in且筹码为0，另一方有剩余筹码，检查是否有uncalled bet
    if ai_is_allin and ai_stack <= 0.01 and random_stack > ALLIN_THRESHOLD:
        # AI all-in且筹码为0，Random还有筹码
        # 检查是否Random有未被call的bet（通过查看最后一个action）
        if actions and actions[-1].player == 'Random' and actions[-1].action.startswith('bet'):
            # Random最后一个action是bet，但AI已经没筹码了
            # 这个bet是uncalled，应该退回
            if verbose:
                print(f"  [Warning: Uncalled bet detected, but already in pot calculation]")
    elif random_is_allin and random_stack <= 0.01 and ai_stack > ALLIN_THRESHOLD:
        # Random all-in且筹码为0，AI还有筹码
        if actions and actions[-1].player == 'AI' and actions[-1].action.startswith('bet'):
            if verbose:
                print(f"  [Warning: Uncalled bet detected, but already in pot calculation]")

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


def run_test(num_hands: int = 32, num_threads: int = 4, verbose: bool = False, seed: int = 42,
             opponent_type: str = 'random', debug: bool = False):
    """运行完整测试"""
    print('=' * 80)
    print(f'🤖 advisor_v2 vs {opponent_type.title()} - 修复版测试')
    print('=' * 80)
    print(f'\n配置:')
    print(f'  手数: {num_hands}')
    print(f'  线程数: {num_threads}')
    print(f'  对手类型: {opponent_type}')
    print(f'  随机种子: {seed}')
    print(f'  调试模式: {debug}')
    print(f'  修复内容: all-in逻辑, raise语义, pot计算, uncalled bet')
    print(f'  开始时间: {time.strftime("%Y-%m-%d %H:%M:%S")}')

    # 初始化
    print('\n初始化advisor_v2组件...')
    start_time = time.time()

    ai = AdvisorV2Player("AdvisorV2")
    opponent = create_opponent(opponent_type, name=f"{opponent_type.title()}Bot")

    results: List[FullHandRecord] = []

    # 多线程执行
    def process_hand(i):
        ai_position = 'BTN' if i % 2 == 0 else 'BB'
        if verbose:
            print(f'\n{"="*80}')
            print(f'Hand #{i+1} - AI Position: {ai_position}')
            print(f'{"="*80}')

        try:
            result = play_full_hand(i, ai, opponent, ai_position, verbose=verbose, base_seed=seed, debug=debug)
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
                    if len(results) % 10 == 0:
                        print(f'  进度: {len(results)}/{num_hands} 手完成')

    total_time = time.time() - start_time

    # 排序结果
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

    # 保存详细报告
    output_dir = r"C:\Users\Administrator\Documents\GitHub\pokerAI\test_results"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{opponent_type}_FIXED_test2.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('=' * 80 + '\n')
        f.write(f'advisor_v2 vs {opponent_type.title()} - 修复版测试结果（{num_hands}手）\n')
        f.write('=' * 80 + '\n\n')
        f.write(f'测试时间: {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write(f'随机种子: {seed}\n')
        f.write(f'总用时: {total_time:.1f}秒\n')
        f.write(f'平均每手: {total_time/len(results):.2f}秒\n\n')

        f.write('修复内容:\n')
        f.write('1. 修复all-in后仍然记录action的问题\n')
        f.write('2. 修复raise amount语义混乱问题\n')
        f.write('3. 添加all-in状态跟踪，跳过已all-in玩家的betting round\n')
        f.write('4. 修复uncalled bet处理逻辑\n')
        f.write('5. 修复筹码不足最小加注时的处理\n\n')

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
    parser = argparse.ArgumentParser(description='advisor_v2完整翻后测试 - 修复版')
    parser.add_argument('--hands', type=int, default=32, help='测试手数（默认32）')
    parser.add_argument('--threads', type=int, default=4, help='线程数（默认4）')
    parser.add_argument('--opponent', type=str, default='random',
                       choices=['random', 'passive', 'aggressive', 'tight'],
                       help='对手类型')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    parser.add_argument('--verbose', action='store_true', help='详细输出模式')
    parser.add_argument('--debug', action='store_true', help='调试模式（显示详细计算过程）')
    args = parser.parse_args()

    run_test(num_hands=args.hands, num_threads=args.threads, verbose=args.verbose,
            seed=args.seed, opponent_type=args.opponent, debug=args.debug)
    print('测试完成！')
