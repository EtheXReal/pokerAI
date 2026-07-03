#!/usr/bin/env python
"""
系统性评估协议 - AI vs 多风格对手

完整管线验证：
  poker_env对局 → StatsTracker累积对手统计 → PlayerClassifier分类
  → GameState.opponent_stats/opponent_type → ExploitEngine调整 → 决策

用法:
  # 单一对手, 1024手
  python tests/performance/evaluation_suite.py --opponent random --hands 1024

  # 全部对手风格 + exploit开/关对比
  python tests/performance/evaluation_suite.py --opponent all --hands 1024 --compare

  # 关闭exploit（纯GTO基线）
  python tests/performance/evaluation_suite.py --opponent tight --no-exploit
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import math
import time
import argparse

from poker_env import PokerGame, GameConfig, Player, PlayerAction, GameState
from poker_env.utils import round_amount
from advisor.core.data_structures import GameState as AdvisorGameState
from advisor.modeling import create_tracker, PlayerClassifier
from advisor.integration.decision_integrator import DecisionIntegrator
from advisor.analysis.range_engine import RangeEngine
from advisor.analysis.equity_engine import EquityEngine
from advisor.analysis.board_analyzer import BoardAnalyzer
from advisor.strategy.gto_strategy import GTOStrategy
from advisor.exploit import ExploitEngine

from tests.performance.opponent_players import OpponentPlayer, create_opponent

OPPONENT_STYLES = ['random', 'passive', 'aggressive', 'tight']


class AdvisorPlayer(Player):
    """AI玩家：完整决策管线（分析 → GTO → exploit），带对手建模"""

    def __init__(self, name: str, seat: int, stack: float, use_exploit: bool = True):
        super().__init__(name, seat, stack)
        self.use_exploit = use_exploit
        self.integrator = DecisionIntegrator(
            range_engine=RangeEngine(),
            equity_engine=EquityEngine(),
            board_analyzer=BoardAnalyzer(),
            strategy=GTOStrategy(),
            exploit_engine=ExploitEngine() if use_exploit else None,
        )
        # 对手建模管线
        self.tracker = create_tracker()
        self.classifier = PlayerClassifier()
        self.villain_id = None  # 由对局循环设置

        # 观测计数
        self.exploit_applied_count = 0
        self.decision_count = 0

    def observe_hand(self, result, players) -> None:
        """
        每手结束后喂给tracker（AI只能看到公开信息：行动序列和摊牌结果）
        """
        positions = {}
        for p in players:
            positions[p.name] = 'BTN' if p.seat == result.btn_seat else 'BB'

        hand_history = {
            'hand_id': f'hand_{result.hand_num}',
            'players': [
                {'id': p.name, 'pos': positions[p.name]}
                for p in players if p.name != self.name
            ],
            'actions': [
                {
                    'street': a.street,
                    'actor': a.player_name,
                    'action': a.action,
                    'amount': a.amount,
                    'position': positions.get(a.player_name, 'UNKNOWN'),
                }
                for a in result.actions
            ],
            'winners': [
                {'seat': players[s].name, 'amount': result.pot}
                for s in result.winner_seats
            ],
            'showdown': result.showdown,
        }
        self.tracker.update_from_hand(hand_history)

    def _get_villain_model(self):
        """获取当前对手的统计和分类"""
        if self.villain_id is None:
            return None, None
        stats = self.tracker.get_stats(self.villain_id)
        if stats.hands_played == 0:
            return None, None
        classification = self.classifier.classify(stats)
        return stats, classification.player_type

    @staticmethod
    def _normalize_action(action_str: str) -> str:
        """poker_env动作串带金额（'bet 7.7BB'/'raise to 4BB'）→ 取动作类型"""
        first = action_str.split()[0].lower() if action_str else ''
        return first if first in ('fold', 'check', 'call', 'bet', 'raise') else 'check'

    def _split_hand_actions(self, hand_actions):
        """把本手动作记录拆成 hero/villain 两条结构化序列"""
        hero_actions, villain_actions = [], []
        for a in hand_actions or []:
            entry = {'street': a.street, 'action': self._normalize_action(a.action)}
            if a.player_name == self.name:
                hero_actions.append(entry)
            else:
                villain_actions.append(entry)
        return hero_actions, villain_actions

    def decide(self, game_state: GameState) -> PlayerAction:
        try:
            opponent_stats, opponent_type = self._get_villain_model()
            hero_actions, villain_actions = self._split_hand_actions(
                getattr(game_state, 'hand_actions', None))

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
                opponent_stats=opponent_stats,
                opponent_type=opponent_type,
                villain_actions=villain_actions,
                hero_actions=hero_actions,
            )

            trace = self.integrator.decide(advisor_game_state)
            selected_action = trace.selected_action  # 从final_decision采样（含exploit）

            self.decision_count += 1
            if trace.exploit_decision is not None:
                self.exploit_applied_count += 1

            action_type = selected_action.action
            amount = selected_action.amount

            if action_type in ['bet', 'raise']:
                if amount > 0:
                    actual_amount = round_amount(game_state.pot * amount)
                else:
                    actual_amount = round_amount(game_state.pot * 0.66)

                if action_type == 'raise':
                    max_raise = game_state.hero_stack - game_state.to_call
                    actual_amount = max(0.5, min(actual_amount, max_raise))
                    if max_raise - actual_amount < 1.0:
                        actual_amount = max_raise
                else:
                    actual_amount = max(0.5, min(actual_amount, game_state.hero_stack))
                    if game_state.hero_stack - actual_amount < 1.0:
                        actual_amount = game_state.hero_stack

                return PlayerAction(action_type, round_amount(actual_amount))
            else:
                return PlayerAction(action_type, 0.0)

        except Exception as e:
            print(f"  [AI决策错误: {e}]")
            import traceback
            traceback.print_exc()
            if game_state.to_call > 0:
                pot_odds = game_state.to_call / (game_state.pot + game_state.to_call)
                return PlayerAction('call' if pot_odds < 0.33 else 'fold', 0.0)
            return PlayerAction('check', 0.0)


class StyledOpponentPlayer(Player):
    """风格化对手（适配poker_env接口）"""

    def __init__(self, name: str, seat: int, stack: float, impl: OpponentPlayer):
        super().__init__(name, seat, stack)
        self.impl = impl

    def decide(self, game_state: GameState) -> PlayerAction:
        action_type, amount = self.impl.decide(
            pot=game_state.pot,
            facing_bet=game_state.facing_bet,
            stack=game_state.hero_stack,
        )
        return PlayerAction(action_type, amount)


def run_match(opponent_style: str, num_hands: int, seed: int,
              use_exploit: bool = True, quiet: bool = False) -> dict:
    """
    跑一场 AI vs 指定风格对手的比赛

    Returns:
        统计字典：bb100/位置分解/标准误/分类结果等
    """
    ai = AdvisorPlayer("AI", seat=0, stack=100.0, use_exploit=use_exploit)
    villain_name = f"{opponent_style.capitalize()}Bot"
    opponent = StyledOpponentPlayer(
        villain_name, seat=1, stack=100.0,
        impl=create_opponent(opponent_style, name=villain_name))
    ai.villain_id = villain_name

    players = [ai, opponent]
    config = GameConfig(num_players=2, starting_stack=100.0,
                        small_blind=0.5, big_blind=1.0,
                        verbose=False, debug=False)
    game = PokerGame(players, config)

    profits = []
    btn_profits = []
    bb_profits = []
    errors = 0

    start = time.time()
    for i in range(num_hands):
        btn_seat = i % 2
        try:
            result = game.play_hand(hand_num=i, btn_seat=btn_seat, seed=seed * 100000 + i)
            profit = result.player_profits[0]
            profits.append(profit)
            (btn_profits if btn_seat == 0 else bb_profits).append(profit)
            # AI观察这手牌，更新对手模型
            ai.observe_hand(result, players)
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f'  [Hand #{i+1} 错误: {e}]')
    elapsed = time.time() - start

    n = len(profits)
    total = sum(profits)
    bb100 = total / n * 100 if n else 0.0
    # 标准误（BB/100口径）
    if n > 1:
        mean = total / n
        var = sum((p - mean) ** 2 for p in profits) / (n - 1)
        stderr_bb100 = math.sqrt(var / n) * 100
    else:
        stderr_bb100 = 0.0

    # 最终对手分类
    stats, ptype = ai._get_villain_model()
    classification = ai.classifier.classify(stats) if stats else None

    report = {
        'opponent': opponent_style,
        'exploit': use_exploit,
        'hands': n,
        'errors': errors,
        'bb100': bb100,
        'stderr_bb100': stderr_bb100,
        'btn_bb100': sum(btn_profits) / len(btn_profits) * 100 if btn_profits else 0.0,
        'bb_bb100': sum(bb_profits) / len(bb_profits) * 100 if bb_profits else 0.0,
        'exploit_rate': ai.exploit_applied_count / ai.decision_count if ai.decision_count else 0.0,
        'villain_classified_as': ptype.value if ptype else 'n/a',
        'classification_confidence': classification.confidence if classification else 0.0,
        'villain_vpip': stats.vpip if stats else 0.0,
        'villain_af': stats.af if stats else 0.0,
        'elapsed_s': elapsed,
    }

    if not quiet:
        _print_report(report)
    return report


def _print_report(r: dict) -> None:
    mode = "GTO+Exploit" if r['exploit'] else "纯GTO"
    print(f"\n--- vs {r['opponent']} ({mode}, {r['hands']}手, {r['elapsed_s']:.0f}s) ---")
    print(f"  BB/100: {r['bb100']:+.1f} ± {r['stderr_bb100']:.1f}")
    print(f"  BTN: {r['btn_bb100']:+.1f} | BB: {r['bb_bb100']:+.1f}")
    print(f"  对手被分类为: {r['villain_classified_as']} "
          f"(置信度 {r['classification_confidence']:.2f}, "
          f"VPIP={r['villain_vpip']:.2f}, AF={r['villain_af']:.1f})")
    print(f"  exploit触发率: {r['exploit_rate']:.1%}")
    if r['errors']:
        print(f"  ⚠️ 错误手数: {r['errors']}")


def main():
    parser = argparse.ArgumentParser(description='系统性评估：AI vs 多风格对手')
    parser.add_argument('--opponent', default='all',
                        choices=OPPONENT_STYLES + ['all'])
    parser.add_argument('--hands', type=int, default=1024)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--no-exploit', action='store_true', help='关闭exploit层（纯GTO）')
    parser.add_argument('--compare', action='store_true',
                        help='每个对手跑exploit开/关两遍并对比')
    args = parser.parse_args()

    styles = OPPONENT_STYLES if args.opponent == 'all' else [args.opponent]

    print('=' * 72)
    print(f'评估协议: {len(styles)}种对手 × {args.hands}手 (seed={args.seed})')
    print('=' * 72)

    all_reports = []
    for style in styles:
        if args.compare:
            r_gto = run_match(style, args.hands, args.seed, use_exploit=False)
            r_exp = run_match(style, args.hands, args.seed, use_exploit=True)
            all_reports.extend([r_gto, r_exp])
            diff = r_exp['bb100'] - r_gto['bb100']
            print(f"  >>> exploit增益: {diff:+.1f} BB/100")
        else:
            all_reports.append(
                run_match(style, args.hands, args.seed,
                          use_exploit=not args.no_exploit))

    # 汇总表
    print('\n' + '=' * 72)
    print('汇总')
    print('=' * 72)
    print(f"{'对手':<12} {'模式':<12} {'BB/100':>10} {'±SE':>8} {'BTN':>8} {'BB':>8} {'分类':<16}")
    for r in all_reports:
        mode = 'exploit' if r['exploit'] else 'gto'
        print(f"{r['opponent']:<12} {mode:<12} {r['bb100']:>+10.1f} {r['stderr_bb100']:>8.1f} "
              f"{r['btn_bb100']:>+8.1f} {r['bb_bb100']:>+8.1f} {r['villain_classified_as']:<16}")

    return all_reports


if __name__ == '__main__':
    main()
