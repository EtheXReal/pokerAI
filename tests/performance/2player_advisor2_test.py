#!/usr/bin/env python
"""
2人对局advisor_v2测试 - 真正的德州扑克

完整的preflop/flop/turn/river决策流程，支持多轮加注

特性：
- 完整的4个街道决策（真扑克，不是假扑克）
- 支持多轮加注（bet → raise → 3-bet → 4-bet...）
- 可插拔的对手系统（random/passive/aggressive/tight）
- advisor_v2架构（DecisionIntegrator + RangeEngine + EquityEngine + BoardAnalyzer + GTOStrategy）

与旧测试的区别：
- 旧测试：只有翻前决策，然后直接showdown（假扑克）
- 本测试：完整的4个街道决策（真扑克）

为什么advisor_v2需要真扑克测试：
- EquityEngine需要board来计算equity
- BoardAnalyzer需要board来分析texture
- Range advantage分析需要翻后的equity分布
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import random
import time
from dataclasses import dataclass
from typing import List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from poker_core import Hand, Board, create_deck, Card
from poker_core.evaluator import HandEvaluator
from advisor_v2.core.data_structures import StrategyContext as GameState
from advisor_v2.modeling import PlayerType
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
    # Preflop: 包括盲注；其他街道：从0开始
    if street == 'preflop':
        street_ai_invested = ai_invested
        street_random_invested = random_invested
    else:
        street_ai_invested = 0
        street_random_invested = 0

    # 行动循环
    last_aggressor = None  # 最后一个下注/加注的人
    last_raise_increment = 1.0  # 最小加注增量，初始为1BB（大盲注）
    num_actions = 0
    max_actions = 20  # 防止无限循环

    while num_actions < max_actions:
        num_actions += 1

        # === 检查是否双方都all-in且金额相等 ===
        # All-in阈值：1BB（最小有意义的下注单位）
        ALLIN_THRESHOLD = 1.0

        if ai_stack <= ALLIN_THRESHOLD and random_stack <= ALLIN_THRESHOLD:
            # 双方都all-in，结束betting
            if verbose:
                print(f"  [Both players all-in, ending betting round]")
            return (None, pot, ai_stack, random_stack, ai_invested, random_invested)

        if street_ai_invested > 0 and street_random_invested > 0 and abs(street_ai_invested - street_random_invested) < 0.01:
            # 双方投入相等且都有投入，检查是否都all-in
            if ai_stack <= ALLIN_THRESHOLD or random_stack <= ALLIN_THRESHOLD:
                if verbose:
                    print(f"  [One player all-in and called, ending betting round]")
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

        # 获取当前玩家的stack
        current_stack = ai_stack if current_player == 'AI' else random_stack

        # === 检查玩家是否还有筹码可以行动 ===
        if current_stack <= ALLIN_THRESHOLD:
            # 玩家筹码不足1BB，视为all-in，只能check或fold
            # 计算是否需要call
            if current_player == 'AI':
                to_call = max(0, street_random_invested - street_ai_invested)
            else:
                to_call = max(0, street_ai_invested - street_random_invested)

            if to_call <= 0.01:
                # 可以免费check
                actions.append(StreetAction(street, current_player, 'check (all-in)', 0, pot))
                if verbose:
                    print(f"  {current_player} checks (all-in, {current_stack:.1f}BB left)")
                # 检查是否双方都check
                if len(actions) >= 2 and actions[-2].action.startswith('check') and actions[-2].street == street:
                    return (None, pot, ai_stack, random_stack, ai_invested, random_invested)
                continue
            else:
                # 面对下注但筹码不足1BB，只能fold
                actions.append(StreetAction(street, current_player, 'fold (insufficient chips)', 0, pot))
                if verbose:
                    print(f"  {current_player} folds (only {current_stack:.1f}BB left, cannot call {to_call:.1f}BB)")
                winner = 'Random' if current_player == 'AI' else 'AI'
                return (winner, pot, ai_stack, random_stack, ai_invested, random_invested)

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
            action_type, amount = opponent_player.decide(pot, facing_bet, random_stack)

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
            # 面对下注不能check，强制fold
            if verbose:
                print(f"  [Invalid: check when facing {to_call:.1f}BB, forcing fold]")
            action_type = 'fold'

        if action_type == 'fold' and to_call <= 0.01:
            # 不面对下注不应该fold，改为check
            if verbose:
                print(f"  [Invalid: fold when can check free, forcing check]")
            action_type = 'check'

        if action_type == 'bet' and to_call > 0.01:
            # 面对下注只能fold/call/raise
            if verbose:
                print(f"  [Invalid: bet when facing {to_call:.1f}BB, forcing raise]")
            action_type = 'raise'

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

            # 如果是第一个行动的人check，继续
            continue

        elif action_type == 'call':
            # 计算实际call金额（不能超过stack）
            call_amount = min(to_call, current_stack)
            # All-in判断：call后剩余筹码<=1BB
            is_allin = (current_stack - call_amount <= ALLIN_THRESHOLD)

            if call_amount <= 0.01 and not is_allin:
                # 实际上是check（没有需要call的，且不是all-in）
                actions.append(StreetAction(street, current_player, 'check', 0, pot))
                if verbose:
                    print(f"  {current_player} checks (call 0)")
                # 检查是否双方都check
                if len(actions) >= 2 and actions[-2].action.startswith('check') and actions[-2].street == street:
                    return (None, pot, ai_stack, random_stack, ai_invested, random_invested)
                continue

            # 执行call（可能是all-in call）
            if current_player == 'AI':
                ai_invested += call_amount
                ai_stack -= call_amount
                street_ai_invested += call_amount
            else:
                random_invested += call_amount
                random_stack -= call_amount
                street_random_invested += call_amount

            pot += call_amount

            # 如果是all-in call且未完全call对手的bet，需要退回对手多余的筹码（边池逻辑）
            if is_allin and call_amount < to_call - 0.01:
                uncalled_bet = to_call - call_amount
                if verbose:
                    print(f"  [All-in call: returning {uncalled_bet:.1f}BB uncalled bet to opponent]")

                # 退回给对手
                if current_player == 'AI':
                    # AI all-in call，Random有未被call的部分
                    random_stack += uncalled_bet
                    random_invested -= uncalled_bet
                    street_random_invested -= uncalled_bet
                    pot -= uncalled_bet
                else:
                    # Random all-in call，AI有未被call的部分
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

            # Call结束这个betting round
            return (None, pot, ai_stack, random_stack, ai_invested, random_invested)

        elif action_type == 'bet':
            # Bet只在不面对下注时有效
            bet_amount = min(amount, current_stack)
            # All-in判断：bet后剩余筹码<=1BB
            is_allin = (current_stack - bet_amount <= ALLIN_THRESHOLD)

            # 防止0BB或过小的bet（除非是all-in）
            if bet_amount < 0.5 and not is_allin:
                # 筹码不足以bet，改为check
                if verbose:
                    print(f"  [Bet amount too small ({bet_amount:.2f}BB), checking instead]")
                actions.append(StreetAction(street, current_player, 'check', 0, pot))
                if verbose:
                    print(f"  {current_player} checks")
                # 检查是否双方都check
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

            # 更新最小加注增量（下次raise必须至少加注这么多）
            last_raise_increment = bet_amount

            # 记录action
            if is_allin:
                actions.append(StreetAction(street, current_player, f'bet {bet_amount:.1f}BB (all-in)', bet_amount, pot))
                if verbose:
                    print(f"  {current_player} bets {bet_amount:.1f}BB (all-in), pot={pot:.1f}BB")
            else:
                actions.append(StreetAction(street, current_player, f'bet {bet_amount:.1f}BB', bet_amount, pot))
                if verbose:
                    print(f"  {current_player} bets {bet_amount:.1f}BB, pot={pot:.1f}BB")

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
                    # 转为all-in call
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

            # 计算raise的增量（限制在剩余stack范围内）
            raise_amt = min(amount, current_stack - call_amt)
            raise_to = facing_bet + raise_amt

            # All-in判断：raise后剩余筹码<=1BB
            is_allin = (current_stack - call_amt - raise_amt <= ALLIN_THRESHOLD)

            # 计算最小加注金额（德州扑克规则：必须至少加注前一次的增量）
            min_raise_to = facing_bet + last_raise_increment

            # 检查是否满足最小加注规则
            if raise_to < min_raise_to - 0.01:
                # 不满足最小加注
                if is_allin:
                    # All-in特例：筹码不足以完成最小加注，但可以all-in
                    # 德州扑克规则：all-in金额不足最小加注时，视为all-in call，不重新开启加注轮
                    if verbose:
                        print(f"  [All-in below min raise: {raise_to:.1f}BB < {min_raise_to:.1f}BB, treating as all-in call]")
                    # 转为all-in call
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
                    if uncalled_bet > 0.01:
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

            # 如果raise_amt过小（除非是all-in），转为call
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

            # 更新最小加注增量（下次raise必须至少加注这么多）
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

            last_aggressor = current_player
            continue

    # 如果达到max_actions，结束（防御性代码）
    if verbose:
        print(f"  [Warning: Reached max actions in betting round]")
    return (None, pot, ai_stack, random_stack, ai_invested, random_invested)


def play_full_hand(hand_num: int, ai_player: AdvisorV2Player, opponent_player: OpponentPlayer,
                   ai_position: str, starting_stack: float = 100.0, verbose: bool = True,
                   base_seed: int = 42) -> FullHandRecord:
    """
    玩一手完整的牌（包含翻前+flop+turn+river，支持多轮加注）

    Args:
        hand_num: 手牌编号
        ai_player: AI玩家
        opponent_player: 对手玩家（可插拔）
        ai_position: AI位置 ('BTN' or 'BB')
        starting_stack: 起始筹码
        verbose: 是否打印详细信息

    Returns:
        FullHandRecord
    """
    sb = 0.5
    bb = 1.0

    # 设置随机种子（固定种子确保可重现）
    random.seed(base_seed * 10000 + hand_num)

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


def run_test(num_hands: int = 32, num_threads: int = 4, verbose: bool = False, seed: int = 42,
             opponent_type: str = 'random'):
    """运行完整测试"""
    print('=' * 80)
    print(f'🤖 advisor_v2 vs {opponent_type.title()} - 完整翻后测试（真扑克 + 多轮加注）')
    print('=' * 80)
    print(f'\n配置:')
    print(f'  手数: {num_hands}')
    print(f'  线程数: {num_threads}')
    print(f'  对手类型: {opponent_type}')
    print(f'  随机种子: {seed}')
    print(f'  包含: 翻前 + Flop + Turn + River 完整决策')
    print(f'  支持: 多轮加注（bet → raise → 3-bet → 4-bet...）')
    print(f'  架构: DecisionIntegrator (RangeEngine + EquityEngine + BoardAnalyzer + GTOStrategy)')
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
            result = play_full_hand(i, ai, opponent, ai_position, verbose=verbose, base_seed=seed)
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
    output_dir = r"C:\Users\Administrator\Documents\GitHub\pokerAI\test_results"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{opponent_type}1024test.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('=' * 80 + '\n')
        f.write(f'advisor_v2 vs Random - 完整翻后测试结果（{num_hands}手）\n')
        f.write('=' * 80 + '\n\n')
        f.write(f'测试时间: {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write(f'随机种子: {seed}\n')
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
    parser = argparse.ArgumentParser(description='advisor_v2完整翻后测试 - 可插拔对手')
    parser.add_argument('--hands', type=int, default=32, help='测试手数（默认32）')
    parser.add_argument('--threads', type=int, default=4, help='线程数（默认4）')
    parser.add_argument('--opponent', type=str, default='random',
                       choices=['random', 'passive', 'aggressive', 'tight'],
                       help='对手类型：random(随机), passive(被动), aggressive(激进), tight(紧凶)，默认random')
    parser.add_argument('--seed', type=int, default=42, help='随机种子（默认42，用于重现结果。注意：多线程时结果可能略有不同，使用--threads 1确保完全可重现）')
    parser.add_argument('--verbose', action='store_true', help='详细输出模式')
    args = parser.parse_args()

    run_test(num_hands=args.hands, num_threads=args.threads, verbose=args.verbose,
            seed=args.seed, opponent_type=args.opponent)
    print('测试完成！')
