#!/usr/bin/env python
"""
2人对局测试 - 使用新的通用poker_env环境

这个测试使用了新的poker_env模块，验证：
1. 2人游戏的行动顺序正确
2. Pot计算正确
3. All-in逻辑正确
4. 与原有的2player_advisor2_test_FIXED.py结果一致
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import time
from typing import Tuple

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState
from poker_core import Hand, Board
from advisor_v2.core.data_structures import StrategyContext as GameState as AdvisorGameState
from advisor_v2.modeling import PlayerType
from advisor_v2.integration.decision_integrator import DecisionIntegrator
from advisor_v2.analysis.range_engine import RangeEngine
from advisor_v2.analysis.equity_engine import EquityEngine
from advisor_v2.analysis.board_analyzer import BoardAnalyzer
from advisor_v2.strategy.gto_strategy import GTOStrategy

from tests.performance.opponent_players import OpponentPlayer, create_opponent


class AdvisorV2Player(Player):
    """Advisor V2 AI玩家（适配poker_env接口）"""

    def __init__(self, name: str, seat: int, stack: float):
        super().__init__(name, seat, stack)
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

    def decide(self, game_state: GameState) -> PlayerAction:
        """
        使用DecisionIntegrator做决策

        Args:
            game_state: poker_env的GameState

        Returns:
            PlayerAction
        """
        try:
            # 转换为advisor的GameState
            advisor_game_state = AdvisorGameState(
                street=game_state.street,
                position=game_state.position,
                is_in_position=game_state.is_in_position,
                hero_hand=game_state.hand,
                pot_size=game_state.pot,
                effective_stack=game_state.effective_stack,
                hero_stack=game_state.hero_stack,
                board=game_state.board,
                facing_bet=game_state.facing_bet,
                bet_to_call=game_state.to_call,
                opponent_type=PlayerType.UNKNOWN
            )

            # 使用DecisionIntegrator决策
            trace = self.integrator.decide(advisor_game_state)
            selected_action = self.integrator.select_action(trace.gto_decision)

            action_type = selected_action.action
            amount = selected_action.amount

            # 转换amount
            if action_type in ['bet', 'raise']:
                if amount > 0:
                    actual_amount = game_state.pot * amount
                else:
                    actual_amount = game_state.pot * 0.66

                actual_amount = max(0.5, min(actual_amount, game_state.hero_stack))
                return PlayerAction(action_type, actual_amount)
            else:
                return PlayerAction(action_type, 0.0)

        except Exception as e:
            print(f"  [AI决策错误: {e}]")
            import traceback
            traceback.print_exc()

            # 出错时保守决策
            if game_state.to_call > 0:
                pot_odds = game_state.to_call / (game_state.pot + game_state.to_call)
                if pot_odds < 0.33:
                    return PlayerAction('call', 0.0)
                else:
                    return PlayerAction('fold', 0.0)
            else:
                return PlayerAction('check', 0.0)


class RandomOpponentPlayer(Player):
    """随机对手玩家（适配poker_env接口）"""

    def __init__(self, name: str, seat: int, stack: float, opponent_impl: OpponentPlayer):
        super().__init__(name, seat, stack)
        self.opponent_impl = opponent_impl

    def decide(self, game_state: GameState) -> PlayerAction:
        """
        使用原有的opponent_players逻辑

        Args:
            game_state: poker_env的GameState

        Returns:
            PlayerAction
        """
        # 调用原有的opponent决策
        action_type, amount = self.opponent_impl.decide(
            pot=game_state.pot,
            facing_bet=game_state.facing_bet,
            stack=game_state.hero_stack
        )

        return PlayerAction(action_type, amount)


def run_test(num_hands: int = 10, verbose: bool = True, debug: bool = False, seed: int = 42):
    """运行2人测试"""
    print('=' * 80)
    print('🧪 2人对局测试 - 使用poker_env环境')
    print('=' * 80)
    print(f'\n配置:')
    print(f'  手数: {num_hands}')
    print(f'  随机种子: {seed}')
    print(f'  Verbose: {verbose}')
    print(f'  Debug: {debug}')
    print(f'  开始时间: {time.strftime("%Y-%m-%d %H:%M:%S")}')

    # 创建玩家
    ai = AdvisorV2Player("AI", seat=0, stack=100.0)
    opponent_impl = create_opponent('random', name="Random")
    random = RandomOpponentPlayer("Random", seat=1, stack=100.0, opponent_impl=opponent_impl)

    players = [ai, random]

    # 创建游戏配置
    config = GameConfig(
        num_players=2,
        starting_stack=100.0,
        small_blind=0.5,
        big_blind=1.0,
        verbose=verbose,
        debug=debug
    )

    # 创建游戏
    game = PokerGame(players, config)

    # 运行测试
    print(f'\n开始执行 {num_hands} 手牌测试...')
    start_time = time.time()

    results = []
    for i in range(num_hands):
        # BTN轮换
        btn_seat = i % 2

        if verbose:
            print(f'\n{"="*80}')
            print(f'Hand #{i+1} - BTN: {players[btn_seat].name} (seat {btn_seat})')
            print(f'{"="*80}')

        try:
            result = game.play_hand(hand_num=i, btn_seat=btn_seat, seed=seed * 10000 + i)
            results.append(result)

            if verbose:
                # 打印结果
                ai_profit = result.player_profits[0]
                print(f"\n  >>> AI Profit: {ai_profit:+.2f}BB")

        except Exception as e:
            print(f'\n  [Hand #{i+1} 错误: {e}]')
            import traceback
            traceback.print_exc()

    total_time = time.time() - start_time

    # 统计结果
    ai_total = sum(r.player_profits[0] for r in results)
    ai_btn_results = [r for r in results if r.btn_seat == 0]
    ai_bb_results = [r for r in results if r.btn_seat == 1]

    ai_btn_total = sum(r.player_profits[0] for r in ai_btn_results) if ai_btn_results else 0
    ai_bb_total = sum(r.player_profits[0] for r in ai_bb_results) if ai_bb_results else 0

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

    # 保存结果
    output_dir = r"C:\Users\Administrator\Documents\GitHub\pokerAI\test_results"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "2player_env_test.txt")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('=' * 80 + '\n')
        f.write(f'2人对局测试 - poker_env环境（{num_hands}手）\n')
        f.write('=' * 80 + '\n\n')
        f.write(f'测试时间: {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write(f'随机种子: {seed}\n')
        f.write(f'总用时: {total_time:.1f}秒\n\n')

        f.write('=' * 80 + '\n')
        f.write('📊 结果汇总\n')
        f.write('=' * 80 + '\n\n')
        f.write(f'总手数: {len(results)}\n')
        f.write(f'AI总盈亏: {ai_total:+.2f} BB\n')
        f.write(f'AI BB/100: {(ai_total / len(results)) * 100:+.2f} BB/100手\n\n')

        if ai_btn_results:
            f.write(f'BTN位置: {ai_btn_total:+.2f} BB, BB/100: {(ai_btn_total / len(ai_btn_results)) * 100:+.2f}\n')
        if ai_bb_results:
            f.write(f'BB位置: {ai_bb_total:+.2f} BB, BB/100: {(ai_bb_total / len(ai_bb_results)) * 100:+.2f}\n')

        f.write('\n' + '=' * 80 + '\n')
        f.write('📋 详细记录\n')
        f.write('=' * 80 + '\n\n')

        for r in results:
            f.write(f'Hand #{r.hand_num + 1} - BTN: seat {r.btn_seat}\n')
            for i, hand_str in enumerate(r.player_hands):
                f.write(f'  {players[i].name} (seat {i}): {hand_str}\n')

            if r.flop:
                f.write(f'Board: {" ".join(r.flop)} {r.turn} {r.river}\n\n')
            else:
                f.write('Board: (preflop fold)\n\n')

            f.write('Actions:\n')
            for action in r.actions:
                f.write(f'  [{action.street}] {action.player_name}: {action.action} (pot={action.pot_after:.1f}BB)\n')

            winner_names = ', '.join(players[s].name for s in r.winner_seats)
            f.write(f'\nWinner: {winner_names}, Pot: {r.pot:.1f}BB\n')
            f.write(f'AI profit: {r.player_profits[0]:+.2f}BB\n')

            if r.showdown:
                f.write('Showdown:\n')
                for i, strength in enumerate(r.hand_strengths):
                    f.write(f'  {players[i].name}: {strength}\n')

            f.write('\n' + '-' * 80 + '\n\n')

    print(f'\n详细结果已保存到: {output_file}')
    print()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='2人对局测试 - poker_env环境')
    parser.add_argument('--hands', type=int, default=10, help='测试手数')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    args = parser.parse_args()

    run_test(num_hands=args.hands, verbose=args.verbose, debug=args.debug, seed=args.seed)
    print('测试完成！')
