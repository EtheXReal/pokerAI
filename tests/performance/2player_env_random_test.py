#!/usr/bin/env python
"""
2人对局测试 - 使用poker_env + RandomPlayer对手

这个测试验证：
1. poker_env环境能正确支持2人游戏
2. 与2player_advisor2_test_FIXED.py行为一致
3. Pot计算、all-in逻辑、行动顺序都正确
4. 使用opponent_players.py中的RandomPlayer作为对手
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import time
from typing import Tuple

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState
from poker_env.utils import round_amount
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

    def __init__(self, name: str, seat: int, stack: float, enable_trace: bool = False):
        super().__init__(name, seat, stack)
        # 初始化advisor_v2组件
        self.range_engine = RangeEngine()
        self.equity_engine = EquityEngine()
        self.board_analyzer = BoardAnalyzer()
        self.gto_strategy = GTOStrategy()

        # 决策追踪器
        from advisor_v2.debug.decision_tracer import DecisionTracer
        self.tracer = DecisionTracer(enabled=enable_trace)
        self.hand_num = 0

        self.integrator = DecisionIntegrator(
            range_engine=self.range_engine,
            equity_engine=self.equity_engine,
            board_analyzer=self.board_analyzer,
            strategy=self.gto_strategy,
            tracer=self.tracer
        )

    def decide(self, game_state: GameState) -> PlayerAction:
        """
        使用DecisionIntegrator做决策（带追踪）

        Args:
            game_state: poker_env的GameState

        Returns:
            PlayerAction
        """
        try:
            # 转换为advisor的GameState
            step_start = time.time()
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
            step_time = (time.time() - step_start) * 1000

            # 开始追踪
            trace_log = self.tracer.start_trace(self.hand_num, advisor_game_state)

            # Trace: GameState转换
            if self.tracer.is_enabled():
                self.tracer.trace_step(
                    step_name="GameState转换",
                    module="tests/performance/2player_env_random_test.py",
                    function="AdvisorV2Player.decide",
                    inputs={"poker_env_state": f"street={game_state.street}, pot={game_state.pot:.1f}BB"},
                    outputs={"advisor_state": f"street={advisor_game_state.street}, pot={advisor_game_state.pot_size:.1f}BB"},
                    duration_ms=step_time,
                    reasoning="将poker_env的GameState转换为advisor格式"
                )

            # 使用DecisionIntegrator决策（内部会自动追踪）
            trace = self.integrator.decide(advisor_game_state)
            selected_action = self.integrator.select_action(trace.gto_decision)

            action_type = selected_action.action
            amount = selected_action.amount

            # 转换amount
            if action_type in ['bet', 'raise']:
                # Trace: 金额计算
                step_start = time.time()

                if amount > 0:
                    actual_amount = round_amount(game_state.pot * amount)
                else:
                    actual_amount = round_amount(game_state.pot * 0.66)

                # 限制在合法范围
                if action_type == 'raise':
                    # raise是增量，需要扣除to_call
                    max_raise = game_state.hero_stack - game_state.to_call
                    actual_amount = max(0.5, min(actual_amount, max_raise))

                    # 如果接近all-in（剩余筹码 < 1BB），直接all-in
                    if max_raise - actual_amount < 1.0:
                        actual_amount = max_raise
                else:
                    # bet是总金额
                    actual_amount = max(0.5, min(actual_amount, game_state.hero_stack))

                    # 如果接近all-in（剩余筹码 < 1BB），直接all-in
                    if game_state.hero_stack - actual_amount < 1.0:
                        actual_amount = game_state.hero_stack

                actual_amount = round_amount(actual_amount)

                step_time = (time.time() - step_start) * 1000

                if self.tracer.is_enabled():
                    self.tracer.trace_step(
                        step_name="金额计算",
                        module="tests/performance/2player_env_random_test.py",
                        function="AdvisorV2Player.decide",
                        inputs={
                            "pot_multiplier": amount,
                            "pot": game_state.pot,
                            "hero_stack": game_state.hero_stack
                        },
                        outputs={"actual_amount": actual_amount},
                        duration_ms=step_time,
                        reasoning=f"将pot的{amount:.1%}转换为实际金额{actual_amount:.1f}BB，并限制在合法范围"
                    )

                final_action = PlayerAction(action_type, actual_amount)
            else:
                step_start = time.time()
                step_time = (time.time() - step_start) * 1000

                if self.tracer.is_enabled():
                    self.tracer.trace_step(
                        step_name="非下注动作",
                        module="tests/performance/2player_env_random_test.py",
                        function="AdvisorV2Player.decide",
                        inputs={"action": action_type},
                        outputs={"amount": 0.0},
                        duration_ms=step_time,
                        reasoning=f"{action_type}动作不需要金额"
                    )
                final_action = PlayerAction(action_type, 0.0)

            # 完成追踪
            self.tracer.finish_trace(final_action.action, final_action.amount)

            # 输出追踪日志
            if self.tracer.is_enabled() and trace_log:
                print("\n" + trace_log.format_full(verbose=True))

                # 保存追踪日志到文件
                try:
                    txt_path = trace_log.save_to_file()
                    print(f"\n💾 追踪日志已保存: {txt_path}")
                except Exception as e:
                    print(f"\n⚠️  保存追踪日志失败: {e}")

                # 导出 Graphviz
                try:
                    dot_path = trace_log.export_to_graphviz()
                    print(f"📊 Graphviz已导出: {dot_path}")
                    print(f"   生成图片: dot -Tpng {dot_path} -o {dot_path.replace('.dot', '.png')}")
                except Exception as e:
                    print(f"⚠️  导出Graphviz失败: {e}")

            return final_action

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
        使用opponent_players.RandomPlayer逻辑

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


def run_test(num_hands: int = 16, verbose: bool = True, debug: bool = False, trace: bool = False, seed: int = 42):
    """运行2人RandomPlayer测试"""
    print('=' * 80)
    print('🎮 2人对局测试 - poker_env + RandomPlayer')
    print('=' * 80)
    print(f'\n配置:')
    print(f'  手数: {num_hands}')
    print(f'  随机种子: {seed}')
    print(f'  对手类型: RandomPlayer (fold=0.4, raise_facing=0.2, bet=0.33)')
    print(f'  Verbose: {verbose}')
    print(f'  Debug: {debug}')
    print(f'  AI决策追踪: {trace}')
    print(f'  开始时间: {time.strftime("%Y-%m-%d %H:%M:%S")}')

    # 创建玩家（启用追踪）
    ai = AdvisorV2Player("AI", seat=0, stack=100.0, enable_trace=trace)
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
        # 设置AI的hand_num（用于追踪）
        ai.hand_num = i

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
    output_dir = os.path.join(os.path.dirname(__file__), "../../test_results")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "2player_env_random_test.txt")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('=' * 80 + '\n')
        f.write(f'2人对局测试 - poker_env + RandomPlayer ({num_hands}手)\n')
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

    print(f'\n✅ 详细结果已保存到: {output_file}')
    print()

    return results


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='2人对局测试 - poker_env + RandomPlayer')
    parser.add_argument('--hands', type=int, default=16, help='测试手数 (默认16)')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    parser.add_argument('--trace', action='store_true', help='启用AI决策追踪')
    args = parser.parse_args()

    run_test(
        num_hands=args.hands,
        verbose=args.verbose,
        debug=args.debug,
        trace=args.trace,
        seed=args.seed
    )
    print('✅ 测试完成！')
