"""
DecisionIntegrator实现

Orchestrate所有模块生成完整决策，确保模块不被架空。
"""

import time
import uuid
import random
from typing import Optional, List

from advisor.core.interfaces.integration_interface import IDecisionIntegrator
from advisor.core.interfaces.analysis_interface import (
    IRangeEngine,
    IEquityEngine,
    IBoardAnalyzer
)
from advisor.core.interfaces.strategy_interface import IStrategy
from advisor.core.data_structures import (
    DecisionTrace,
    StrategyContext,
    StrategyDecision,
    Action,
    EquityInfo,
    RangeAdvantage,
    BoardAnalysis,
)
from poker_core.cards import Hand, Card
from poker_core.range import Range
from poker_core.position import Position


class DecisionIntegrator(IDecisionIntegrator):
    """
    决策集成器实现

    职责：
    1. Orchestrate所有Analysis和Strategy模块
    2. 生成完整的DecisionTrace
    3. 验证模块使用（确保不被架空）
    """

    def __init__(
        self,
        range_engine: IRangeEngine,
        equity_engine: Optional[IEquityEngine] = None,
        board_analyzer: Optional[IBoardAnalyzer] = None,
        strategy: Optional[IStrategy] = None,
        exploit_engine: Optional['IExploitEngine'] = None
    ):
        """
        初始化DecisionIntegrator

        Args:
            range_engine: RangeEngine（必需）
            equity_engine: EquityEngine（翻后需要）
            board_analyzer: BoardAnalyzer（翻后需要）
            strategy: Strategy（默认GTOStrategy）
            exploit_engine: ExploitEngine（可选；提供且GameState带对手信息时启用exploit调整）
        """
        self.range_engine = range_engine
        self.equity_engine = equity_engine
        self.board_analyzer = board_analyzer
        self.strategy = strategy
        self.exploit_engine = exploit_engine
        self._full_range = None  # 懒加载的完整1326组合范围

        # 如果没有提供strategy，使用默认GTOStrategy
        if self.strategy is None:
            from advisor.strategy.gto_strategy import GTOStrategy
            self.strategy = GTOStrategy()

    def decide(self, game_state: any) -> DecisionTrace:
        """
        完整决策流程

        Args:
            game_state: GameState（advisor的GameState对象）

        Returns:
            DecisionTrace（包含所有中间结果）
        """
        start_time = time.time()

        # 生成trace_id
        trace_id = str(uuid.uuid4())[:8]

        # 1. Analysis阶段
        analysis_start = time.time()

        hero_range, villain_range, range_advantage = self._analyze_ranges(game_state)
        equity_info = None
        board_analysis = None

        if game_state.street != 'preflop':
            # 翻后需要equity和board分析
            equity_info = self._calculate_equity(game_state, villain_range)
            board_analysis = self._analyze_board(game_state)

        analysis_time = (time.time() - analysis_start) * 1000

        # 2. Strategy阶段
        strategy_start = time.time()

        # 构建StrategyContext
        ctx = self._build_strategy_context(
            game_state,
            hero_range,
            villain_range,
            equity_info,
            range_advantage,
            board_analysis
        )

        # 调用strategy决策
        gto_decision = self.strategy.decide(ctx)

        # 2.5 Exploit阶段（有exploit_engine且GameState带对手信息时）
        exploit_decision = None
        final_decision = gto_decision
        exploit_meta = {}

        if self.exploit_engine is not None:
            villain_profile = self._build_villain_profile(game_state)
            if villain_profile is not None:
                adjustment = self.exploit_engine.calculate_adjustment(
                    villain_profile, ctx, gto_decision
                )
                if adjustment.adjustments and adjustment.exploit_weight > 0:
                    adjusted_dist = adjustment.apply_to_frequencies(
                        gto_decision.action_distribution
                    )
                    exploit_decision = StrategyDecision(
                        action_distribution=adjusted_dist,
                        sizing_distribution=dict(gto_decision.sizing_distribution),
                        reasoning=adjustment.reasoning,
                        confidence=adjustment.confidence,
                        key_factors={
                            **gto_decision.key_factors,
                            'exploit_weight': adjustment.exploit_weight,
                            'exploit_adjustments': dict(adjustment.adjustments),
                            'villain_type': villain_profile.player_type.value,
                        },
                    )
                    final_decision = exploit_decision
                exploit_meta = {
                    'villain_type': villain_profile.player_type.value,
                    'exploit_weight': adjustment.exploit_weight,
                    'exploit_reasoning': adjustment.reasoning,
                }

        strategy_time = (time.time() - strategy_start) * 1000

        # 3. 选择最终action
        selected_action = self.select_action(final_decision)

        total_time = (time.time() - start_time) * 1000

        # 4. 构建DecisionTrace
        trace = DecisionTrace(
            trace_id=trace_id,
            timestamp=time.time(),
            game_state=game_state,
            hero_range=hero_range,
            villain_range=villain_range,
            equity_info=equity_info,
            range_advantage=range_advantage,
            board_analysis=board_analysis,
            gto_decision=gto_decision,
            exploit_decision=exploit_decision,
            final_decision=final_decision,
            selected_action=selected_action,
            analysis_time_ms=analysis_time,
            strategy_time_ms=strategy_time,
            total_time_ms=total_time,
            metadata={
                'street': game_state.street,
                'position': str(game_state.position),
                'strategy': self.strategy.get_name(),
                **exploit_meta,
            }
        )

        # 5. 验证模块使用（开发时检查）
        module_usage = trace.verify_module_usage()
        if not all(module_usage.values()):
            # 记录警告（但不阻止）
            unused_modules = [k for k, v in module_usage.items() if not v]
            trace.metadata['warning'] = f"Modules not used: {unused_modules}"

        return trace

    def _analyze_ranges(self, game_state: any) -> tuple:
        """
        分析hero和villain的range

        Args:
            game_state: GameState

        Returns:
            (hero_range, villain_range, range_advantage)
        """
        # 获取position
        position = self._convert_position(game_state.position)

        # 转换action_history（GameState的action_history是string list，需要转换为Action list）
        action_history = self._convert_action_history(game_state)

        # 获取hero GTO range
        hero_range = self.range_engine.get_ideal_range(
            position=position,
            action_history=action_history
        )
        # 空范围兜底（如BB未被加注时没有open range）：
        # 此时hero的范围是完整随机范围，绝不能让percentile退化为0.5中间值
        if len(hero_range) == 0:
            hero_range = Range.full()

        # 获取villain range：优先根据其翻前行动定基准范围
        villain_position = self._estimate_villain_position(game_state)
        villain_range = self._estimate_villain_base_range(
            game_state, villain_position, position)

        board = list(game_state.board) if game_state.board else []

        # 翻后：按双方行动序列收缩范围
        # villain收缩强度取决于其动作的信息量（跟注站的call不含信息）
        if game_state.street != 'preflop' and board:
            villain_style = self._villain_narrow_style(game_state)
            villain_range = self._narrow_by_actions(
                villain_range, board, getattr(game_state, 'villain_actions', None),
                style=villain_style)
            # hero自己的动作遵循GTO策略设计 → honest收缩
            hero_range = self._narrow_by_actions(
                hero_range, board, getattr(game_state, 'hero_actions', None),
                style='honest')

            # villain不可能持有hero的牌
            villain_range = villain_range.remove_dead_cards(set(game_state.hero_hand.cards))

        # 分析range interaction（如果是翻后）
        range_advantage = None
        if game_state.street != 'preflop' and board:
            range_advantage = self.range_engine.analyze_range_interaction(
                hero_range=hero_range,
                villain_range=villain_range,
                board=board
            )

        return hero_range, villain_range, range_advantage

    def _estimate_villain_base_range(self, game_state: any,
                                     villain_position: Position,
                                     hero_position: Position) -> Range:
        """
        根据villain的翻前行动确定其基准范围

        - 翻前有raise → open range
        - 只有call → 跟注范围（比open range弱，去掉了会3bet的顶部和会fold的底部）
        - 无信息 → 该位置的open range（保守默认）
        """
        villain_actions = getattr(game_state, 'villain_actions', None) or []
        preflop_actions = [a['action'] for a in villain_actions
                           if a.get('street') == 'preflop']

        if any(a in ('raise', 'bet') for a in preflop_actions):
            return self.range_engine.get_ideal_range(
                position=villain_position, action_history=[])
        elif 'call' in preflop_actions:
            return self.range_engine.get_preflop_caller_range(
                villain_position, hero_position)
        else:
            return self.range_engine.get_ideal_range(
                position=villain_position, action_history=[])

    def _villain_narrow_style(self, game_state: any) -> str:
        """
        按对手类型确定其动作的信息量档位

        - 松被动/疯狂型（什么牌都call/bet）→ sticky（动作几乎不含信息）
        - 紧型/规则型 → honest（动作与牌力强相关）
        - 未知 → neutral
        """
        from advisor.modeling import PlayerType

        opponent_type = getattr(game_state, 'opponent_type', None)
        if opponent_type in (PlayerType.CALLING_STATION, PlayerType.LAP,
                             PlayerType.FISH, PlayerType.MANIAC):
            return 'sticky'
        if opponent_type in (PlayerType.NIT, PlayerType.WEAK_TIGHT,
                             PlayerType.TAG, PlayerType.SOLID_REG):
            return 'honest'
        return 'neutral'

    def _narrow_by_actions(self, range_obj: Range, board: list,
                           actions: Optional[list],
                           style: str = 'neutral') -> Range:
        """按翻后行动序列逐步收缩范围"""
        if not actions:
            return range_obj

        narrowed = range_obj
        for a in actions:
            if a.get('street') == 'preflop':
                continue
            narrowed = self.range_engine.narrow_range_postflop(
                narrowed, board, a.get('action', ''), style=style)
        return narrowed

    def _calculate_equity(self, game_state: any, villain_range: Range) -> Optional[EquityInfo]:
        """
        计算equity（翻后）

        Args:
            game_state: GameState
            villain_range: Villain的range

        Returns:
            EquityInfo
        """
        if not self.equity_engine:
            return None

        if not game_state.board or len(game_state.board) < 3:
            return None

        # 决定iterations（根据street）
        if game_state.street == 'river':
            iterations = 50  # River只有1张未知牌
        elif game_state.street == 'turn':
            iterations = 200
        else:  # flop
            iterations = 200

        board = list(game_state.board)

        return self.equity_engine.calculate_equity(
            hand=game_state.hero_hand,
            villain_range=villain_range,
            board=board,
            iterations=iterations
        )

    def _analyze_board(self, game_state: any) -> Optional[BoardAnalysis]:
        """
        分析board texture（翻后）

        Args:
            game_state: GameState

        Returns:
            BoardAnalysis
        """
        if not self.board_analyzer:
            return None

        if not game_state.board or len(game_state.board) < 3:
            return None

        board = list(game_state.board)
        return self.board_analyzer.analyze(board)

    def _build_strategy_context(
        self,
        game_state: any,
        hero_range: Range,
        villain_range: Range,
        equity_info: Optional[EquityInfo],
        range_advantage: Optional[RangeAdvantage],
        board_analysis: Optional[BoardAnalysis]
    ) -> StrategyContext:
        """
        构建StrategyContext

        Args:
            game_state: GameState
            hero_range: Hero range
            villain_range: Villain range
            equity_info: Equity信息
            range_advantage: Range优势
            board_analysis: Board分析

        Returns:
            StrategyContext
        """
        # 转换position
        position = self._convert_position(game_state.position)
        villain_position = self._estimate_villain_position(game_state)

        # 转换action_history（使用helper方法）
        action_history = self._convert_action_history(game_state)

        # 判断是否facing bet（从game_state直接获取，不依赖action_history推断）
        # 翻前特殊：BB的盲注不算"下注"——只有超过1BB的投入才是真的加注
        # （否则BTN首入会被误判为facing bet，走防守分支而不是开池分支）
        facing_bet = False
        facing_bet_size = 0.0
        if hasattr(game_state, 'facing_bet') and game_state.facing_bet is not None:
            threshold = 1.01 if game_state.street == 'preflop' else 0.01
            facing_bet = game_state.facing_bet > threshold
            facing_bet_size = game_state.facing_bet if facing_bet else 0.0

        # Hero手牌percentile：由RangeEngine基于（可能已收缩的）hero范围计算
        board = list(game_state.board) if game_state.board else None
        hero_percentile = self.range_engine.get_hand_percentile(
            game_state.hero_hand, hero_range,
            board=board if game_state.street != 'preflop' else None)

        # 翻前另计完整范围percentile（防守宽度按赔率扩展时用：
        # 面对便宜的加注，防守范围要比预置的continue range宽得多）
        hero_percentile_full = None
        if game_state.street == 'preflop':
            if self._full_range is None:
                self._full_range = Range.full()
            hero_percentile_full = self.range_engine.get_hand_percentile(
                game_state.hero_hand, self._full_range, board=None)

        # 构建StrategyContext
        ctx = StrategyContext(
            street=game_state.street,
            position=position,
            action_history=action_history,
            pot_size=game_state.pot_size,
            effective_stack=game_state.effective_stack,
            hero_hand=game_state.hero_hand,
            hero_range=hero_range,
            villain_range=villain_range,
            villain_position=villain_position,
            villain_tendencies=self._extract_villain_tendencies(game_state),
            equity_info=equity_info,
            range_advantage=range_advantage,
            board_analysis=board_analysis,
            facing_bet=facing_bet,
            facing_bet_size=facing_bet_size,
            hero_hand_percentile=hero_percentile,
            hero_hand_percentile_full=hero_percentile_full,
            to_call=(game_state.bet_to_call or 0.0) if hasattr(game_state, 'bet_to_call') else 0.0,
        )

        return ctx

    def select_action(self, decision: StrategyDecision) -> Action:
        """
        从决策分布中选择最终action

        Args:
            decision: StrategyDecision

        Returns:
            Action
        """
        # 1. 从action_distribution中采样
        actions = list(decision.action_distribution.keys())
        probs = list(decision.action_distribution.values())

        selected_action_type = random.choices(actions, weights=probs, k=1)[0]

        # 2. 如果需要sizing，从sizing_distribution中采样
        amount = 0.0
        if selected_action_type in ['raise', 'bet']:
            if decision.sizing_distribution:
                sizings = list(decision.sizing_distribution.keys())
                sizing_probs = list(decision.sizing_distribution.values())
                pot_fraction = random.choices(sizings, weights=sizing_probs, k=1)[0]
                # pot_fraction是pot的倍数，需要转换为实际金额
                # 这里简化：直接用pot_fraction作为金额
                amount = pot_fraction
            else:
                # 没有sizing分布，使用默认值
                amount = 1.0

        return Action(action=selected_action_type, amount=amount)

    def _build_villain_profile(self, game_state: any) -> Optional['PlayerProfile']:
        """
        从GameState的对手信息构建PlayerProfile

        需要opponent_type或opponent_stats至少一项；都没有则返回None（不exploit）。
        """
        from advisor.core.data_structures import PlayerProfile
        from advisor.modeling import PlayerType

        opponent_type = getattr(game_state, 'opponent_type', None)
        stats = getattr(game_state, 'opponent_stats', None)

        if opponent_type is None and stats is None:
            return None

        if stats is not None:
            # fold_to_cbet无观测样本时OpponentStats默认0.0，会被误读为"从不弃牌"
            # （最大粘性）→ 无样本时用0.5中性值
            faced_cbet_samples = getattr(stats, '_faced_cbet_count', 0)
            fold_to_cbet = stats.fold_to_cbet_flop if faced_cbet_samples > 0 else 0.5

            return PlayerProfile(
                player_id=stats.player_id,
                player_type=opponent_type or PlayerType.UNKNOWN,
                vpip=stats.vpip,
                pfr=stats.pfr,
                af=stats.af,
                wtsd=stats.wtsd,
                w_sd=stats.w_sd,
                cbet_freq_flop=stats.cbet_flop,
                cbet_freq_turn=stats.cbet_turn,
                cbet_freq_river=stats.cbet_river,
                fold_to_cbet_flop=fold_to_cbet,
                fold_to_cbet_turn=stats.fold_to_cbet_turn,
                three_bet_freq=stats.three_bet_pct,
                fold_to_3bet=stats.fold_to_3bet,
                four_bet_freq=stats.four_bet_pct,
                sample_size=stats.hands_played,
                hands_observed=stats.hands_played,
            )

        # 只有类型没有统计：用类型的典型数值。
        # hands_observed=0 表示"无实测统计"（exploit层的统计门槛按此豁免），
        # sample_size=30 让exploit权重达到可用档位（信任显式传入的类型）
        return PlayerProfile(
            player_id='unknown',
            player_type=opponent_type,
            sample_size=30,
            hands_observed=0,
        )

    def _extract_villain_tendencies(self, game_state: any) -> dict:
        """从opponent_stats提取关键统计传给StrategyContext"""
        stats = getattr(game_state, 'opponent_stats', None)
        if stats is None:
            return {}
        return {
            'vpip': stats.vpip,
            'pfr': stats.pfr,
            'af': stats.af,
            'fold_to_cbet_flop': stats.fold_to_cbet_flop,
            'three_bet_pct': stats.three_bet_pct,
            'fold_to_3bet': stats.fold_to_3bet,
            'hands_played': stats.hands_played,
        }

    def _convert_action_history(self, game_state: any) -> List[Action]:
        """
        转换action_history从string list到Action list

        GameState的action_history是string list (e.g., ['raise', 'call'])
        RangeEngine期望Action list

        Args:
            game_state: GameState

        Returns:
            Action list
        """
        action_history = []
        if game_state.action_history:
            for action_str in game_state.action_history:
                # 简化：只记录action类型
                if action_str in ['fold', 'call', 'check']:
                    action_history.append(Action(action=action_str, amount=0))
                elif 'raise' in action_str or 'bet' in action_str:
                    # 尝试提取金额（如果有）
                    amount = game_state.facing_bet if game_state.facing_bet else 0
                    action_history.append(Action(action='raise' if 'raise' in action_str else 'bet', amount=amount))
            return action_history

        # action_history未提供时，从结构化行动记录合成翻前加注序列
        # （get_ideal_range按翻前raise次数选择 open/3bet/4bet 范围）
        villain_actions = getattr(game_state, 'villain_actions', None) or []
        hero_actions = getattr(game_state, 'hero_actions', None) or []
        preflop_raises = sum(
            1 for a in villain_actions + hero_actions
            if a.get('street') == 'preflop' and a.get('action') in ('raise', 'bet')
        )
        # 3+次加注（facing 4bet+）沿用4bet-continue范围（get_ideal_range只识别到2次）
        preflop_raises = min(preflop_raises, 2)
        amount = game_state.facing_bet if game_state.facing_bet else 0
        for _ in range(preflop_raises):
            action_history.append(Action(action='raise', amount=amount))
        return action_history

    def _convert_position(self, position_str: str) -> Position:
        """
        转换position字符串到Position枚举

        Args:
            position_str: 'BTN', 'CO', 'MP', 'SB', 'BB', etc.

        Returns:
            Position枚举
        """
        position_map = {
            'BTN': Position.BTN,
            'BTN/SB': Position.BTN,  # poker_env单挑时按钮位的名称
            'CO': Position.CO,
            'MP': Position.MP,
            'SB': Position.SB,
            'BB': Position.BB,
            'UTG': Position.MP,  # 简化：UTG映射到MP
        }
        return position_map.get(position_str, Position.MP)

    def _estimate_villain_position(self, game_state: any) -> Position:
        """
        估计villain的position

        简化实现：假设单挑，villain在hero的对面

        Args:
            game_state: GameState

        Returns:
            Villain的Position
        """
        hero_pos = self._convert_position(game_state.position)

        # 简化：BTN vs BB, CO vs BTN, 等等
        if hero_pos == Position.BTN:
            return Position.BB
        elif hero_pos == Position.BB:
            return Position.BTN
        elif hero_pos == Position.CO:
            return Position.BTN
        else:
            return Position.CO
