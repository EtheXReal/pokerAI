"""
DecisionIntegrator实现

Orchestrate所有模块生成完整决策，确保模块不被架空。
"""

import time
import uuid
import random
from typing import Optional, List

from advisor_v2.core.interfaces.integration_interface import IDecisionIntegrator
from advisor_v2.core.interfaces.analysis_interface import (
    IRangeEngine,
    IEquityEngine,
    IBoardAnalyzer
)
from advisor_v2.core.interfaces.strategy_interface import IStrategy
from advisor_v2.core.data_structures import (
    DecisionTrace,
    StrategyContext,
    StrategyDecision,
    Action,
    EquityInfo,
    RangeAdvantage,
    BoardAnalysis,
)
from advisor.range_engine.cards import Hand, Card
from advisor.range_engine.range import Range
from advisor.strategy_engine.gto_baseline import Position


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
        strategy: Optional[IStrategy] = None
    ):
        """
        初始化DecisionIntegrator

        Args:
            range_engine: RangeEngine（必需）
            equity_engine: EquityEngine（翻后需要）
            board_analyzer: BoardAnalyzer（翻后需要）
            strategy: Strategy（默认GTOStrategy）
        """
        self.range_engine = range_engine
        self.equity_engine = equity_engine
        self.board_analyzer = board_analyzer
        self.strategy = strategy

        # 如果没有提供strategy，使用默认GTOStrategy
        if self.strategy is None:
            from advisor_v2.strategy.gto_strategy import GTOStrategy
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

        strategy_time = (time.time() - strategy_start) * 1000

        # 3. 选择最终action
        selected_action = self.select_action(gto_decision)

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
            final_decision=gto_decision,  # Phase 1只有GTO
            selected_action=selected_action,
            analysis_time_ms=analysis_time,
            strategy_time_ms=strategy_time,
            total_time_ms=total_time,
            metadata={
                'street': game_state.street,
                'position': str(game_state.position),
                'strategy': self.strategy.get_name()
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

        # 获取hero GTO range
        hero_range = self.range_engine.get_ideal_range(
            position=position,
            action_history=game_state.action_history or []
        )

        # 获取villain range（简化：使用GTO range）
        # TODO: Phase 2集成OpponentModel
        villain_position = self._estimate_villain_position(game_state)
        villain_range = self.range_engine.get_ideal_range(
            position=villain_position,
            action_history=[]
        )

        # 分析range interaction（如果是翻后）
        range_advantage = None
        if game_state.street != 'preflop' and game_state.board:
            board = list(game_state.board) if game_state.board else []
            range_advantage = self.range_engine.analyze_range_interaction(
                hero_range=hero_range,
                villain_range=villain_range,
                board=board
            )

        return hero_range, villain_range, range_advantage

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

        # 转换action_history
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
            villain_tendencies={},  # TODO: Phase 2集成OpponentModel
            equity_info=equity_info,
            range_advantage=range_advantage,
            board_analysis=board_analysis,
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
