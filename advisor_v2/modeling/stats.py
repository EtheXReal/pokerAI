"""
对手统计数据结构

OpponentStats: 完整的20+对手统计指标
PositionStats: 按位置细分的统计
StreetsStats: 按街道细分的统计

设计原则:
1. 所有百分比指标范围 [0.0, 1.0]
2. 增量更新 (避免存储所有历史数据)
3. 支持序列化 (用于SQLite存储)
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, List
import json

from .models import PositionType, StreetType


@dataclass
class StreetsStats:
    """
    按街道细分的统计

    用于追踪玩家在不同街道的行为模式
    """
    # C-bet频率 (作为翻前加注者的持续下注)
    cbet_flop: float = 0.0
    cbet_turn: float = 0.0
    cbet_river: float = 0.0

    # 对C-bet的响应
    fold_to_cbet_flop: float = 0.0
    fold_to_cbet_turn: float = 0.0
    fold_to_cbet_river: float = 0.0
    raise_cbet_flop: float = 0.0
    raise_cbet_turn: float = 0.0

    # 激进因子 (bet+raise / call)
    agg_flop: float = 0.0
    agg_turn: float = 0.0
    agg_river: float = 0.0

    # 样本数
    _cbet_opportunities: List[int] = field(default_factory=lambda: [0, 0, 0])  # [flop, turn, river]
    _faced_cbet_count: List[int] = field(default_factory=lambda: [0, 0, 0])
    _actions_count: Dict[str, List[int]] = field(default_factory=dict)  # 用于计算AF

    def to_dict(self) -> dict:
        """转换为字典（用于存储）"""
        return {k: v for k, v in asdict(self).items() if not k.startswith('_')}


@dataclass
class PositionStats:
    """
    按位置细分的统计

    用于追踪玩家在不同位置的打法差异
    """
    # 开池加注频率 (按位置)
    open_raise_utg: float = 0.0
    open_raise_mp: float = 0.0
    open_raise_co: float = 0.0
    open_raise_btn: float = 0.0
    open_raise_sb: float = 0.0

    # 各位置的VPIP
    vpip_utg: float = 0.0
    vpip_mp: float = 0.0
    vpip_co: float = 0.0
    vpip_btn: float = 0.0
    vpip_sb: float = 0.0
    vpip_bb: float = 0.0

    # 样本数
    _hands_by_position: Dict[str, int] = field(default_factory=dict)
    _open_opportunities: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典（用于存储）"""
        return {k: v for k, v in asdict(self).items() if not k.startswith('_')}


@dataclass
class OpponentStats:
    """
    完整的对手统计数据 (20+核心指标)

    分类:
    1. 基础指标 (4个): hands_played, vpip, pfr, af
    2. 翻前指标 (7个): 3-bet, 4-bet, fold_to_3bet, etc.
    3. 翻后指标 (6个): c-bet, fold_to_cbet, etc.
    4. 进攻性指标 (5个): wtsd, w_sd, agg_by_street
    5. 特殊指标 (3个): check_raise, donk_bet, float

    所有百分比字段取值范围: [0.0, 1.0]
    """

    # ========== 基础信息 ==========
    player_id: str
    hands_played: int = 0
    last_updated: Optional[float] = None  # timestamp

    # ========== 基础指标 (4个) ==========
    vpip: float = 0.0  # Voluntarily Put money In Pot (主动入池率)
    pfr: float = 0.0  # Pre-Flop Raise (翻前加注率)
    af: float = 0.0  # Aggression Factor: (bet+raise) / call
    overall_agg: float = 0.0  # 总体激进度

    # ========== 翻前指标 (7个) ==========
    three_bet_pct: float = 0.0  # 3-bet频率
    four_bet_pct: float = 0.0  # 4-bet频率
    fold_to_3bet: float = 0.0  # 面对3-bet的弃牌率
    call_3bet: float = 0.0  # 面对3-bet的跟注率
    fold_to_steal: float = 0.0  # 盲注位对偷盲的弃牌率
    open_raise_first_in: float = 0.0  # 作为第一个进入底池的加注率
    limp_first_in: float = 0.0  # 作为第一个进入底池的跛入率

    # ========== 翻后指标 (6个) ==========
    cbet_flop: float = 0.0  # 翻牌圈持续下注频率
    cbet_turn: float = 0.0  # 转牌圈持续下注频率
    cbet_river: float = 0.0  # 河牌圈持续下注频率
    fold_to_cbet_flop: float = 0.0  # 对翻牌c-bet弃牌率
    fold_to_cbet_turn: float = 0.0  # 对转牌c-bet弃牌率
    raise_cbet: float = 0.0  # 对c-bet加注频率

    # ========== 进攻性指标 (5个) ==========
    wtsd: float = 0.0  # Went To ShowDown (摊牌率): 看到翻牌后去摊牌的比例
    w_sd: float = 0.0  # Won at ShowDown (摊牌胜率): 摊牌时获胜的比例
    agg_flop: float = 0.0  # 翻牌圈激进度
    agg_turn: float = 0.0  # 转牌圈激进度
    agg_river: float = 0.0  # 河牌圈激进度

    # ========== 特殊指标 (3个) ==========
    check_raise_freq: float = 0.0  # Check-raise频率
    donk_bet_freq: float = 0.0  # Donk bet频率 (翻后OOP主动下注)
    float_freq: float = 0.0  # Float频率 (飘浮下注: 翻牌跟注,转牌下注)

    # ========== 细分统计 ==========
    streets_stats: StreetsStats = field(default_factory=StreetsStats)
    position_stats: PositionStats = field(default_factory=PositionStats)

    # ========== 内部计数器 (用于增量更新) ==========
    # 这些字段不会被序列化到数据库
    _vpip_opportunities: int = field(default=0, repr=False)
    _pfr_opportunities: int = field(default=0, repr=False)
    _three_bet_opportunities: int = field(default=0, repr=False)
    _faced_3bet_count: int = field(default=0, repr=False)
    _cbet_opportunities: int = field(default=0, repr=False)
    _faced_cbet_count: int = field(default=0, repr=False)
    _saw_flop_count: int = field(default=0, repr=False)
    _showdown_count: int = field(default=0, repr=False)
    _won_showdown_count: int = field(default=0, repr=False)

    # 激进度计数器
    _aggressive_actions: int = field(default=0, repr=False)  # bet + raise
    _passive_actions: int = field(default=0, repr=False)  # call
    _check_raise_opportunities: int = field(default=0, repr=False)
    _check_raises: int = field(default=0, repr=False)

    def __post_init__(self):
        """初始化后处理"""
        if self.last_updated is None:
            import time
            self.last_updated = time.time()

    # ========== 核心更新方法 ==========

    def update_from_hand(self, hand_result: 'HandResult') -> None:
        """
        从单手牌结果更新统计

        Args:
            hand_result: HandResult对象，包含该手牌的完整信息
        """
        from .models import HandResult
        import time

        self.hands_played += 1
        self.last_updated = time.time()

        # 更新基础指标
        if hand_result.vpip:
            self._update_vpip(True)
        else:
            self._update_vpip(False)

        if hand_result.pfr:
            self._update_pfr(True)
        else:
            self._update_pfr(False)

        # 更新翻前指标
        # 3-bet机会：只有面对raise时才算
        if hand_result.faced_raise:
            self._three_bet_opportunities += 1
            if hand_result.three_bet:
                old_total = self.three_bet_pct * (self._three_bet_opportunities - 1)
                self.three_bet_pct = (old_total + 1.0) / self._three_bet_opportunities
            else:
                old_total = self.three_bet_pct * (self._three_bet_opportunities - 1)
                self.three_bet_pct = old_total / self._three_bet_opportunities

        if hand_result.four_bet:
            self._update_4bet(True)

        # 面对3-bet的响应: 只在实际面对3-bet时才更新
        if hand_result.fold_to_3bet or hand_result.call_3bet:
            self._faced_3bet_count += 1
            if hand_result.fold_to_3bet:
                old_total = self.fold_to_3bet * (self._faced_3bet_count - 1)
                self.fold_to_3bet = (old_total + 1.0) / self._faced_3bet_count
            else:
                # 没弃牌，更新弃牌率为0贡献
                old_total = self.fold_to_3bet * (self._faced_3bet_count - 1)
                self.fold_to_3bet = old_total / self._faced_3bet_count

            if hand_result.call_3bet:
                old_total = self.call_3bet * (self._faced_3bet_count - 1)
                self.call_3bet = (old_total + 1.0) / self._faced_3bet_count

        # 更新翻后指标
        if hand_result.cbet_flop is not None:
            self._update_cbet_flop(hand_result.cbet_flop)
        if hand_result.cbet_turn is not None:
            self._update_cbet_turn(hand_result.cbet_turn)
        if hand_result.cbet_river is not None:
            self._update_cbet_river(hand_result.cbet_river)
        if hand_result.fold_to_cbet is not None:
            self._update_fold_to_cbet(hand_result.fold_to_cbet)

        # 更新摊牌统计
        # BUG FIX: 每手牌都需要检查，不仅仅是看到翻牌的手牌
        if hand_result.saw_flop:
            self._saw_flop_count += 1
            if hand_result.went_to_showdown:
                self._showdown_count += 1
                if hand_result.won_at_showdown:
                    self._won_showdown_count += 1

        # 只要有看过翻牌的历史数据，就更新WTSD和W$SD
        # 这样即使当前手牌翻前fold，也会基于最新的总计数更新比例
        if self._saw_flop_count > 0:
            self.wtsd = self._showdown_count / self._saw_flop_count

        if self._showdown_count > 0:
            self.w_sd = self._won_showdown_count / self._showdown_count

        # 更新激进度
        self._update_aggression_from_actions(hand_result.actions)

    def _update_vpip(self, did_vpip: bool) -> None:
        """更新VPIP"""
        self._vpip_opportunities += 1
        if did_vpip:
            # 增量更新平均值
            old_total = self.vpip * (self._vpip_opportunities - 1)
            self.vpip = (old_total + 1.0) / self._vpip_opportunities
        else:
            old_total = self.vpip * (self._vpip_opportunities - 1)
            self.vpip = old_total / self._vpip_opportunities

    def _update_pfr(self, did_pfr: bool) -> None:
        """更新PFR"""
        self._pfr_opportunities += 1
        if did_pfr:
            old_total = self.pfr * (self._pfr_opportunities - 1)
            self.pfr = (old_total + 1.0) / self._pfr_opportunities
        else:
            old_total = self.pfr * (self._pfr_opportunities - 1)
            self.pfr = old_total / self._pfr_opportunities

    def _update_3bet(self, did_3bet: bool) -> None:
        """更新3-bet频率"""
        self._three_bet_opportunities += 1
        if did_3bet:
            old_total = self.three_bet_pct * (self._three_bet_opportunities - 1)
            self.three_bet_pct = (old_total + 1.0) / self._three_bet_opportunities
        else:
            old_total = self.three_bet_pct * (self._three_bet_opportunities - 1)
            self.three_bet_pct = old_total / self._three_bet_opportunities

    def _update_4bet(self, did_4bet: bool) -> None:
        """更新4-bet频率"""
        # 简化处理: 4-bet机会较少,暂时与3-bet合并计数
        pass

    def _update_fold_to_3bet(self, did_fold: bool) -> None:
        """更新面对3-bet的弃牌率"""
        self._faced_3bet_count += 1
        if did_fold:
            old_total = self.fold_to_3bet * (self._faced_3bet_count - 1)
            self.fold_to_3bet = (old_total + 1.0) / self._faced_3bet_count
        else:
            old_total = self.fold_to_3bet * (self._faced_3bet_count - 1)
            self.fold_to_3bet = old_total / self._faced_3bet_count

    def _update_call_3bet(self, did_call: bool) -> None:
        """更新面对3-bet的跟注率"""
        # 已在fold_to_3bet中计数
        if did_call:
            old_total = self.call_3bet * (self._faced_3bet_count - 1)
            self.call_3bet = (old_total + 1.0) / self._faced_3bet_count

    def _update_cbet_flop(self, did_cbet: bool) -> None:
        """更新翻牌c-bet频率"""
        self._cbet_opportunities += 1
        if did_cbet:
            old_total = self.cbet_flop * (self._cbet_opportunities - 1)
            self.cbet_flop = (old_total + 1.0) / self._cbet_opportunities
        else:
            old_total = self.cbet_flop * (self._cbet_opportunities - 1)
            self.cbet_flop = old_total / self._cbet_opportunities

    def _update_cbet_turn(self, did_cbet: bool) -> None:
        """更新转牌c-bet频率"""
        # 简化: 使用同一个计数器
        if did_cbet:
            old_total = self.cbet_turn * self._cbet_opportunities
            self.cbet_turn = (old_total + 1.0) / (self._cbet_opportunities + 1)

    def _update_cbet_river(self, did_cbet: bool) -> None:
        """更新河牌c-bet频率"""
        if did_cbet:
            old_total = self.cbet_river * self._cbet_opportunities
            self.cbet_river = (old_total + 1.0) / (self._cbet_opportunities + 1)

    def _update_fold_to_cbet(self, did_fold: bool) -> None:
        """更新对c-bet弃牌率"""
        self._faced_cbet_count += 1
        if did_fold:
            old_total = self.fold_to_cbet_flop * (self._faced_cbet_count - 1)
            self.fold_to_cbet_flop = (old_total + 1.0) / self._faced_cbet_count
        else:
            old_total = self.fold_to_cbet_flop * (self._faced_cbet_count - 1)
            self.fold_to_cbet_flop = old_total / self._faced_cbet_count

    def _update_aggression_from_actions(self, actions: List['ActionRecord']) -> None:
        """
        从行动列表更新激进度

        AF = (bet + raise) / call

        注意：包括所有街道的行动（翻前+翻后）
        """
        from .models import ActionType

        for action_record in actions:
            if action_record.action.is_aggressive():
                self._aggressive_actions += 1
            elif action_record.action == ActionType.CALL:
                self._passive_actions += 1

        # 更新AF
        if self._passive_actions > 0:
            self.af = self._aggressive_actions / self._passive_actions
        else:
            # 如果从不call，AF等于激进行动次数
            self.af = float(self._aggressive_actions) if self._aggressive_actions > 0 else 0.0

    # ========== 辅助方法 ==========

    def get_confidence(self) -> float:
        """
        计算统计置信度

        基于手数:
        - < 30手: 0.3
        - 30-50手: 0.6
        - 50-100手: 0.8
        - 100-200手: 0.9
        - > 200手: 0.95
        """
        if self.hands_played < 30:
            return 0.3
        elif self.hands_played < 50:
            return 0.6
        elif self.hands_played < 100:
            return 0.8
        elif self.hands_played < 200:
            return 0.9
        else:
            return 0.95

    def to_dict(self) -> dict:
        """
        转换为字典 (用于JSON序列化和数据库存储)

        排除内部计数器字段 (_开头的字段)
        """
        result = {}
        for key, value in asdict(self).items():
            if key.startswith('_'):
                continue
            if isinstance(value, (StreetsStats, PositionStats)):
                result[key] = value.to_dict()
            else:
                result[key] = value
        return result

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> 'OpponentStats':
        """
        从字典创建实例 (用于从数据库加载)

        Args:
            data: 包含统计数据的字典

        Returns:
            OpponentStats实例
        """
        # 处理嵌套对象
        if 'streets_stats' in data and isinstance(data['streets_stats'], dict):
            data['streets_stats'] = StreetsStats(**data['streets_stats'])
        if 'position_stats' in data and isinstance(data['position_stats'], dict):
            data['position_stats'] = PositionStats(**data['position_stats'])

        return cls(**data)

    def __repr__(self) -> str:
        """简洁的字符串表示"""
        return (
            f"OpponentStats(player_id='{self.player_id}', "
            f"hands={self.hands_played}, "
            f"VPIP={self.vpip:.1%}, "
            f"PFR={self.pfr:.1%}, "
            f"AF={self.af:.2f}, "
            f"confidence={self.get_confidence():.1%})"
        )

    def summary(self) -> str:
        """
        详细的统计摘要

        Returns:
            多行字符串，包含主要统计指标
        """
        lines = [
            f"=== Opponent Stats: {self.player_id} ===",
            f"Hands Played: {self.hands_played} (Confidence: {self.get_confidence():.0%})",
            "",
            "Basic Stats:",
            f"  VPIP: {self.vpip:.1%}  |  PFR: {self.pfr:.1%}  |  AF: {self.af:.2f}",
            "",
            "Preflop:",
            f"  3-bet: {self.three_bet_pct:.1%}  |  Fold to 3-bet: {self.fold_to_3bet:.1%}",
            "",
            "Postflop:",
            f"  C-bet Flop: {self.cbet_flop:.1%}  |  Fold to C-bet: {self.fold_to_cbet_flop:.1%}",
            f"  WTSD: {self.wtsd:.1%}  |  W$SD: {self.w_sd:.1%}",
            "",
        ]
        return "\n".join(lines)


# ========== 工厂函数 ==========

def create_opponent_stats(player_id: str) -> OpponentStats:
    """
    创建新的对手统计实例

    Args:
        player_id: 玩家唯一标识

    Returns:
        初始化的OpponentStats对象
    """
    return OpponentStats(player_id=player_id)
