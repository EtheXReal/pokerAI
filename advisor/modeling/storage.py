"""
持久化存储 (Persistent Storage)

核心功能:
1. SQLite数据库存储对手统计
2. 支持完整的序列化/反序列化
3. 自动时间戳追踪
4. 跨session数据保留

设计原则:
- 抽象StorageBackend接口（方便未来扩展）
- SQLiteStorage具体实现
- 线程安全的数据库操作
- 自动创建schema
"""
from __future__ import annotations

import sqlite3
import json
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
from abc import ABC, abstractmethod

from .stats import OpponentStats


class StorageBackend(ABC):
    """
    存储后端抽象接口

    定义统一的存储接口，方便未来扩展到其他数据库
    （PostgreSQL, MongoDB等）
    """

    @abstractmethod
    def save_stats(self, stats: OpponentStats) -> bool:
        """
        保存对手统计

        Args:
            stats: OpponentStats对象

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def load_stats(self, player_id: str) -> Optional[OpponentStats]:
        """
        加载对手统计

        Args:
            player_id: 玩家ID

        Returns:
            OpponentStats对象，如果不存在返回None
        """
        pass

    @abstractmethod
    def delete_stats(self, player_id: str) -> bool:
        """
        删除对手统计

        Args:
            player_id: 玩家ID

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def list_all_players(self) -> List[str]:
        """
        列出所有已追踪的玩家

        Returns:
            玩家ID列表
        """
        pass

    @abstractmethod
    def clear_all(self) -> bool:
        """
        清空所有数据

        Returns:
            是否成功
        """
        pass


class SQLiteStorage(StorageBackend):
    """
    SQLite存储实现

    使用单表存储所有统计数据，JSON字段存储复杂结构
    """

    # 数据库schema版本
    SCHEMA_VERSION = 1

    def __init__(self, db_path: str = "opponent_stats.db"):
        """
        初始化SQLite存储

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self._init_database()

    def _init_database(self) -> None:
        """初始化数据库，创建表结构"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # 创建统计表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS opponent_stats (
                player_id TEXT PRIMARY KEY,
                hands_played INTEGER NOT NULL,

                -- 基础指标
                vpip REAL NOT NULL,
                pfr REAL NOT NULL,
                af REAL NOT NULL,
                overall_agg REAL NOT NULL,

                -- 翻前指标
                three_bet_pct REAL NOT NULL,
                four_bet_pct REAL NOT NULL,
                fold_to_3bet REAL NOT NULL,
                call_3bet REAL NOT NULL,
                fold_to_steal REAL NOT NULL,
                open_raise_first_in REAL NOT NULL,
                limp_first_in REAL NOT NULL,

                -- 翻后指标
                cbet_flop REAL NOT NULL,
                cbet_turn REAL NOT NULL,
                cbet_river REAL NOT NULL,
                fold_to_cbet_flop REAL NOT NULL,
                fold_to_cbet_turn REAL NOT NULL,
                raise_cbet REAL NOT NULL,

                -- 进攻性指标
                wtsd REAL NOT NULL,
                w_sd REAL NOT NULL,
                agg_flop REAL NOT NULL,
                agg_turn REAL NOT NULL,
                agg_river REAL NOT NULL,

                -- 特殊指标
                check_raise_freq REAL NOT NULL,
                donk_bet_freq REAL NOT NULL,
                float_freq REAL NOT NULL,

                -- 位置统计 (JSON)
                position_stats TEXT,

                -- 街道统计 (JSON)
                streets_stats TEXT,

                -- 内部计数器 (JSON)
                internal_counters TEXT,

                -- 时间戳
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                -- schema版本
                schema_version INTEGER NOT NULL
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_updated_at
            ON opponent_stats(updated_at)
        """)

        conn.commit()
        conn.close()

    def save_stats(self, stats: OpponentStats) -> bool:
        """
        保存对手统计

        使用INSERT OR REPLACE实现upsert操作
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # 序列化复杂结构
            stats_dict = stats.to_dict()

            # 提取内部计数器
            internal_counters = {
                'vpip_opportunities': stats_dict.get('_vpip_opportunities', 0),
                'pfr_opportunities': stats_dict.get('_pfr_opportunities', 0),
                'three_bet_opportunities': stats_dict.get('_three_bet_opportunities', 0),
                'faced_3bet_count': stats_dict.get('_faced_3bet_count', 0),
                'cbet_opportunities': stats_dict.get('_cbet_opportunities', 0),
                'faced_cbet_count': stats_dict.get('_faced_cbet_count', 0),
                'saw_flop_count': stats_dict.get('_saw_flop_count', 0),
                'showdown_count': stats_dict.get('_showdown_count', 0),
                'won_showdown_count': stats_dict.get('_won_showdown_count', 0),
                'aggressive_actions': stats_dict.get('_aggressive_actions', 0),
                'passive_actions': stats_dict.get('_passive_actions', 0),
                'check_raise_opportunities': stats_dict.get('_check_raise_opportunities', 0),
                'check_raises': stats_dict.get('_check_raises', 0),
            }

            now = datetime.utcnow().isoformat()

            cursor.execute("""
                INSERT OR REPLACE INTO opponent_stats (
                    player_id, hands_played,
                    vpip, pfr, af, overall_agg,
                    three_bet_pct, four_bet_pct, fold_to_3bet, call_3bet,
                    fold_to_steal, open_raise_first_in, limp_first_in,
                    cbet_flop, cbet_turn, cbet_river,
                    fold_to_cbet_flop, fold_to_cbet_turn, raise_cbet,
                    wtsd, w_sd, agg_flop, agg_turn, agg_river,
                    check_raise_freq, donk_bet_freq, float_freq,
                    position_stats, streets_stats, internal_counters,
                    created_at, updated_at, schema_version
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    COALESCE(
                        (SELECT created_at FROM opponent_stats WHERE player_id = ?),
                        ?
                    ),
                    ?, ?
                )
            """, (
                stats.player_id,
                stats.hands_played,
                stats.vpip,
                stats.pfr,
                stats.af,
                stats.overall_agg,
                stats.three_bet_pct,
                stats.four_bet_pct,
                stats.fold_to_3bet,
                stats.call_3bet,
                stats.fold_to_steal,
                stats.open_raise_first_in,
                stats.limp_first_in,
                stats.cbet_flop,
                stats.cbet_turn,
                stats.cbet_river,
                stats.fold_to_cbet_flop,
                stats.fold_to_cbet_turn,
                stats.raise_cbet,
                stats.wtsd,
                stats.w_sd,
                stats.agg_flop,
                stats.agg_turn,
                stats.agg_river,
                stats.check_raise_freq,
                stats.donk_bet_freq,
                stats.float_freq,
                json.dumps(stats_dict.get('position_stats', {})),
                json.dumps(stats_dict.get('streets_stats', {})),
                json.dumps(internal_counters),
                stats.player_id,  # for COALESCE
                now,  # created_at default
                now,  # updated_at
                self.SCHEMA_VERSION,
            ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error saving stats for {stats.player_id}: {e}")
            return False

    def load_stats(self, player_id: str) -> Optional[OpponentStats]:
        """
        加载对手统计

        从数据库恢复完整的OpponentStats对象
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row  # 使用Row对象方便访问
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM opponent_stats WHERE player_id = ?
            """, (player_id,))

            row = cursor.fetchone()
            conn.close()

            if row is None:
                return None

            # 解析JSON字段
            position_stats = json.loads(row['position_stats'])
            streets_stats = json.loads(row['streets_stats'])
            internal_counters = json.loads(row['internal_counters'])

            # 重建完整的字典
            stats_dict = {
                'player_id': row['player_id'],
                'hands_played': row['hands_played'],
                'vpip': row['vpip'],
                'pfr': row['pfr'],
                'af': row['af'],
                'overall_agg': row['overall_agg'],
                'three_bet_pct': row['three_bet_pct'],
                'four_bet_pct': row['four_bet_pct'],
                'fold_to_3bet': row['fold_to_3bet'],
                'call_3bet': row['call_3bet'],
                'fold_to_steal': row['fold_to_steal'],
                'open_raise_first_in': row['open_raise_first_in'],
                'limp_first_in': row['limp_first_in'],
                'cbet_flop': row['cbet_flop'],
                'cbet_turn': row['cbet_turn'],
                'cbet_river': row['cbet_river'],
                'fold_to_cbet_flop': row['fold_to_cbet_flop'],
                'fold_to_cbet_turn': row['fold_to_cbet_turn'],
                'raise_cbet': row['raise_cbet'],
                'wtsd': row['wtsd'],
                'w_sd': row['w_sd'],
                'agg_flop': row['agg_flop'],
                'agg_turn': row['agg_turn'],
                'agg_river': row['agg_river'],
                'check_raise_freq': row['check_raise_freq'],
                'donk_bet_freq': row['donk_bet_freq'],
                'float_freq': row['float_freq'],
                'position_stats': position_stats,
                'streets_stats': streets_stats,
                # 内部计数器
                '_vpip_opportunities': internal_counters.get('vpip_opportunities', 0),
                '_pfr_opportunities': internal_counters.get('pfr_opportunities', 0),
                '_three_bet_opportunities': internal_counters.get('three_bet_opportunities', 0),
                '_faced_3bet_count': internal_counters.get('faced_3bet_count', 0),
                '_cbet_opportunities': internal_counters.get('cbet_opportunities', 0),
                '_faced_cbet_count': internal_counters.get('faced_cbet_count', 0),
                '_saw_flop_count': internal_counters.get('saw_flop_count', 0),
                '_showdown_count': internal_counters.get('showdown_count', 0),
                '_won_showdown_count': internal_counters.get('won_showdown_count', 0),
                '_aggressive_actions': internal_counters.get('aggressive_actions', 0),
                '_passive_actions': internal_counters.get('passive_actions', 0),
                '_check_raise_opportunities': internal_counters.get('check_raise_opportunities', 0),
                '_check_raises': internal_counters.get('check_raises', 0),
            }

            # 从字典恢复OpponentStats对象
            return OpponentStats.from_dict(stats_dict)

        except Exception as e:
            print(f"Error loading stats for {player_id}: {e}")
            return None

    def delete_stats(self, player_id: str) -> bool:
        """删除对手统计"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM opponent_stats WHERE player_id = ?
            """, (player_id,))

            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()

            return deleted

        except Exception as e:
            print(f"Error deleting stats for {player_id}: {e}")
            return False

    def list_all_players(self) -> List[str]:
        """列出所有已追踪的玩家"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("""
                SELECT player_id FROM opponent_stats ORDER BY updated_at DESC
            """)

            players = [row[0] for row in cursor.fetchall()]
            conn.close()

            return players

        except Exception as e:
            print(f"Error listing players: {e}")
            return []

    def clear_all(self) -> bool:
        """清空所有数据"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("DELETE FROM opponent_stats")

            conn.commit()
            conn.close()

            return True

        except Exception as e:
            print(f"Error clearing all data: {e}")
            return False

    def get_stats_count(self) -> int:
        """获取统计数量"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM opponent_stats")
            count = cursor.fetchone()[0]

            conn.close()
            return count

        except Exception as e:
            print(f"Error getting stats count: {e}")
            return 0

    def get_database_info(self) -> Dict[str, Any]:
        """获取数据库信息"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # 统计总数
            cursor.execute("SELECT COUNT(*) FROM opponent_stats")
            total_players = cursor.fetchone()[0]

            # 总手数
            cursor.execute("SELECT SUM(hands_played) FROM opponent_stats")
            total_hands = cursor.fetchone()[0] or 0

            # 数据库文件大小
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

            # 最近更新时间
            cursor.execute("""
                SELECT updated_at FROM opponent_stats
                ORDER BY updated_at DESC LIMIT 1
            """)
            result = cursor.fetchone()
            last_update = result[0] if result else None

            conn.close()

            return {
                'db_path': str(self.db_path),
                'total_players': total_players,
                'total_hands': total_hands,
                'db_size_bytes': db_size,
                'db_size_kb': db_size / 1024,
                'last_update': last_update,
                'schema_version': self.SCHEMA_VERSION,
            }

        except Exception as e:
            print(f"Error getting database info: {e}")
            return {}

    def __repr__(self) -> str:
        """字符串表示"""
        info = self.get_database_info()
        return (
            f"SQLiteStorage("
            f"path={info.get('db_path', 'unknown')}, "
            f"players={info.get('total_players', 0)}, "
            f"hands={info.get('total_hands', 0)})"
        )


# ========== 辅助函数 ==========

def create_storage(db_path: str = "opponent_stats.db") -> SQLiteStorage:
    """
    创建存储后端的工厂函数

    Args:
        db_path: 数据库文件路径

    Returns:
        SQLiteStorage实例
    """
    return SQLiteStorage(db_path=db_path)
