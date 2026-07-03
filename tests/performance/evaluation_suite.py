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

OPPONENT_STYLES = ['random', 'passive', 'aggressive', 'tight', 'tag']


class TagPlayer(Player):
    """
    会看牌的TAG规则对手（紧凶型）

    与random系bot不同，这个对手根据真实牌力决策：
    - 翻前：按牌力表开池/3bet/跟注，无limp
    - 翻后：顶对+价值下注，听牌按赔率跟注，空气弃牌
    比不看牌的随机bot强得多，作为有意义的基准陪练。
    """

    def __init__(self, name: str, seat: int, stack: float):
        super().__init__(name, seat, stack)
        import random as _random
        self._rng = _random.Random(name)  # 独立随机流，不干扰全局seed
        # 复用RangeEngine的169手强度表
        from advisor.analysis.range_engine import RangeEngine
        self._range_engine = RangeEngine()

    def _preflop_strength(self, hand) -> float:
        return self._range_engine._get_preflop_hand_strength(hand)

    def _postflop_category(self, hand, board) -> str:
        """'strong' / 'medium' / 'draw' / 'weak'"""
        from poker_core.evaluator import HandEvaluator, HandRank
        from advisor.analysis.range_engine import RangeEngine

        cards = list(hand.cards) + list(board)
        if len(cards) == 5:
            strength = HandEvaluator.evaluate(cards)
        elif len(cards) == 7:
            strength = HandEvaluator.evaluate_best_5(cards)
        else:  # turn: 6张取最优5张
            from itertools import combinations
            strength = max((HandEvaluator.evaluate(list(c)) for c in combinations(cards, 5)),
                           key=lambda s: s.to_score())

        board_top = max(int(c.rank) for c in board)
        if strength.rank >= HandRank.TWO_PAIR:
            return 'strong'
        if strength.rank == HandRank.ONE_PAIR and strength.primary and strength.primary[0] >= board_top:
            return 'strong'   # 顶对或超对
        if RangeEngine._has_strong_draw(hand, list(board)):
            return 'draw'
        if strength.rank == HandRank.ONE_PAIR:
            return 'medium'
        return 'weak'

    def decide(self, game_state: GameState) -> PlayerAction:
        pot = game_state.pot
        to_call = game_state.to_call
        stack = game_state.hero_stack
        r = self._rng.random()

        if game_state.street == 'preflop':
            s = self._preflop_strength(game_state.hand)
            if to_call <= 0.01:
                # BB无人加注：强牌加注，其余check
                if s >= 0.70:
                    return PlayerAction('raise', min(3.0, stack))
                return PlayerAction('check', 0.0)
            if to_call <= 0.75:
                # BTN开池位（补0.5BB）：raise-or-fold
                if s >= 0.48:
                    return PlayerAction('raise', min(2.0, stack))
                return PlayerAction('fold', 0.0)
            # 面对raise/3bet
            if s >= 0.85:
                return PlayerAction('raise', min(to_call * 2.5, stack - to_call))
            call_threshold = 0.55 if to_call <= 3.0 else 0.72
            if s >= call_threshold and to_call < stack * 0.35:
                return PlayerAction('call', 0.0)
            return PlayerAction('fold', 0.0)

        # ---------- 翻后 ----------
        category = self._postflop_category(game_state.hand, game_state.board)

        if to_call <= 0.01:
            # 无人下注
            if category == 'strong':
                return PlayerAction('bet', min(round_amount(pot * 0.66), stack))
            if category == 'medium' and r < 0.5:
                return PlayerAction('bet', min(round_amount(pot * 0.5), stack))
            if category == 'draw' and r < 0.4:
                return PlayerAction('bet', min(round_amount(pot * 0.5), stack))  # 半bluff
            if category == 'weak' and r < 0.10:
                return PlayerAction('bet', min(round_amount(pot * 0.5), stack))  # 少量bluff
            return PlayerAction('check', 0.0)

        # 面对下注
        pot_odds = to_call / (pot + to_call) if (pot + to_call) > 0 else 1.0
        if category == 'strong':
            if r < 0.35:
                return PlayerAction('raise', min(round_amount(to_call * 2.5), stack - to_call))
            return PlayerAction('call', 0.0)
        if category == 'draw':
            # 按赔率跟注（花听/两头顺听约35%胜率）
            if pot_odds < 0.32 and to_call < stack * 0.4:
                return PlayerAction('call', 0.0)
            return PlayerAction('fold', 0.0)
        if category == 'medium':
            if pot_odds < 0.30:
                return PlayerAction('call', 0.0)
            return PlayerAction('fold', 0.0)
        return PlayerAction('fold', 0.0)


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
    def _convert_sizing(game_state: GameState, action_type: str, amount: float) -> float:
        """
        把策略输出的sizing转换为poker_env的金额语义

        poker_env: bet的amount是下注总额；raise的amount是超出call部分的增量。
        标准sizing：翻前开池2.5BB、3bet/4bet≈3×对手注；翻后bet按pot比例、raise≈2.75×对手注。
        """
        stack = game_state.hero_stack
        pot = game_state.pot
        facing = game_state.facing_bet or 0.0
        to_call = game_state.to_call or 0.0

        if action_type == 'raise':
            if game_state.street == 'preflop' and facing <= 1.01:
                # 开池：raise-to ≈ 2.5BB → 增量2.0（在SB补0.5后）
                actual = 2.0
            elif game_state.street == 'preflop':
                # 3bet/4bet: raise-to ≈ 3×对手加注 → 增量 = 2×facing
                actual = 2.0 * facing
            else:
                # 翻后raise: raise-to ≈ 2.75×对手下注 → 增量 = 1.75×facing
                actual = 1.75 * facing

            max_raise = stack - to_call
            actual = max(0.5, min(actual, max_raise))
            if max_raise - actual < 1.0:  # 接近all-in直接推
                actual = max_raise
            return round_amount(actual)

        # bet: amount是pot比例（策略sizing分布），默认0.66 pot
        fraction = amount if 0 < amount <= 2.0 else 0.66
        actual = max(0.5, min(pot * fraction, stack))
        if stack - actual < 1.0:
            actual = stack
        return round_amount(actual)

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
                actual_amount = self._convert_sizing(game_state, action_type, amount)
                return PlayerAction(action_type, actual_amount)
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


def _make_opponent(opponent_style: str, name: str, seat: int) -> Player:
    if opponent_style == 'tag':
        return TagPlayer(name, seat=seat, stack=100.0)
    return StyledOpponentPlayer(
        name, seat=seat, stack=100.0,
        impl=create_opponent(opponent_style, name=name))


def run_match(opponent_style: str, num_hands: int, seed: int,
              use_exploit: bool = True, quiet: bool = False,
              duplicate: bool = False) -> dict:
    """
    跑一场 AI vs 指定风格对手的比赛

    duplicate=True 时启用对拆方差缩减：每手牌用同一seed跑两场（AI换边），
    发牌运气在配对求和中抵消，只留下决策质量差异。

    Returns:
        统计字典：bb100/位置分解/标准误/分类结果等
    """
    villain_name = f"{opponent_style.capitalize()}Bot"
    config = GameConfig(num_players=2, starting_stack=100.0,
                        small_blind=0.5, big_blind=1.0,
                        verbose=False, debug=False)

    # 游戏1: AI在seat0
    ai = AdvisorPlayer("AI", seat=0, stack=100.0, use_exploit=use_exploit)
    ai.villain_id = villain_name
    players1 = [ai, _make_opponent(opponent_style, villain_name, seat=1)]
    game1 = PokerGame(players1, config)

    # 游戏2（duplicate）: AI在seat1，同seed拿到对面的牌
    if duplicate:
        ai2 = AdvisorPlayer("AI", seat=1, stack=100.0, use_exploit=use_exploit)
        ai2.villain_id = villain_name
        players2 = [_make_opponent(opponent_style, villain_name, seat=0), ai2]
        game2 = PokerGame(players2, config)

    profits = []       # 每手（或每配对）AI盈亏
    btn_profits = []
    bb_profits = []
    errors = 0

    start = time.time()
    for i in range(num_hands):
        btn_seat = i % 2
        hand_seed = seed * 100000 + i
        try:
            r1 = game1.play_hand(hand_num=i, btn_seat=btn_seat, seed=hand_seed)
            p1 = r1.player_profits[0]
            ai.observe_hand(r1, players1)

            if duplicate:
                r2 = game2.play_hand(hand_num=i, btn_seat=btn_seat, seed=hand_seed)
                p2 = r2.player_profits[1]
                ai2.observe_hand(r2, players2)
                # 配对求和：同一副牌AI两边各打一次
                profits.append(p1 + p2)
                (btn_profits if btn_seat == 0 else bb_profits).append(p1)
                (bb_profits if btn_seat == 0 else btn_profits).append(p2)
            else:
                profits.append(p1)
                (btn_profits if btn_seat == 0 else bb_profits).append(p1)
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f'  [Hand #{i+1} 错误: {e}]')
    elapsed = time.time() - start

    n = len(profits)
    total = sum(profits)
    hands_played = n * (2 if duplicate else 1)
    bb100 = total / hands_played * 100 if n else 0.0
    # 标准误（BB/100口径；duplicate下按配对样本计算，再折算到单手口径）
    if n > 1:
        mean = total / n
        var = sum((p - mean) ** 2 for p in profits) / (n - 1)
        stderr_bb100 = math.sqrt(var / n) * 100 / (2 if duplicate else 1)
    else:
        stderr_bb100 = 0.0

    # 最终对手分类
    stats, ptype = ai._get_villain_model()
    classification = ai.classifier.classify(stats) if stats else None

    report = {
        'opponent': opponent_style,
        'exploit': use_exploit,
        'hands': hands_played,
        'duplicate': duplicate,
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
    parser.add_argument('--duplicate', action='store_true',
                        help='对拆方差缩减：每手同一副牌AI两边各打一次')
    args = parser.parse_args()

    styles = OPPONENT_STYLES if args.opponent == 'all' else [args.opponent]

    print('=' * 72)
    print(f'评估协议: {len(styles)}种对手 × {args.hands}手 (seed={args.seed})')
    print('=' * 72)

    all_reports = []
    for style in styles:
        if args.compare:
            r_gto = run_match(style, args.hands, args.seed, use_exploit=False,
                              duplicate=args.duplicate)
            r_exp = run_match(style, args.hands, args.seed, use_exploit=True,
                              duplicate=args.duplicate)
            all_reports.extend([r_gto, r_exp])
            diff = r_exp['bb100'] - r_gto['bb100']
            print(f"  >>> exploit增益: {diff:+.1f} BB/100")
        else:
            all_reports.append(
                run_match(style, args.hands, args.seed,
                          use_exploit=not args.no_exploit,
                          duplicate=args.duplicate))

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
