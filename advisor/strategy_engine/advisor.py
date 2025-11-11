"""
ProLevelAdvisor - 职业级决策顾问 (Pro-Level Decision Advisor)

整合三层架构的核心决策引擎：
- Range Engine (Phase 2.1): 范围推断和equity计算
- Opponent Modeling (Phase 2.2): 对手分类和统计
- Strategy Engine (Phase 2.3): GTO基线 + Exploit调整

提供端到端的决策输出。
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import sys
sys.path.append('/home/user/pokerAI')

# Range Engine
from advisor.range_engine import (
    Range, Hand, Board, EquityCalculator, BoardTexture,
    get_open_range, parse_range_dict
)

# Opponent Modeling
from advisor.opponent_modeling import (
    PlayerType, OpponentStats, PlayerClassifier,
    classify_player
)

# Strategy Engine
from .decision import DecisionOutput, merge_decisions
from .gto_baseline import GTOBaseline, GTOContext, Street, Position
from .range_estimator import RangeEstimator, Action
from .exploits import get_exploit_strategy


@dataclass
class GameState:
    """
    游戏状态快照

    包含做决策所需的所有信息
    """
    # 必填字段（没有默认值）
    street: str  # 'preflop', 'flop', 'turn', 'river'
    position: str  # 'UTG', 'MP', 'CO', 'BTN', 'SB', 'BB'
    is_in_position: bool
    hero_hand: Hand
    pot_size: float  # BB
    effective_stack: float  # BB
    hero_stack: float  # BB

    # 可选字段（有默认值）
    board: Optional[Board] = None
    action_history: Optional[List[str]] = None  # ['open', '3bet', 'call', ...]

    # 当前面对的情况
    facing_bet: Optional[float] = None  # 对手下注大小 (BB)
    bet_to_call: Optional[float] = None  # 需要跟注的金额 (BB)
    min_raise: Optional[float] = None  # 最小加注 (BB)

    # 对手信息
    num_opponents: int = 1
    opponent_stats: Optional[OpponentStats] = None
    opponent_type: Optional[PlayerType] = None

    # 其他
    tournament: bool = False  # 是否锦标赛
    bubble: bool = False  # 是否泡沫阶段

    def __post_init__(self):
        """初始化后处理"""
        if self.action_history is None:
            self.action_history = []

        # 计算SPR
        self.spr = self.effective_stack / self.pot_size if self.pot_size > 0 else 999

        # 如果没有对手类型，使用默认
        if self.opponent_type is None and self.opponent_stats is not None:
            result = classify_player(self.opponent_stats)
            self.opponent_type = result.player_type


class ProLevelAdvisor:
    """
    职业级决策顾问

    整合三层架构，提供端到端的决策建议
    """

    def __init__(self,
                 exploit_weight: float = 0.4,
                 gto_weight: float = 0.6):
        """
        初始化

        Args:
            exploit_weight: Exploit策略权重 (0.0-1.0)
            gto_weight: GTO策略权重 (0.0-1.0)
        """
        # 三层架构
        self.range_estimator = RangeEstimator()
        self.equity_calculator = EquityCalculator(iterations=5000)
        self.gto_baseline = GTOBaseline()
        self.classifier = PlayerClassifier()

        # 策略权重
        self.exploit_weight = exploit_weight
        self.gto_weight = gto_weight

        # 归一化权重
        total = exploit_weight + gto_weight
        if total > 0:
            self.exploit_weight /= total
            self.gto_weight /= total

    def advise(self, game_state: GameState) -> DecisionOutput:
        """
        主决策接口

        Args:
            game_state: 游戏状态

        Returns:
            DecisionOutput 决策输出
        """
        # ===== 步骤1: 推断范围 =====
        hero_range, villain_range = self._estimate_ranges(game_state)

        # ===== 步骤2: 计算equity =====
        equity = self._calculate_equity(
            game_state.hero_hand,
            villain_range,
            game_state.board,
            game_state.num_opponents
        )

        # ===== 步骤3: 分析公共牌 =====
        board_texture = None
        if game_state.board and len(game_state.board.cards) > 0:
            board_texture = BoardTexture(game_state.board)

        # ===== 步骤4: 判断范围优势 =====
        range_advantage = self._assess_range_advantage(
            hero_range, villain_range, game_state.board
        )

        # ===== 步骤5: 构建GTO上下文 =====
        gto_ctx = self._build_gto_context(
            game_state, equity, range_advantage, board_texture
        )

        # ===== 步骤6: GTO基线决策 =====
        gto_decision = self._get_gto_decision(game_state, gto_ctx)

        # ===== 步骤7: Exploit调整 =====
        exploit_decision = self._get_exploit_decision(
            game_state, gto_ctx, gto_decision
        )

        # ===== 步骤8: 混合策略 =====
        final_decision = self._merge_strategies(
            gto_decision, exploit_decision, game_state
        )

        # ===== 步骤9: 添加决策依据 =====
        final_decision.reasoning.update({
            'equity': equity,
            'range_advantage': range_advantage,
            'opponent_type': game_state.opponent_type.name if game_state.opponent_type else 'Unknown',
            'board_texture': board_texture.wetness if board_texture else 'unknown',
            'position': 'IP' if game_state.is_in_position else 'OOP',
            'pot_odds': gto_ctx.pot_size / (gto_ctx.pot_size + gto_ctx.bet_to_call) if gto_ctx.bet_to_call else 0,
            'spr': game_state.spr,
            'street': game_state.street,
            'strategy_weights': {
                'gto': self.gto_weight,
                'exploit': self.exploit_weight
            }
        })

        return final_decision

    # ===== 内部方法 =====

    def _estimate_ranges(self, game_state: GameState) -> tuple:
        """推断hero和villain范围"""
        # Hero范围（简化：假设合理开池/跟注范围）
        try:
            pos = Position[game_state.position.upper()]
            hero_dict = get_open_range(pos.value, 'normal')
            hero_range = parse_range_dict(hero_dict)
        except:
            hero_range = Range.from_string("22+,A2s+,K5s+,Q8s+,J8s+,T8s+,A5o+,K9o+")

        # Villain范围
        if game_state.action_history and game_state.opponent_type:
            try:
                last_action = game_state.action_history[-1]
                villain_pos = Position.BTN  # 默认
                villain_range = self.range_estimator.estimate_preflop_range(
                    villain_pos,
                    Action[last_action.upper()],
                    game_state.opponent_type
                )
            except:
                villain_range = Range.from_string("22+,A2s+,K8s+,Q9s+,J9s+,T8s+")
        else:
            villain_range = Range.from_string("22+,A2s+,K8s+,Q9s+,J9s+,T8s+")

        return hero_range, villain_range

    def _calculate_equity(self,
                         hero_hand: Hand,
                         villain_range: Range,
                         board: Optional[Board],
                         num_opponents: int) -> float:
        """计算equity"""
        try:
            if board is None:
                board = Board([])

            villain_hands = villain_range.to_hands()
            if not villain_hands:
                return 0.5

            # 移除死牌
            dead_cards = set(hero_hand.cards)
            if board:
                dead_cards.update(board.cards)

            valid_hands = [h for h in villain_hands
                          if not (set(h.cards) & dead_cards)]

            if not valid_hands:
                return 0.5

            # 计算equity
            result = self.equity_calculator.calculate_vs_range(
                hero_hand, valid_hands[:100], board  # 限制100个combos加速
            )

            equity = result.equity

            # 多人底池打折
            if num_opponents > 1:
                equity = self.gto_baseline.multiway_equity_discount(equity, num_opponents)

            return equity

        except Exception as e:
            # 出错返回默认值
            return 0.5

    def _assess_range_advantage(self,
                                hero_range: Range,
                                villain_range: Range,
                                board: Optional[Board]) -> str:
        """评估范围优势"""
        hero_size = len(hero_range)
        villain_size = len(villain_range)

        if hero_size > villain_size * 1.3:
            return 'strong'
        elif hero_size > villain_size * 0.8:
            return 'medium'
        else:
            return 'weak'

    def _build_gto_context(self,
                          game_state: GameState,
                          equity: float,
                          range_advantage: str,
                          board_texture: Optional[BoardTexture]) -> GTOContext:
        """构建GTO上下文"""
        # 转换street
        street_map = {
            'preflop': Street.PREFLOP,
            'flop': Street.FLOP,
            'turn': Street.TURN,
            'river': Street.RIVER
        }
        street = street_map.get(game_state.street.lower(), Street.FLOP)

        # 转换position
        try:
            position = Position[game_state.position.upper()]
        except:
            position = Position.BTN

        return GTOContext(
            street=street,
            position=position,
            is_in_position=game_state.is_in_position,
            equity=equity,
            range_advantage=range_advantage,
            pot_size=game_state.pot_size,
            effective_stack=game_state.effective_stack,
            spr=game_state.spr,
            num_opponents=game_state.num_opponents,
            facing_bet=game_state.facing_bet,
            bet_to_call=game_state.bet_to_call,
            board_texture=board_texture.wetness if board_texture else None
        )

    def _get_gto_decision(self,
                         game_state: GameState,
                         gto_ctx: GTOContext) -> DecisionOutput:
        """获取GTO基线决策"""
        if game_state.street == 'preflop':
            # 翻前策略
            try:
                hand_strength = 0.7  # 简化
                action_dist = self.gto_baseline.preflop_strategy(
                    gto_ctx.position,
                    hand_strength,
                    game_state.action_history,
                    game_state.effective_stack
                )
            except:
                action_dist = {'fold': 0.3, 'call': 0.5, 'raise': 0.2}
        else:
            # 翻后策略
            action_dist = self.gto_baseline.postflop_strategy(gto_ctx)

        # 转换为标准格式
        recommended = max(action_dist, key=action_dist.get)

        return DecisionOutput(
            action_distribution=action_dist,
            recommended_action=recommended,
            reasoning={'strategy': 'GTO baseline'},
            confidence=0.8
        )

    def _get_exploit_decision(self,
                             game_state: GameState,
                             gto_ctx: GTOContext,
                             gto_decision: DecisionOutput) -> DecisionOutput:
        """获取Exploit调整决策"""
        if not game_state.opponent_type:
            # 无对手信息，返回GTO
            return gto_decision

        # 获取exploit策略
        exploit_strategy = get_exploit_strategy(game_state.opponent_type)

        # 应用调整
        if game_state.facing_bet:
            # 防守情况
            adjusted_dist = exploit_strategy.apply_to_gto_strategy(
                gto_decision.action_distribution,
                'defense'
            )
        elif gto_ctx.equity > 0.65:
            # 价值下注情况
            adjusted_dist = exploit_strategy.apply_to_gto_strategy(
                gto_decision.action_distribution,
                'value'
            )
        else:
            # 其他情况
            adjusted_dist = gto_decision.action_distribution.copy()

        recommended = max(adjusted_dist, key=adjusted_dist.get)

        return DecisionOutput(
            action_distribution=adjusted_dist,
            recommended_action=recommended,
            reasoning={'strategy': 'Exploit adjusted'},
            confidence=0.85
        )

    def _merge_strategies(self,
                         gto_decision: DecisionOutput,
                         exploit_decision: DecisionOutput,
                         game_state: GameState) -> DecisionOutput:
        """混合GTO和Exploit策略"""
        # 动态调整权重
        weights = self._calculate_dynamic_weights(game_state)

        # 使用merge_decisions函数
        merged = merge_decisions(
            {'gto': gto_decision, 'exploit': exploit_decision},
            weights
        )

        # 添加尺寸建议
        if 'raise' in merged.recommended_action or 'bet' in merged.recommended_action:
            merged = self._add_sizing_options(merged, game_state)

        return merged

    def _calculate_dynamic_weights(self, game_state: GameState) -> Dict[str, float]:
        """
        动态计算GTO和Exploit权重

        考虑：
        - 对手样本量（样本少 → 更GTO）
        - 对手偏差（偏差大 → 更Exploit）
        - 筹码深度（浅筹码 → 更GTO）
        """
        gto_weight = self.gto_weight
        exploit_weight = self.exploit_weight

        # 如果对手统计不足
        if game_state.opponent_stats:
            hands_played = game_state.opponent_stats.hands_played
            if hands_played < 30:
                # 样本少，更依赖GTO
                gto_weight += 0.2
                exploit_weight -= 0.2

        # 浅筹码更GTO
        if game_state.spr < 3:
            gto_weight += 0.1
            exploit_weight -= 0.1

        # 归一化
        total = gto_weight + exploit_weight
        if total > 0:
            gto_weight /= total
            exploit_weight /= total

        return {'gto': gto_weight, 'exploit': exploit_weight}

    def _add_sizing_options(self,
                           decision: DecisionOutput,
                           game_state: GameState) -> DecisionOutput:
        """添加下注尺寸选项"""
        # 构建尺寸选项
        sizing_options = {
            'r33': 0.15,
            'r50': 0.25,
            'r66': 0.35,
            'r75': 0.15,
            'r100': 0.10,
        }

        # 计算最优尺寸（BB）
        pot = game_state.pot_size
        optimal_sizing_pct = 0.66  # 默认2/3 pot

        # 根据对手类型调整
        if game_state.opponent_type:
            exploit = get_exploit_strategy(game_state.opponent_type)
            if game_state.opponent_type in [PlayerType.FISH, PlayerType.CALLING_STATION]:
                optimal_sizing_pct = exploit.preferred_sizing_vs_weak
            elif game_state.opponent_type in [PlayerType.NIT, PlayerType.ROCK]:
                optimal_sizing_pct = exploit.preferred_sizing_vs_tight

        optimal_sizing_bb = pot * optimal_sizing_pct

        decision.sizing_options = sizing_options
        decision.optimal_sizing = optimal_sizing_bb
        decision.sizing_range = (pot * 0.33, pot * 1.0)

        return decision


# ===== 便捷函数 =====

def create_advisor(exploit_weight: float = 0.4) -> ProLevelAdvisor:
    """
    创建顾问实例

    Args:
        exploit_weight: Exploit权重 (0.0-1.0)

    Returns:
        ProLevelAdvisor实例
    """
    return ProLevelAdvisor(
        exploit_weight=exploit_weight,
        gto_weight=1.0 - exploit_weight
    )


def quick_advise(hero_hand: str,
                board: str,
                position: str,
                pot: float,
                stack: float,
                opponent_type: Optional[PlayerType] = None) -> DecisionOutput:
    """
    快速决策（简化接口）

    Args:
        hero_hand: 手牌字符串 "AsKh"
        board: 公共牌字符串 "Ah9c3d" 或 ""
        position: 位置 "BTN", "BB", etc.
        pot: 底池大小 (BB)
        stack: 有效筹码 (BB)
        opponent_type: 对手类型（可选）

    Returns:
        DecisionOutput
    """
    advisor = create_advisor()

    game_state = GameState(
        street='flop' if board else 'preflop',
        position=position,
        is_in_position=(position in ['BTN', 'CO']),
        hero_hand=Hand.from_str(hero_hand),
        board=Board.from_str(board) if board else None,
        pot_size=pot,
        effective_stack=stack,
        hero_stack=stack,
        opponent_type=opponent_type,
    )

    return advisor.advise(game_state)
