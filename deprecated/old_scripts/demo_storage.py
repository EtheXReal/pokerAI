#!/usr/bin/env python
"""
存储系统演示脚本

展示SQLite持久化存储的完整工作流程：
1. 创建和配置存储后端
2. 保存对手统计到数据库
3. 跨session加载数据
4. 与StatsTracker集成
5. 数据库管理功能
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from advisor.opponent_modeling import (
    create_opponent_stats,
    create_storage,
    create_tracker,
    HandResult,
    PositionType,
)


def print_section(title: str):
    """打印章节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def demo_basic_storage():
    """演示基础存储功能"""
    print_section("演示 1: 基础存储功能")

    # 创建存储
    print("\n创建SQLite存储后端...")
    storage = create_storage("demo_opponent_stats.db")
    print(f"✓ 存储创建成功: {storage}")

    # 创建统计
    print("\n创建玩家统计...")
    stats = create_opponent_stats("Alice")
    stats.hands_played = 100
    stats.vpip = 0.28
    stats.pfr = 0.22
    stats.af = 2.3
    stats.three_bet_pct = 0.08
    stats.cbet_flop = 0.70
    stats.wtsd = 0.24
    stats.w_sd = 0.52
    print(f"✓ 统计创建: {stats.player_id}, {stats.hands_played}手")

    # 保存
    print("\n保存到数据库...")
    success = storage.save_stats(stats)
    print(f"✓ 保存{'成功' if success else '失败'}")

    # 加载
    print("\n从数据库加载...")
    loaded = storage.load_stats("Alice")
    if loaded:
        print(f"✓ 加载成功: {loaded.player_id}")
        print(f"  - 手数: {loaded.hands_played}")
        print(f"  - VPIP: {loaded.vpip:.1%}")
        print(f"  - PFR: {loaded.pfr:.1%}")
        print(f"  - AF: {loaded.af:.2f}")

    # 列出所有玩家
    print("\n当前数据库中的玩家:")
    players = storage.list_all_players()
    for i, player in enumerate(players, 1):
        print(f"  {i}. {player}")


def demo_cross_session_persistence():
    """演示跨session持久化"""
    print_section("演示 2: 跨Session数据持久化")

    # === Session 1 ===
    print("\n📍 Session 1: 初始数据收集")
    storage1 = create_storage("demo_opponent_stats.db")

    # 添加多个玩家
    players_data = [
        ("Bob", 50, 0.45, 0.08, 0.8),  # Fish
        ("Charlie", 80, 0.22, 0.18, 2.5),  # TAG
        ("Dave", 120, 0.55, 0.40, 4.2),  # Maniac
    ]

    for name, hands, vpip, pfr, af in players_data:
        stats = create_opponent_stats(name)
        stats.hands_played = hands
        stats.vpip = vpip
        stats.pfr = pfr
        stats.af = af
        storage1.save_stats(stats)
        print(f"  ✓ 保存 {name}: {hands}手, VPIP={vpip:.1%}")

    print(f"\n数据库信息:")
    info = storage1.get_database_info()
    print(f"  - 玩家数: {info['total_players']}")
    print(f"  - 总手数: {info['total_hands']}")
    print(f"  - 数据库大小: {info['db_size_kb']:.2f} KB")

    del storage1  # 模拟session结束

    # === Session 2 ===
    print("\n📍 Session 2: 数据恢复并继续")
    storage2 = create_storage("demo_opponent_stats.db")

    print("\n加载之前的玩家数据...")
    players = storage2.list_all_players()
    for player_id in players:
        loaded = storage2.load_stats(player_id)
        if loaded:
            print(f"  ✓ {player_id}: {loaded.hands_played}手, "
                  f"VPIP={loaded.vpip:.1%}, PFR={loaded.pfr:.1%}")

    # 更新数据
    print("\n更新Bob的数据 (新增50手)...")
    bob = storage2.load_stats("Bob")
    if bob:
        bob.hands_played = 100  # 50 -> 100
        bob.vpip = 0.42  # 稍微调整
        storage2.save_stats(bob)
        print(f"  ✓ Bob现在有 {bob.hands_played}手")


def demo_tracker_integration():
    """演示与StatsTracker集成"""
    print_section("演示 3: 与StatsTracker集成")

    # 创建带存储的tracker
    print("\n创建带存储后端的StatsTracker...")
    storage = create_storage("demo_opponent_stats.db")
    tracker = create_tracker(storage_backend=storage)
    print("✓ Tracker创建成功")

    # 模拟处理手牌
    print("\n处理手牌历史...")
    for i in range(5):
        hand_history = {
            'hand_id': f'demo_h{i:03d}',
            'players': [
                {'id': 'Eve', 'pos': 'BTN'},
                {'id': 'Frank', 'pos': 'BB'},
            ],
            'actions': [
                {'street': 'preflop', 'actor': 'Eve', 'action': 'raise', 'amount': 3.0},
                {'street': 'preflop', 'actor': 'Frank', 'action': 'call' if i < 3 else 'fold'},
            ],
            'winners': [{'seat': 'Eve', 'amount': 6.5}],
            'showdown': False,
        }
        tracker.update_from_hand(hand_history)
        print(f"  ✓ 处理手牌 #{i+1}")

    # 验证自动保存
    print("\n验证数据已自动保存到数据库...")
    eve_from_db = storage.load_stats('Eve')
    frank_from_db = storage.load_stats('Frank')

    if eve_from_db and frank_from_db:
        print(f"  ✓ Eve: {eve_from_db.hands_played}手, VPIP={eve_from_db.vpip:.1%}, PFR={eve_from_db.pfr:.1%}")
        print(f"  ✓ Frank: {frank_from_db.hands_played}手, VPIP={frank_from_db.vpip:.1%}")

    # 新session继续
    print("\n模拟新session，继续处理更多手牌...")
    tracker2 = create_tracker(storage_backend=storage)

    # 应该自动加载之前的数据
    eve_stats = tracker2.get_stats('Eve')
    print(f"  ✓ 自动加载Eve的历史数据: {eve_stats.hands_played}手")

    # 继续处理
    for i in range(5, 10):
        hand_history = {
            'hand_id': f'demo_h{i:03d}',
            'players': [
                {'id': 'Eve', 'pos': 'BTN'},
            ],
            'actions': [
                {'street': 'preflop', 'actor': 'Eve', 'action': 'fold'},
            ],
            'winners': [],
            'showdown': False,
        }
        tracker2.update_from_hand(hand_history)

    eve_final = tracker2.get_stats('Eve')
    print(f"  ✓ 处理更多手牌后，Eve现在有: {eve_final.hands_played}手")


def demo_database_management():
    """演示数据库管理功能"""
    print_section("演示 4: 数据库管理")

    storage = create_storage("demo_opponent_stats.db")

    # 获取数据库信息
    print("\n数据库详细信息:")
    info = storage.get_database_info()
    print(f"  数据库路径: {info['db_path']}")
    print(f"  玩家总数: {info['total_players']}")
    print(f"  总手数: {info['total_hands']}")
    print(f"  数据库大小: {info['db_size_kb']:.2f} KB ({info['db_size_bytes']} bytes)")
    print(f"  最后更新: {info['last_update']}")
    print(f"  Schema版本: {info['schema_version']}")

    # 列出所有玩家
    print("\n所有玩家列表:")
    players = storage.list_all_players()
    for i, player_id in enumerate(players, 1):
        stats = storage.load_stats(player_id)
        if stats:
            print(f"  {i}. {player_id}: "
                  f"{stats.hands_played}手, "
                  f"VPIP={stats.vpip:.1%}, "
                  f"PFR={stats.pfr:.1%}, "
                  f"AF={stats.af:.2f}")

    # 删除单个玩家
    if len(players) > 0:
        to_delete = players[0]
        print(f"\n删除玩家: {to_delete}")
        success = storage.delete_stats(to_delete)
        print(f"  {'✓ 删除成功' if success else '✗ 删除失败'}")
        print(f"  剩余玩家数: {storage.get_stats_count()}")


def demo_data_integrity():
    """演示数据完整性"""
    print_section("演示 5: 数据完整性验证")

    storage = create_storage("demo_opponent_stats.db")

    # 创建包含内部计数器的统计
    print("\n创建包含内部计数器的统计...")
    stats = create_opponent_stats("George")

    # 通过update_from_hand更新，设置内部计数器
    for i in range(10):
        hand = HandResult(
            hand_id=f"h{i:03d}",
            position=PositionType.BTN,
            vpip=(i < 7),
            pfr=(i < 5),
            three_bet=(i < 2),
        )
        stats.update_from_hand(hand)

    print(f"  ✓ 处理10手牌")
    print(f"    - VPIP: {stats.vpip:.1%}")
    print(f"    - PFR: {stats.pfr:.1%}")
    print(f"    - 3-bet: {stats.three_bet_pct:.1%}")

    # 保存
    storage.save_stats(stats)
    print("  ✓ 保存到数据库")

    # 重新加载
    loaded = storage.load_stats("George")
    print("\n重新加载并验证数据一致性...")
    print(f"  ✓ VPIP: {loaded.vpip:.1%} (原始: {stats.vpip:.1%}) - {'✓' if abs(loaded.vpip - stats.vpip) < 0.001 else '✗'}")
    print(f"  ✓ PFR: {loaded.pfr:.1%} (原始: {stats.pfr:.1%}) - {'✓' if abs(loaded.pfr - stats.pfr) < 0.001 else '✗'}")
    print(f"  ✓ 3-bet: {loaded.three_bet_pct:.1%} (原始: {stats.three_bet_pct:.1%}) - {'✓' if abs(loaded.three_bet_pct - stats.three_bet_pct) < 0.001 else '✗'}")

    # 继续更新测试增量更新
    print("\n继续处理5手牌...")
    for i in range(10, 15):
        hand = HandResult(
            hand_id=f"h{i:03d}",
            position=PositionType.BTN,
            vpip=True,
            pfr=True,
        )
        loaded.update_from_hand(hand)

    print(f"  ✓ 现在有{loaded.hands_played}手")
    print(f"    - VPIP: {loaded.vpip:.1%}")
    print(f"    - PFR: {loaded.pfr:.1%}")


def cleanup():
    """清理演示数据库"""
    print_section("清理")

    import os
    db_path = "demo_opponent_stats.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"✓ 已删除演示数据库: {db_path}")
    else:
        print("  (没有需要清理的文件)")


def main():
    """主函数"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 18 + "SQLite存储系统演示" + " " * 30 + "║")
    print("║" + " " * 15 + "Phase 2.2 - 对手建模引擎" + " " * 26 + "║")
    print("╚" + "═" * 68 + "╝")

    try:
        # 运行所有演示
        demo_basic_storage()
        input("\n按回车继续下一个演示...")

        demo_cross_session_persistence()
        input("\n按回车继续下一个演示...")

        demo_tracker_integration()
        input("\n按回车继续下一个演示...")

        demo_database_management()
        input("\n按回车继续下一个演示...")

        demo_data_integrity()
        input("\n按回车清理...")

        cleanup()

        # 总结
        print_section("总结")
        print("\nSQLite存储系统核心功能:")
        print("✓ 完整的CRUD操作")
        print("✓ 跨session数据持久化")
        print("✓ 自动保存与加载")
        print("✓ 与StatsTracker无缝集成")
        print("✓ 内部计数器完整保留")
        print("✓ 数据完整性验证")

        print("\n优势:")
        print("→ 零配置启动 (自动创建表结构)")
        print("→ O(1) 查询性能 (主键索引)")
        print("→ 支持多玩家并发追踪")
        print("→ 数据库文件轻量 (~几十KB)")

        print("\n下一步:")
        print("→ Week 2: 实现 classifier.py (玩家分类器)")
        print("→ Week 3: 实现 exploits.py (Exploit策略库)")

        print("\n" + "=" * 70)
        print("演示完成！ 🎉")
        print("=" * 70 + "\n")

    except KeyboardInterrupt:
        print("\n\n演示被中断。")
        cleanup()
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        cleanup()


if __name__ == '__main__':
    main()
