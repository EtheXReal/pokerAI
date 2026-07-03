"""
AdvisorEnvPlayer - advisor决策系统的poker_env适配器

把完整决策管线（分析 → GTO → exploit + 对手建模）包装成poker_env的Player，
供对战模拟、评估协议和人机对战界面共用。
"""

from typing import Optional

from poker_env import Player, PlayerAction, GameState
from poker_env.utils import round_amount

from advisor.core.data_structures import GameState as AdvisorGameState
from advisor.modeling import create_tracker, PlayerClassifier
from advisor.integration.decision_integrator import DecisionIntegrator
from advisor.analysis.range_engine import RangeEngine
from advisor.analysis.equity_engine import EquityEngine
from advisor.analysis.board_analyzer import BoardAnalyzer
from advisor.strategy.gto_strategy import GTOStrategy
from advisor.exploit import ExploitEngine


class AdvisorEnvPlayer(Player):
    """AI玩家：完整决策管线（分析 → GTO → exploit），带对手建模"""

    def __init__(self, name: str, seat: int, stack: float, use_exploit: bool = True,
                 keep_traces: bool = False):
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
        self.villain_id: Optional[str] = None  # 由对局循环设置

        # 观测计数
        self.exploit_applied_count = 0
        self.decision_count = 0

        # DecisionTrace留存（人机界面复盘用；对战模拟默认关闭省内存）
        self.keep_traces = keep_traces
        self.hand_traces = []  # 当前手牌的traces

    def start_hand(self) -> None:
        """新一手开始时清空trace缓存"""
        self.hand_traces = []

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

    def get_villain_model(self):
        """获取当前对手的统计和分类 (stats, player_type)"""
        if self.villain_id is None:
            return None, None
        stats = self.tracker.get_stats(self.villain_id)
        if stats.hands_played == 0:
            return None, None
        classification = self.classifier.classify(stats)
        return stats, classification.player_type

    # 向后兼容的私有别名
    _get_villain_model = get_villain_model

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
            opponent_stats, opponent_type = self.get_villain_model()
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
            if self.keep_traces:
                self.hand_traces.append(trace)

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
