"""
Model接口定义

Model Layer负责对手建模，包括：
1. 玩家分类（LAG, TAG, PASSIVE等）
2. 构建玩家画像（VPIP, PFR, 各种趋势）
3. 实时更新观察
4. 基于profile预测range
"""

from abc import ABC, abstractmethod
from typing import Optional
from advisor_v2.core.data_structures import PlayerProfile, PlayerType, Action
from advisor_v2.core.data_structures import Position
from poker_core.range import Range


class IOpponentModel(ABC):
    """
    对手模型接口

    关键改进：
    - 不再返回UNKNOWN（即使样本少也尝试分类）
    - 实时更新（每个action都更新profile）
    - 置信度评估（用于GTO-Exploit平衡）
    """

    @abstractmethod
    def classify_player(self, player_id: str) -> PlayerType:
        """
        分类玩家类型

        基于统计数据（VPIP, PFR, AF）分类。

        Args:
            player_id: 玩家ID

        Returns:
            PlayerType (LAG, TAG, LOOSE_PASSIVE, TIGHT_PASSIVE, NORMAL, etc.)

        分类标准：
        - LAG: VPIP >= 35%, PFR >= 25%, AF >= 2.5
        - TAG: VPIP <= 18%, PFR >= 12%, AF >= 2.0
        - LOOSE_PASSIVE: VPIP >= 35%, AF < 1.5
        - TIGHT_PASSIVE: VPIP <= 18%, AF < 1.5
        - NORMAL: 其他

        注意：
        - 即使样本量少（<10 hands），也尝试分类（基于初始假设）
        - 不再返回UNKNOWN（UNKNOWN会导致exploit layer死亡）
        - 置信度低时，分类为NORMAL（最保守）
        """
        pass

    @abstractmethod
    def get_profile(self, player_id: str) -> PlayerProfile:
        """
        获取完整的玩家画像

        Args:
            player_id: 玩家ID

        Returns:
            PlayerProfile对象，包含：
            - player_type: 玩家类型
            - vpip, pfr, af: 基础统计
            - cbet_freq_flop/turn/river: C-bet频率
            - fold_to_cbet_flop/turn/river: 对C-bet的弃牌率
            - three_bet_freq, fold_to_3bet: 3-bet相关
            - sample_size, confidence: 样本量和可靠性

        如果玩家未见过，返回默认profile（NORMAL类型）。
        """
        pass

    @abstractmethod
    def update_observation(self, player_id: str, action: Action, context: dict):
        """
        实时更新观察

        每次对手有action，都调用此方法更新profile。

        Args:
            player_id: 玩家ID
            action: 对手的action
            context: 上下文信息，包含：
                - street: 'preflop', 'flop', 'turn', 'river'
                - position: 对手位置
                - pot_size: 当前pot大小
                - facing_bet: 是否面对bet
                - is_open: 是否是开池action
                - is_3bet: 是否是3-bet
                等等

        Example:
            # BTN open to 3BB
            update_observation('player_123', Action('raise', 3.0), {
                'street': 'preflop',
                'position': Position.BTN,
                'pot_size': 1.5,
                'facing_bet': False,
                'is_open': True
            })

            # Flop cbet
            update_observation('player_123', Action('bet', 4.5), {
                'street': 'flop',
                'position': Position.BTN,
                'pot_size': 7.0,
                'facing_bet': False
            })
        """
        pass

    @abstractmethod
    def predict_range(self, player_id: str, position: Position,
                     action_history: list) -> Range:
        """
        基于profile预测对手range

        Args:
            player_id: 玩家ID
            position: 对手位置
            action_history: 行动历史

        Returns:
            预测的range

        逻辑：
        1. 获取GTO baseline range
        2. 根据player_type调整：
           - LAG: 扩大range（+30-50%）
           - TAG: 缩小range（-10-20%）
           - TIGHT_PASSIVE: 缩小并线性化
           - LOOSE_PASSIVE: 扩大并线性化
        3. 根据具体tendencies微调（如cbet_freq）

        Example:
            # Unknown player, BTN open
            predict_range('new_player', Position.BTN, [Action('raise', 3.0)])
            # 返回：标准BTN open range

            # Known LAG, BTN open (VPIP=38%, PFR=30%)
            predict_range('lag_player', Position.BTN, [Action('raise', 3.0)])
            # 返回：扩大40%的range（因为LAG开得更宽）
        """
        pass

    @abstractmethod
    def reset_player(self, player_id: str):
        """
        重置玩家数据

        用于：
        - 开始新session
        - 玩家行为明显变化（手动重置）
        """
        pass

    @abstractmethod
    def get_all_profiles(self) -> dict:
        """
        获取所有玩家的profile

        Returns:
            {player_id: PlayerProfile, ...}

        用于：
        - 数据持久化
        - 分析和调试
        """
        pass

    @abstractmethod
    def save_profiles(self, filepath: str):
        """保存profiles到文件"""
        pass

    @abstractmethod
    def load_profiles(self, filepath: str):
        """从文件加载profiles"""
        pass
