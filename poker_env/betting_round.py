"""
Betting Round Logic

处理单个街道的betting round逻辑，支持多轮加注
"""
from typing import List, Optional, Tuple
from dataclasses import dataclass

from .player import Player, PlayerAction, GameState
from .utils import (Street, get_action_order, get_position_name, round_amount,
                    ALLIN_THRESHOLD, FLOAT_TOLERANCE, MIN_BET_UNIT, ZERO_THRESHOLD, BIG_BLIND)
from advisor.range_engine import Board


@dataclass
class ActionRecord:
    """单个行动记录"""
    street: str
    player_name: str
    player_seat: int
    action: str
    amount: float
    pot_after: float


class BettingRound:
    """
    Betting Round管理器

    负责执行单个街道的betting round，处理所有玩家的行动
    """

    def __init__(self, verbose: bool = False, debug: bool = False):
        self.verbose = verbose
        self.debug = debug

    def run(
        self,
        street: Street,
        players: List[Player],
        btn_seat: int,
        board: Board,
        pot: float,
        actions: List[ActionRecord]
    ) -> Tuple[Optional[str], float]:
        """
        运行一个完整的betting round

        Args:
            street: 当前街道
            players: 所有玩家列表
            btn_seat: 庄家座位索引
            board: 公共牌
            pot: 当前pot大小
            actions: 行动记录列表（会被修改）

        Returns:
            (winner_name, final_pot)
            winner_name: 如果有人fold，返回获胜者名称；否则返回None
            final_pot: 最终的pot大小
        """
        # 获取行动顺序
        num_players = len(players)
        action_order = get_action_order(num_players, btn_seat, street)

        # 过滤掉已fold或all-in的玩家
        active_players = [p for p in players if p.is_active and not p.is_allin]

        if len(active_players) <= 1:
            # 只有一个玩家active，betting round结束
            return None, pot

        if self.debug:
            print(f"\n  [DEBUG] === Starting {street.value} betting round ===")
            print(f"  [DEBUG] Pot: {pot:.2f}BB")
            for p in players:
                if p.is_active:
                    print(f"  [DEBUG] {p.name} (seat {p.seat}): stack={p.stack:.2f}BB, "
                          f"street_invested={p.street_invested:.2f}BB, allin={p.is_allin}")

        # 行动循环变量
        last_raise_increment = BIG_BLIND  # 初始最小加注增量为1BB
        num_actions = 0
        max_actions = 50  # 防止无限循环
        current_player_idx = 0

        # 找到第一个应该行动的玩家
        for seat in action_order:
            player = players[seat]
            if player.is_active and not player.is_allin:
                current_player_idx = action_order.index(seat)
                break

        while num_actions < max_actions:
            num_actions += 1

            # 检查是否还有玩家需要行动
            active_players = [p for p in players if p.is_active and not p.is_allin]
            if len(active_players) == 0:
                # 所有玩家都all-in了
                return None, pot
            elif len(active_players) == 1:
                # 其他人都fold了
                winner = active_players[0]
                return winner.name, pot

            # 获取当前行动的玩家
            current_seat = action_order[current_player_idx]
            current_player = players[current_seat]

            # 如果当前玩家不active或已all-in，跳到下一个
            if not current_player.is_active or current_player.is_allin:
                current_player_idx = (current_player_idx + 1) % len(action_order)
                continue

            # 计算facing bet和to_call
            max_street_invested = max(p.street_invested for p in players if p.is_active)
            facing_bet = max_street_invested
            to_call = max(0, facing_bet - current_player.street_invested)

            # 检查是否可以结束betting round
            # 条件：所有active玩家的街道投入相等，且至少有一个玩家行动过
            if num_actions > 1 and to_call <= ZERO_THRESHOLD:
                # 检查是否所有active玩家投入相等
                active_invested = [p.street_invested for p in players if p.is_active]
                if len(set(active_invested)) == 1:
                    # 所有人投入相等，结束
                    return None, pot

            # 计算game state
            position_name = get_position_name(current_seat, btn_seat, num_players)
            effective_stack = min(p.stack for p in players if p.is_active)
            min_raise_to = facing_bet + last_raise_increment

            game_state = GameState(
                street=street.value,
                player=current_player,
                position=position_name,
                hand=current_player.hand,
                board=board,
                pot=pot,
                effective_stack=effective_stack,
                hero_stack=current_player.stack,
                facing_bet=facing_bet,
                to_call=to_call,
                min_raise=min_raise_to,
                num_active_players=len([p for p in players if p.is_active]),
                num_allin_players=len([p for p in players if p.is_allin]),
                is_in_position=(current_seat == btn_seat)
            )

            if self.debug:
                print(f"\n  [DEBUG] Action #{num_actions}, {current_player.name} to act")
                print(f"  [DEBUG] Facing bet: {facing_bet:.2f}BB, to_call: {to_call:.2f}BB")
                print(f"  [DEBUG] Stack: {current_player.stack:.2f}BB")

            # 获取玩家决策
            try:
                player_action = current_player.decide(game_state)
            except Exception as e:
                if self.verbose:
                    print(f"  [Error in {current_player.name} decision: {e}]")
                # 出错时默认fold或check
                if to_call > ZERO_THRESHOLD:
                    player_action = PlayerAction('fold', 0.0)
                else:
                    player_action = PlayerAction('check', 0.0)

            action_type = player_action.action
            amount = player_action.amount

            if self.debug:
                print(f"  [DEBUG] Decision: {action_type}, amount: {amount:.2f}BB")

            # Action规范化
            if to_call > ZERO_THRESHOLD and action_type == 'bet':
                action_type = 'raise'
                if self.verbose:
                    print(f"  [Normalized: bet -> raise]")

            if to_call <= ZERO_THRESHOLD and action_type == 'raise':
                action_type = 'bet'
                if self.verbose:
                    print(f"  [Normalized: raise -> bet]")

            # 处理action
            if action_type == 'fold':
                current_player.is_active = False
                actions.append(ActionRecord(
                    street.value, current_player.name, current_seat, 'fold', 0, pot
                ))
                if self.verbose:
                    print(f"  {current_player.name} folds")

                # 检查是否只剩一个玩家
                active_players = [p for p in players if p.is_active]
                if len(active_players) == 1:
                    return active_players[0].name, pot

            elif action_type == 'check':
                # 验证：facing bet时不能check
                if to_call > ZERO_THRESHOLD:
                    # 非法check，强制fold
                    if self.verbose:
                        print(f"  [Invalid check facing bet {to_call:.2f}BB, folding instead]")
                    current_player.is_active = False
                    actions.append(ActionRecord(
                        street.value, current_player.name, current_seat, 'fold', 0, pot
                    ))
                    if self.verbose:
                        print(f"  {current_player.name} folds")

                    # 检查是否只剩一个玩家
                    active_players = [p for p in players if p.is_active]
                    if len(active_players) == 1:
                        return active_players[0].name, pot
                else:
                    # 没有facing bet，合法check
                    actions.append(ActionRecord(
                        street.value, current_player.name, current_seat, 'check', 0, pot
                    ))
                    if self.verbose:
                        print(f"  {current_player.name} checks")

            elif action_type == 'call':
                call_amount = min(to_call, current_player.stack)
                actual_invested = current_player.invest(call_amount)
                pot += actual_invested

                # 如果是all-in call且未完全call对手的bet
                if current_player.is_allin and call_amount < to_call - FLOAT_TOLERANCE:
                    uncalled_bet = to_call - call_amount
                    if self.verbose:
                        print(f"  [All-in call: returning {uncalled_bet:.2f}BB uncalled bet]")

                    # 找到投入最多的玩家，退回uncalled bet
                    for p in players:
                        if p.is_active and p.street_invested == facing_bet:
                            p.return_chips(uncalled_bet)
                            pot -= uncalled_bet
                            break

                action_str = f'call {actual_invested:.2f}BB' + (' (all-in)' if current_player.is_allin else '')
                actions.append(ActionRecord(
                    street.value, current_player.name, current_seat, action_str, actual_invested, pot
                ))
                if self.verbose:
                    print(f"  {current_player.name} calls {actual_invested:.2f}BB" +
                          (' (all-in)' if current_player.is_allin else '') +
                          f", pot={pot:.2f}BB")

                if self.debug:
                    print(f"  [DEBUG] After call: pot={pot:.2f}BB, {current_player.name} stack={current_player.stack:.2f}BB")

                # Call结束当前玩家的行动
                # 但需要继续检查其他玩家

            elif action_type == 'bet':
                bet_amount = min(amount, current_player.stack)
                # 验证：主动bet最小1BB（不包括all-in）
                if bet_amount < MIN_BET_UNIT and current_player.stack > MIN_BET_UNIT:
                    # Bet太小，改为check
                    if self.verbose:
                        print(f"  [Bet too small (<{MIN_BET_UNIT:.1f}BB), checking instead]")
                    actions.append(ActionRecord(
                        street.value, current_player.name, current_seat, 'check', 0, pot
                    ))
                    if self.verbose:
                        print(f"  {current_player.name} checks")
                else:
                    actual_invested = current_player.invest(bet_amount)
                    pot += actual_invested
                    last_raise_increment = actual_invested

                    action_str = f'bet {actual_invested:.2f}BB' + (' (all-in)' if current_player.is_allin else '')
                    actions.append(ActionRecord(
                        street.value, current_player.name, current_seat, action_str, actual_invested, pot
                    ))
                    if self.verbose:
                        print(f"  {current_player.name} bets {actual_invested:.2f}BB" +
                              (' (all-in)' if current_player.is_allin else '') +
                              f", pot={pot:.2f}BB")

                    if self.debug:
                        print(f"  [DEBUG] After bet: pot={pot:.2f}BB")

            elif action_type == 'raise':
                # 计算raise金额
                call_amt = to_call
                if current_player.stack < call_amt:
                    # 筹码不足以call，只能all-in call或fold
                    if current_player.stack > ALLIN_THRESHOLD:
                        actual_invested = current_player.invest(current_player.stack)
                        pot += actual_invested

                        # 退回uncalled bet
                        uncalled_bet = call_amt - actual_invested
                        if uncalled_bet > FLOAT_TOLERANCE:
                            for p in players:
                                if p.is_active and p.street_invested == facing_bet:
                                    p.return_chips(uncalled_bet)
                                    pot -= uncalled_bet
                                    break

                        actions.append(ActionRecord(
                            street.value, current_player.name, current_seat,
                            f'call {actual_invested:.2f}BB (all-in)', actual_invested, pot
                        ))
                        if self.verbose:
                            print(f"  {current_player.name} calls {actual_invested:.2f}BB (all-in), pot={pot:.2f}BB")
                    else:
                        # Fold
                        current_player.is_active = False
                        actions.append(ActionRecord(
                            street.value, current_player.name, current_seat, 'fold', 0, pot
                        ))
                        if self.verbose:
                            print(f"  {current_player.name} folds")
                else:
                    # 正常raise
                    raise_amt = min(amount, current_player.stack - call_amt)
                    raise_to = facing_bet + raise_amt
                    total_invest = call_amt + raise_amt

                    # 检查最小加注
                    if raise_to < min_raise_to - FLOAT_TOLERANCE:
                        # 不满足最小加注
                        if current_player.stack - total_invest <= ALLIN_THRESHOLD:
                            # All-in但不足最小加注，允许（德州扑克规则）
                            if self.verbose:
                                print(f"  [All-in below min raise: {raise_to:.2f}BB < {min_raise_to:.2f}BB, allowing]")

                            actual_invested = current_player.invest(total_invest)
                            pot += actual_invested
                            last_raise_increment = raise_amt

                            actions.append(ActionRecord(
                                street.value, current_player.name, current_seat,
                                f'raise to {raise_to:.2f}BB (all-in)', actual_invested, pot
                            ))
                            if self.verbose:
                                print(f"  {current_player.name} raises to {raise_to:.2f}BB (all-in), pot={pot:.2f}BB")
                        else:
                            # 不是all-in且不满足最小加注，改为call
                            if self.verbose:
                                print(f"  [Raise below minimum, calling instead]")
                            actual_invested = current_player.invest(call_amt)
                            pot += actual_invested

                            actions.append(ActionRecord(
                                street.value, current_player.name, current_seat,
                                f'call {actual_invested:.2f}BB', actual_invested, pot
                            ))
                            if self.verbose:
                                print(f"  {current_player.name} calls {actual_invested:.2f}BB, pot={pot:.2f}BB")
                    else:
                        # 满足最小加注，正常raise
                        actual_invested = current_player.invest(total_invest)
                        pot += actual_invested
                        last_raise_increment = raise_amt

                        action_str = f'raise to {raise_to:.2f}BB' + (' (all-in)' if current_player.is_allin else '')
                        actions.append(ActionRecord(
                            street.value, current_player.name, current_seat, action_str, actual_invested, pot
                        ))
                        if self.verbose:
                            print(f"  {current_player.name} raises to {raise_to:.2f}BB" +
                                  (' (all-in)' if current_player.is_allin else '') +
                                  f", pot={pot:.2f}BB")

                        if self.debug:
                            print(f"  [DEBUG] After raise: pot={pot:.2f}BB")

            # 移到下一个玩家
            current_player_idx = (current_player_idx + 1) % len(action_order)

            # 检查是否所有active玩家都完成了行动
            # 条件：所有active玩家的投入相等
            active_players = [p for p in players if p.is_active and not p.is_allin]
            if len(active_players) > 0:
                active_invested = [p.street_invested for p in active_players]
                if len(set(active_invested)) == 1 and num_actions >= len(active_players):
                    # 所有人投入相等且每人至少行动过一次
                    return None, pot

        # 达到max_actions
        if self.verbose:
            print(f"  [Warning: Reached max actions]")
        return None, pot
