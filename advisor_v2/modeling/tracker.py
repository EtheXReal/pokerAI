"""
统计追踪器 (Stats Tracker)

核心功能:
1. 管理多个玩家的统计数据
2. 从手牌历史自动解析和更新统计
3. 识别特殊行动 (c-bet, 3-bet, check-raise等)
4. 内存缓存 + 可选持久化

设计原则:
- 自动从游戏引擎输出的手牌历史提取信息
- 支持多玩家同时追踪
- 高效的增量更新
- 可扩展的存储后端
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
import json

from .stats import OpponentStats, create_opponent_stats
from .models import (
    HandResult,
    ActionRecord,
    ActionType,
    StreetType,
    PositionType,
    parse_street,
    parse_position,
    classify_action
)


class ActionParser:
    """
    行动序列解析器

    从原始的手牌历史中识别和提取关键信息:
    - 谁是翻前加注者 (PFR)
    - 谁进行了c-bet
    - 谁进行了3-bet/4-bet
    - 谁进行了check-raise
    - 等等
    """

    @staticmethod
    def parse_hand_actions(actions: List[dict], player_id: str) -> HandResult:
        """
        解析单手牌的行动序列，提取该玩家的统计信息

        Args:
            actions: 行动列表，每个元素为 {street, actor, action, amount, ...}
            player_id: 目标玩家ID

        Returns:
            HandResult对象，包含该手牌的统计信息
        """
        # 初始化结果
        result = HandResult(
            hand_id="",  # 由调用者填充
            position=PositionType.UNKNOWN,
            vpip=False,
            pfr=False,
        )

        # 解析行动序列
        preflop_actions = []
        flop_actions = []
        turn_actions = []
        river_actions = []

        preflop_raiser = None
        last_raiser_by_street = {}
        player_position = PositionType.UNKNOWN

        for action in actions:
            actor = action.get('actor', '')
            street_str = action.get('street', 'preflop')
            action_type_str = action.get('action', 'fold')
            amount = action.get('amount', 0.0)

            street = parse_street(street_str)
            action_type = classify_action(action_type_str)

            # 记录该玩家的位置
            if actor == player_id and 'position' in action:
                player_position = parse_position(action.get('position', 'UNKNOWN'))

            # 记录行动
            action_record = ActionRecord(
                street=street,
                position=player_position,
                action=action_type,
                amount=amount,
                pot_size=action.get('pot_before', 0.0),
                facing_bet=action.get('to_call', 0.0),
            )

            # 按街道分组
            if street == StreetType.PREFLOP:
                preflop_actions.append((actor, action_type, amount))
            elif street == StreetType.FLOP:
                flop_actions.append((actor, action_type, amount))
            elif street == StreetType.TURN:
                turn_actions.append((actor, action_type, amount))
            elif street == StreetType.RIVER:
                river_actions.append((actor, action_type, amount))

            # 追踪加注者
            if action_type in [ActionType.RAISE, ActionType.BET]:
                last_raiser_by_street[street] = actor
                if street == StreetType.PREFLOP and preflop_raiser is None:
                    preflop_raiser = actor

            # 如果是目标玩家，记录行动
            if actor == player_id:
                result.actions.append(action_record)

        # 分析翻前行动
        result.position = player_position
        result.vpip, result.pfr, result.faced_raise, result.three_bet, result.four_bet = (
            ActionParser._analyze_preflop(player_id, preflop_actions)
        )

        # 分析翻后行动
        # 判断玩家是否saw_flop：手牌进入flop且玩家没有翻前fold
        if len(flop_actions) > 0:
            # 检查玩家是否翻前fold
            player_folded_preflop = False
            for actor, action_type, amount in preflop_actions:
                if actor == player_id and action_type == ActionType.FOLD:
                    player_folded_preflop = True
                    break

            # 如果没有翻前fold，说明saw_flop
            if not player_folded_preflop:
                result.saw_flop = True

                # C-bet分析: 翻前加注者在翻牌圈下注
                if preflop_raiser == player_id:
                    result.cbet_flop = ActionParser._did_cbet(
                        player_id, flop_actions
                    )

                # Fold to C-bet分析: 面对翻前加注者的翻牌圈下注
                if preflop_raiser and preflop_raiser != player_id:
                    result.fold_to_cbet = ActionParser._did_fold_to_cbet(
                        player_id, preflop_raiser, flop_actions
                    )

        # 摊牌分析 (需要从外部传入)
        # result.went_to_showdown 和 won_at_showdown 需要由调用者填充

        return result

    @staticmethod
    def _analyze_preflop(
        player_id: str,
        actions: List[Tuple[str, ActionType, float]]
    ) -> Tuple[bool, bool, bool, bool, bool]:
        """
        分析翻前行动

        Returns:
            (vpip, pfr, faced_raise, three_bet, four_bet)
        """
        vpip = False
        pfr = False
        faced_raise = False
        three_bet = False
        four_bet = False

        raise_count = 0  # 整个翻前的总加注次数
        player_raised = False

        for actor, action_type, amount in actions:
            if action_type in [ActionType.RAISE, ActionType.BET]:
                raise_count += 1

            if actor == player_id:
                # 检查是否面对raise
                if raise_count > 0 and not player_raised:
                    faced_raise = True

                # VPIP: 主动投钱 (不包括BB)
                if action_type in [ActionType.CALL, ActionType.RAISE, ActionType.BET]:
                    vpip = True

                # PFR: 加注
                if action_type in [ActionType.RAISE, ActionType.BET]:
                    pfr = True
                    player_raised = True

                    # 3-bet: 第二次加注
                    if raise_count == 2:
                        three_bet = True
                    # 4-bet: 第三次加注
                    elif raise_count == 3:
                        four_bet = True

        return vpip, pfr, faced_raise, three_bet, four_bet

    @staticmethod
    def _did_cbet(
        player_id: str,
        actions: List[Tuple[str, ActionType, float]]
    ) -> bool:
        """
        判断玩家是否在该街道进行了c-bet

        C-bet定义: 翻前加注者在翻后第一个主动下注
        """
        for actor, action_type, amount in actions:
            if action_type in [ActionType.BET, ActionType.RAISE]:
                return actor == player_id
            elif action_type == ActionType.CHECK:
                continue
            else:
                # 其他行动 (call/fold) 意味着已经有人下注了
                break
        return False

    @staticmethod
    def _did_fold_to_cbet(
        player_id: str,
        preflop_raiser: str,
        actions: List[Tuple[str, ActionType, float]]
    ) -> Optional[bool]:
        """
        判断玩家是否面对C-bet并fold

        Args:
            player_id: 目标玩家ID
            preflop_raiser: 翻前加注者ID
            actions: 翻牌圈行动序列

        Returns:
            True: 面对C-bet并fold
            False: 面对C-bet但没有fold（call或raise）
            None: 没有面对C-bet的机会
        """
        # 首先检查翻前加注者是否C-bet
        cbet_happened = False
        player_acted_after_cbet = False

        for actor, action_type, amount in actions:
            # 检查是否是翻前加注者的C-bet
            if actor == preflop_raiser and action_type in [ActionType.BET, ActionType.RAISE]:
                cbet_happened = True
                continue

            # 如果C-bet已经发生，检查玩家的响应
            if cbet_happened and actor == player_id:
                player_acted_after_cbet = True
                # 玩家面对C-bet的行动
                if action_type == ActionType.FOLD:
                    return True  # Fold to C-bet
                elif action_type in [ActionType.CALL, ActionType.RAISE]:
                    return False  # 没有fold
                # 如果是check，说明不是面对C-bet（可能是后位）
                break

        # 如果没有C-bet发生，或玩家没有机会响应，返回None
        return None


class StatsTracker:
    """
    统计追踪器

    管理多个玩家的统计数据，自动从手牌历史更新
    """

    def __init__(self, storage_backend: Optional[object] = None):
        """
        初始化追踪器

        Args:
            storage_backend: 可选的存储后端 (用于持久化)
        """
        # 内存缓存: player_id -> OpponentStats
        self._stats: Dict[str, OpponentStats] = {}

        # 存储后端 (后续实现)
        self._storage = storage_backend

        # 已处理的手牌ID (避免重复处理)
        self._processed_hands: Set[str] = set()

    def get_stats(self, player_id: str) -> OpponentStats:
        """
        获取玩家统计

        如果玩家不存在，自动创建新的统计对象

        Args:
            player_id: 玩家唯一标识

        Returns:
            OpponentStats对象
        """
        if player_id not in self._stats:
            # 尝试从存储加载
            if self._storage is not None:
                loaded_stats = self._storage.load_stats(player_id)
                if loaded_stats is not None:
                    self._stats[player_id] = loaded_stats
                    return loaded_stats

            # 创建新的统计
            self._stats[player_id] = create_opponent_stats(player_id)

        return self._stats[player_id]

    def update_from_hand(self, hand_history: dict) -> None:
        """
        从单手牌历史更新所有玩家的统计

        Args:
            hand_history: 手牌历史字典，包含:
                - hand_id: 手牌ID
                - players: 玩家列表 [{id, position, stack_start, ...}]
                - actions: 行动列表 [{street, actor, action, amount, ...}]
                - winners: 赢家列表 [{seat, amount}]
                - showdown: 是否摊牌
        """
        hand_id = hand_history.get('hand_id', '')

        # 避免重复处理
        if hand_id in self._processed_hands:
            return

        players = hand_history.get('players', [])
        actions = hand_history.get('actions', [])
        winners = hand_history.get('winners', [])
        showdown = hand_history.get('showdown', False)

        # 为每个玩家解析手牌结果
        for player in players:
            player_id = player.get('id', player.get('seat', ''))
            if not player_id:
                continue

            # 解析行动序列
            hand_result = ActionParser.parse_hand_actions(actions, player_id)
            hand_result.hand_id = hand_id
            hand_result.position = parse_position(player.get('pos', 'UNKNOWN'))

            # 补充摊牌信息
            # BUG FIX: 只有实际参与摊牌的玩家才标记went_to_showdown=True
            # 不能简单地用整手牌的showdown状态应用到所有玩家
            if showdown:
                # 判断该玩家是否真的went_to_showdown:
                # 1. 玩家在winners列表中（无论是否赢）
                # 2. 或者玩家的最后一个action在river街道且不是fold
                player_went_to_showdown = False

                # 方法1: 检查是否在winners中
                for winner in winners:
                    if winner.get('seat', '') == player_id:
                        player_went_to_showdown = True
                        # 检查是否赢得摊牌
                        if winner.get('amount', 0) > 0:
                            hand_result.won_at_showdown = True
                        break

                # 方法2: 如果winners只包含赢家，我们需要检查玩家的行动
                # 查找玩家的最后一个action
                if not player_went_to_showdown:
                    last_action_street = None
                    last_action_type = None
                    for action in reversed(actions):
                        if action.get('actor', '') == player_id:
                            last_action_street = action.get('street', '')
                            last_action_type = action.get('action', '')
                            break

                    # 如果最后action在river且不是fold，说明去了摊牌
                    if last_action_street == 'river' and last_action_type != 'fold':
                        player_went_to_showdown = True
                    # 或者如果玩家在flop/turn有action但没fold，且game到了showdown
                    elif last_action_type and last_action_type != 'fold':
                        # 这种情况需要检查游戏是否真的到了river
                        # 简化：如果整手牌showdown且玩家最后不是fold，认为went_to_showdown
                        player_went_to_showdown = True

                hand_result.went_to_showdown = player_went_to_showdown
            else:
                hand_result.went_to_showdown = False

            # 更新统计
            stats = self.get_stats(player_id)
            stats.update_from_hand(hand_result)

        # 标记已处理
        self._processed_hands.add(hand_id)

        # 持久化 (如果有存储后端)
        if self._storage is not None:
            for player in players:
                player_id = player.get('id', player.get('seat', ''))
                if player_id in self._stats:
                    self._storage.save_stats(self._stats[player_id])

    def update_from_hands(self, hand_histories: List[dict]) -> None:
        """
        批量更新多手牌历史

        Args:
            hand_histories: 手牌历史列表
        """
        for hand_history in hand_histories:
            self.update_from_hand(hand_history)

    def get_all_stats(self) -> Dict[str, OpponentStats]:
        """
        获取所有玩家的统计

        Returns:
            字典: player_id -> OpponentStats
        """
        return self._stats.copy()

    def get_player_count(self) -> int:
        """获取追踪的玩家数量"""
        return len(self._stats)

    def clear_stats(self, player_id: Optional[str] = None) -> None:
        """
        清空统计数据

        Args:
            player_id: 如果指定，只清空该玩家的数据；否则清空所有
        """
        if player_id is not None:
            if player_id in self._stats:
                del self._stats[player_id]
        else:
            self._stats.clear()
            self._processed_hands.clear()

    def export_to_dict(self) -> dict:
        """
        导出所有统计为字典 (用于序列化)

        Returns:
            包含所有玩家统计的字典
        """
        return {
            'players': {
                player_id: stats.to_dict()
                for player_id, stats in self._stats.items()
            },
            'processed_hands': list(self._processed_hands)
        }

    def export_to_json(self) -> str:
        """导出为JSON字符串"""
        return json.dumps(self.export_to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> 'StatsTracker':
        """
        从字典创建追踪器

        Args:
            data: 包含统计数据的字典

        Returns:
            StatsTracker实例
        """
        tracker = cls()

        # 加载玩家统计
        players_data = data.get('players', {})
        for player_id, stats_dict in players_data.items():
            tracker._stats[player_id] = OpponentStats.from_dict(stats_dict)

        # 加载已处理手牌
        processed_hands = data.get('processed_hands', [])
        tracker._processed_hands = set(processed_hands)

        return tracker

    def __repr__(self) -> str:
        """简洁的字符串表示"""
        return (
            f"StatsTracker("
            f"players={self.get_player_count()}, "
            f"hands_processed={len(self._processed_hands)})"
        )

    def summary(self) -> str:
        """
        详细摘要

        Returns:
            多行字符串，包含所有玩家的统计摘要
        """
        lines = [
            "=== StatsTracker Summary ===",
            f"Total Players Tracked: {self.get_player_count()}",
            f"Total Hands Processed: {len(self._processed_hands)}",
            "",
        ]

        if self._stats:
            lines.append("Player Statistics:")
            for player_id, stats in sorted(self._stats.items()):
                confidence = stats.get_confidence()
                lines.append(
                    f"  {player_id}: "
                    f"{stats.hands_played} hands, "
                    f"VPIP={stats.vpip:.1%}, "
                    f"PFR={stats.pfr:.1%}, "
                    f"AF={stats.af:.2f}, "
                    f"confidence={confidence:.0%}"
                )

        return "\n".join(lines)


# ========== 辅助函数 ==========

def create_tracker(storage_backend: Optional[object] = None) -> StatsTracker:
    """
    创建统计追踪器的工厂函数

    Args:
        storage_backend: 可选的存储后端

    Returns:
        StatsTracker实例
    """
    return StatsTracker(storage_backend=storage_backend)
