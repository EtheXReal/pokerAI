"""
玩家分类器 (Player Classifier)

根据统计数据识别9种玩家类型：
1. Nit - 极紧型
2. TAG - 紧凶型
3. Weak Tight - 弱紧型
4. Calling Station - 跟注站
5. LAP - 松被动型
6. Fish - 鱼
7. LAG - 松凶型
8. Maniac - 疯狂型
9. Solid Reg - 稳健常客

分类算法基于：
- VPIP (主动入池率)
- PFR (翻前加注率)
- AF (激进因子)
- 3-bet频率
- WTSD (摊牌率)
- W$SD (摊牌胜率)
"""
from __future__ import annotations

from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

from .models import PlayerType
from .stats import OpponentStats


@dataclass
class ClassificationResult:
    """
    分类结果

    包含分类类型、置信度和理由
    """
    player_type: PlayerType
    confidence: float  # 0.0 - 1.0
    reason: str
    alternative_types: List[Tuple[PlayerType, float]] = None  # 备选类型和置信度

    def __post_init__(self):
        if self.alternative_types is None:
            self.alternative_types = []


class PlayerClassifier:
    """
    玩家分类器

    基于统计数据的规则系统，识别玩家类型
    """

    # 玩家类型特征阈值定义
    TYPE_THRESHOLDS = {
        PlayerType.NIT: {
            'vpip_max': 0.15,
            'pfr_max': 0.12,
            'three_bet_max': 0.05,
            'af_max': 2.0,
        },
        PlayerType.TAG: {
            'vpip_min': 0.15,
            'vpip_max': 0.25,
            'pfr_min': 0.12,
            'pfr_max': 0.20,
            'pfr_vpip_ratio_min': 0.6,
            'af_min': 2.0,
            'three_bet_min': 0.06,
            'three_bet_max': 0.10,
        },
        PlayerType.WEAK_TIGHT: {
            'vpip_max': 0.20,
            'pfr_max': 0.15,
            'af_max': 1.5,
        },
        PlayerType.CALLING_STATION: {
            'vpip_min': 0.30,
            'vpip_max': 0.50,
            'pfr_max': 0.15,
            'af_max': 1.0,
            'wtsd_min': 0.30,
        },
        PlayerType.LAP: {
            'vpip_min': 0.25,
            'vpip_max': 0.40,
            'pfr_max': 0.18,
            'af_max': 1.8,
        },
        PlayerType.FISH: {
            'vpip_min': 0.40,
            'pfr_max': 0.15,
            'af_max': 1.5,
            'wtsd_min': 0.35,
            'w_sd_max': 0.45,
        },
        PlayerType.LAG: {
            'vpip_min': 0.25,
            'vpip_max': 0.40,
            'pfr_min': 0.18,
            'pfr_max': 0.30,
            'af_min': 2.5,
            'three_bet_min': 0.08,
        },
        PlayerType.MANIAC: {
            'vpip_min': 0.45,
            'pfr_min': 0.30,
            'af_min': 3.5,
            'three_bet_min': 0.12,
        },
        PlayerType.SOLID_REG: {
            'vpip_min': 0.20,
            'vpip_max': 0.28,
            'pfr_min': 0.16,
            'pfr_max': 0.24,
            'pfr_vpip_ratio_min': 0.65,
            'pfr_vpip_ratio_max': 0.85,
            'af_min': 2.0,
            'af_max': 3.5,
            'three_bet_min': 0.07,
            'three_bet_max': 0.11,
            'wtsd_min': 0.22,
            'wtsd_max': 0.28,
            'w_sd_min': 0.50,
        },
    }

    # 最小样本量要求
    MIN_HANDS_FOR_CLASSIFICATION = 30
    MIN_HANDS_FOR_HIGH_CONFIDENCE = 100
    MIN_HANDS_FOR_VERY_HIGH_CONFIDENCE = 200

    def __init__(self):
        """初始化分类器"""
        pass

    def classify(self, stats: OpponentStats) -> ClassificationResult:
        """
        分类玩家

        Args:
            stats: 对手统计数据

        Returns:
            分类结果
        """
        # 检查样本量
        if stats.hands_played < self.MIN_HANDS_FOR_CLASSIFICATION:
            return ClassificationResult(
                player_type=PlayerType.UNKNOWN,
                confidence=0.0,
                reason=f"样本量不足 ({stats.hands_played}手 < {self.MIN_HANDS_FOR_CLASSIFICATION}手)"
            )

        # 计算所有类型的匹配分数
        scores = self._calculate_type_scores(stats)

        # 按分数排序
        sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        if not sorted_types or sorted_types[0][1] == 0:
            return ClassificationResult(
                player_type=PlayerType.UNKNOWN,
                confidence=0.0,
                reason="无法匹配任何玩家类型"
            )

        # 最佳匹配
        best_type, best_score = sorted_types[0]

        # 备选类型
        alternatives = [(ptype, score) for ptype, score in sorted_types[1:3] if score > 0.3]

        # 计算置信度
        confidence = self._calculate_confidence(stats, best_score, sorted_types)

        # 生成理由
        reason = self._generate_reason(stats, best_type)

        return ClassificationResult(
            player_type=best_type,
            confidence=confidence,
            reason=reason,
            alternative_types=alternatives
        )

    def _calculate_type_scores(self, stats: OpponentStats) -> Dict[PlayerType, float]:
        """
        计算每种类型的匹配分数

        Returns:
            {PlayerType: score} 分数越高匹配度越好
        """
        scores = {}

        for player_type, thresholds in self.TYPE_THRESHOLDS.items():
            score = self._calculate_single_type_score(stats, thresholds)
            scores[player_type] = score

        return scores

    def _calculate_single_type_score(
        self,
        stats: OpponentStats,
        thresholds: Dict[str, float]
    ) -> float:
        """
        计算单个类型的匹配分数

        使用加权评分系统：
        - 每个满足的条件加分
        - 每个违反的条件减分
        - 核心指标权重更高
        """
        score = 0.0
        total_weight = 0.0

        # 计算PFR/VPIP比率
        pfr_vpip_ratio = stats.pfr / stats.vpip if stats.vpip > 0 else 0.0

        # 指标权重
        weights = {
            'vpip': 2.0,      # 核心指标
            'pfr': 2.0,       # 核心指标
            'af': 1.5,
            'three_bet': 1.0,
            'pfr_vpip_ratio': 1.5,
            'wtsd': 1.0,
            'w_sd': 1.0,
        }

        # 统计值映射
        stat_values = {
            'vpip': stats.vpip,
            'pfr': stats.pfr,
            'af': stats.af,
            'three_bet': stats.three_bet_pct,
            'pfr_vpip_ratio': pfr_vpip_ratio,
            'wtsd': stats.wtsd,
            'w_sd': stats.w_sd,
        }

        # 检查每个阈值
        for key, threshold_value in thresholds.items():
            # 解析键 (e.g., 'vpip_min', 'vpip_max')
            parts = key.rsplit('_', 1)
            if len(parts) != 2:
                continue

            stat_name, bound_type = parts

            if stat_name not in stat_values:
                continue

            stat_value = stat_values[stat_name]
            weight = weights.get(stat_name, 1.0)
            total_weight += weight

            # 检查是否满足阈值
            if bound_type == 'min':
                if stat_value >= threshold_value:
                    score += weight
                else:
                    # 违反最小值，减分（距离越远减分越多）
                    penalty = (threshold_value - stat_value) / max(threshold_value, 0.01)
                    score -= weight * min(penalty, 1.0)

            elif bound_type == 'max':
                if stat_value <= threshold_value:
                    score += weight
                else:
                    # 违反最大值，减分
                    penalty = (stat_value - threshold_value) / max(threshold_value, 0.01)
                    score -= weight * min(penalty, 1.0)

        # 归一化到 [0, 1]
        if total_weight > 0:
            normalized_score = max(0.0, score / total_weight)
        else:
            normalized_score = 0.0

        return normalized_score

    def _calculate_confidence(
        self,
        stats: OpponentStats,
        best_score: float,
        sorted_types: List[Tuple[PlayerType, float]]
    ) -> float:
        """
        计算分类置信度

        考虑因素：
        1. 样本量
        2. 最佳匹配分数
        3. 与次佳类型的差距
        """
        # 基于样本量的置信度
        if stats.hands_played < self.MIN_HANDS_FOR_CLASSIFICATION:
            sample_confidence = 0.0
        elif stats.hands_played < self.MIN_HANDS_FOR_HIGH_CONFIDENCE:
            # 30-100手: 0.5-0.8
            sample_confidence = 0.5 + 0.3 * (
                (stats.hands_played - self.MIN_HANDS_FOR_CLASSIFICATION) /
                (self.MIN_HANDS_FOR_HIGH_CONFIDENCE - self.MIN_HANDS_FOR_CLASSIFICATION)
            )
        elif stats.hands_played < self.MIN_HANDS_FOR_VERY_HIGH_CONFIDENCE:
            # 100-200手: 0.8-0.95
            sample_confidence = 0.8 + 0.15 * (
                (stats.hands_played - self.MIN_HANDS_FOR_HIGH_CONFIDENCE) /
                (self.MIN_HANDS_FOR_VERY_HIGH_CONFIDENCE - self.MIN_HANDS_FOR_HIGH_CONFIDENCE)
            )
        else:
            # 200+手: 0.95
            sample_confidence = 0.95

        # 基于匹配分数的置信度
        score_confidence = best_score

        # 基于与次佳类型差距的置信度
        if len(sorted_types) >= 2:
            second_score = sorted_types[1][1]
            gap = best_score - second_score
            # 差距越大，置信度越高
            gap_confidence = min(1.0, 0.6 + gap * 2.0)
        else:
            gap_confidence = 1.0

        # 综合置信度（加权平均）
        confidence = (
            sample_confidence * 0.4 +
            score_confidence * 0.4 +
            gap_confidence * 0.2
        )

        return min(0.99, confidence)  # 上限99%

    def _generate_reason(self, stats: OpponentStats, player_type: PlayerType) -> str:
        """
        生成分类理由

        说明为什么归类为此类型
        """
        pfr_vpip_ratio = stats.pfr / stats.vpip if stats.vpip > 0 else 0.0

        reasons = {
            PlayerType.NIT: f"极紧型: VPIP={stats.vpip:.1%} (极低), PFR={stats.pfr:.1%} (极低)",
            PlayerType.TAG: f"紧凶型: VPIP={stats.vpip:.1%} (适中), PFR={stats.pfr:.1%} (高), AF={stats.af:.2f} (激进)",
            PlayerType.WEAK_TIGHT: f"弱紧型: VPIP={stats.vpip:.1%} (低), 但AF={stats.af:.2f} (被动)",
            PlayerType.CALLING_STATION: f"跟注站: VPIP={stats.vpip:.1%} (高), PFR={stats.pfr:.1%} (低), WTSD={stats.wtsd:.1%} (高)",
            PlayerType.LAP: f"松被动型: VPIP={stats.vpip:.1%} (较高), 但AF={stats.af:.2f} (被动)",
            PlayerType.FISH: f"鱼: VPIP={stats.vpip:.1%} (过高), 打法差, W$SD={stats.w_sd:.1%} (低)",
            PlayerType.LAG: f"松凶型: VPIP={stats.vpip:.1%} (高), PFR={stats.pfr:.1%} (高), AF={stats.af:.2f} (激进)",
            PlayerType.MANIAC: f"疯狂型: VPIP={stats.vpip:.1%} (极高), PFR={stats.pfr:.1%} (极高), 极度激进",
            PlayerType.SOLID_REG: f"稳健常客: 平衡打法, PFR/VPIP={pfr_vpip_ratio:.2f}, W$SD={stats.w_sd:.1%} (盈利)",
        }

        return reasons.get(player_type, f"未知类型")

    def get_exploitation_hints(self, player_type: PlayerType) -> List[str]:
        """
        获取针对性策略提示

        Args:
            player_type: 玩家类型

        Returns:
            策略提示列表
        """
        hints = {
            PlayerType.NIT: [
                "他们很少入池，只玩强牌",
                "可以经常偷盲",
                "如果他们加注，要小心",
                "在他们面前可以放心诈唬",
            ],
            PlayerType.TAG: [
                "尊重他们的加注",
                "注意位置优势",
                "不要频繁诈唬",
                "在有位置时可以3-bet施压",
            ],
            PlayerType.WEAK_TIGHT: [
                "可以经常偷盲",
                "他们容易被激进打法吓到",
                "翻后可以多诈唬",
                "利用他们的被动性",
            ],
            PlayerType.CALLING_STATION: [
                "不要诈唬！他们会一直跟注",
                "价值下注要大",
                "只在有强牌时下注",
                "避免复杂的诈唬线",
            ],
            PlayerType.LAP: [
                "价值下注",
                "小心诈唬（他们会跟注）",
                "在有牌时下大注",
                "翻前可以隔离加注",
            ],
            PlayerType.FISH: [
                "持续价值下注",
                "不要诈唬",
                "耐心等待强牌",
                "翻前隔离加注",
                "保持简单直接的打法",
            ],
            PlayerType.LAG: [
                "需要更宽的范围对抗",
                "不要被吓到",
                "有强牌时慢打",
                "选择性3-bet",
                "准备好大波动",
            ],
            PlayerType.MANIAC: [
                "需要非常宽的范围",
                "耐心等待中等牌力",
                "让他们持续激进",
                "有对子/顶对就可以价值",
                "避免诈唬（他们会加注）",
            ],
            PlayerType.SOLID_REG: [
                "避免正面对抗",
                "寻找软弱玩家",
                "注意他们的调整",
                "保持不可预测",
                "利用位置优势",
            ],
            PlayerType.UNKNOWN: [
                "收集更多数据",
                "使用默认策略",
                "观察他们的行为模式",
            ],
        }

        return hints.get(player_type, ["需要更多数据"])


# ========== 辅助函数 ==========

def classify_player(stats: OpponentStats) -> ClassificationResult:
    """
    分类玩家的便捷函数

    Args:
        stats: 对手统计

    Returns:
        分类结果
    """
    classifier = PlayerClassifier()
    return classifier.classify(stats)


def get_player_type_name(player_type: PlayerType) -> str:
    """
    获取玩家类型的中文名称

    Args:
        player_type: 玩家类型

    Returns:
        中文名称
    """
    names = {
        PlayerType.NIT: "极紧型 (Nit)",
        PlayerType.TAG: "紧凶型 (TAG)",
        PlayerType.WEAK_TIGHT: "弱紧型 (Weak Tight)",
        PlayerType.CALLING_STATION: "跟注站 (Calling Station)",
        PlayerType.LAP: "松被动型 (LAP)",
        PlayerType.FISH: "鱼 (Fish)",
        PlayerType.LAG: "松凶型 (LAG)",
        PlayerType.MANIAC: "疯狂型 (Maniac)",
        PlayerType.SOLID_REG: "稳健常客 (Solid Reg)",
        PlayerType.UNKNOWN: "未知 (Unknown)",
    }
    return names.get(player_type, "未知")
