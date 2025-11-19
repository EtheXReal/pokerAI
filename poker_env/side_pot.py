"""
Side Pot Management

处理德州扑克的边池（Side Pot）逻辑
"""
from dataclasses import dataclass
from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .player import Player

from .utils import ZERO_THRESHOLD, FLOAT_TOLERANCE, SMALL_BLIND


@dataclass
class SidePot:
    """
    边池数据结构

    在多人all-in时，需要创建多个边池。
    每个边池有自己的金额和有资格赢得该边池的玩家列表。
    """
    amount: float  # 边池金额
    eligible_seats: List[int]  # 有资格赢得此边池的玩家座位列表
    cap_per_player: float  # 每个玩家在此边池的投入上限

    def __str__(self):
        return f"SidePot(amount={self.amount:.1f}BB, eligible={self.eligible_seats}, cap={self.cap_per_player:.1f}BB)"


class SidePotManager:
    """
    边池管理器

    负责根据玩家投入计算边池结构
    """

    @staticmethod
    def calculate_side_pots(players: List['Player'], verbose: bool = False) -> List[SidePot]:
        """
        根据玩家总投入计算边池

        算法：
        1. 获取所有active玩家的投入金额
        2. 按投入金额排序（从少到多）
        3. 从最小投入开始，逐级创建边池
        4. 每个边池包含投入≥该级别的所有玩家

        Args:
            players: 玩家列表
            verbose: 是否打印详细信息

        Returns:
            边池列表（按main pot到side pot顺序）

        示例：
            3人游戏：
            Player A (seat 0): 投入 30BB
            Player B (seat 1): 投入 50BB
            Player C (seat 2): 投入 100BB

            结果：
            Main Pot: 90BB (30x3), eligible=[0,1,2]
            Side Pot 1: 40BB (20x2), eligible=[1,2]
            Side Pot 2: 50BB (50x1), eligible=[2]
        """
        # 获取所有active玩家及其投入
        # 包括fold的玩家（他们的投入也要算在pot中）
        invested_players = []
        for p in players:
            if p.invested > ZERO_THRESHOLD:  # 有投入的玩家
                invested_players.append((p.seat, p.invested, p.is_active))

        if not invested_players:
            return []

        # 按投入金额排序
        invested_players.sort(key=lambda x: x[1])

        if verbose:
            print(f"\n  [SidePot] Calculating side pots:")
            for seat, invested, is_active in invested_players:
                status = "active" if is_active else "folded"
                print(f"  [SidePot]   seat {seat}: {invested:.1f}BB ({status})")

        side_pots = []
        prev_level = 0.0

        # 逐级创建边池
        for i, (seat, invested, is_active) in enumerate(invested_players):
            if invested > prev_level + FLOAT_TOLERANCE:  # 有新的投入级别
                # 计算这一级的边池金额
                level_amount = invested - prev_level

                # 这一级包含当前玩家及之后所有投入更多的玩家
                # 注意：即使玩家fold了，他们的投入也要算在pot中
                num_contributors = len(invested_players) - i
                pot_amount = level_amount * num_contributors

                # 有资格赢得此边池的玩家：投入≥此级别且still active
                eligible_seats = []
                for j in range(i, len(invested_players)):
                    seat_j, invested_j, is_active_j = invested_players[j]
                    if is_active_j:  # 只有active玩家才能赢
                        eligible_seats.append(seat_j)

                # 创建边池
                side_pot = SidePot(
                    amount=pot_amount,
                    eligible_seats=eligible_seats,
                    cap_per_player=invested
                )
                side_pots.append(side_pot)

                if verbose:
                    pot_type = "Main Pot" if len(side_pots) == 1 else f"Side Pot {len(side_pots)-1}"
                    print(f"  [SidePot] {pot_type}: {pot_amount:.1f}BB, eligible={eligible_seats}, cap={invested:.1f}BB")

                prev_level = invested

        return side_pots

    @staticmethod
    def distribute_pots(side_pots: List[SidePot], players: List['Player'],
                       hand_strengths: List[Tuple[int, any]], verbose: bool = False) -> List[float]:
        """
        根据边池和牌力分配奖金

        Args:
            side_pots: 边池列表
            players: 玩家列表
            hand_strengths: [(seat, strength), ...] 玩家牌力列表（只包含active玩家）
            verbose: 是否打印详细信息

        Returns:
            每个玩家的总奖金列表（按seat索引）
        """
        player_winnings = [0.0] * len(players)

        if verbose:
            print(f"\n  [SidePot] Distributing pots:")

        for i, side_pot in enumerate(side_pots):
            pot_name = "Main Pot" if i == 0 else f"Side Pot {i}"

            if verbose:
                print(f"  [SidePot] {pot_name}: {side_pot.amount:.1f}BB, eligible={side_pot.eligible_seats}")

            # 找到eligible中的玩家及其牌力
            eligible_strengths = []
            for seat, strength in hand_strengths:
                if seat in side_pot.eligible_seats:
                    eligible_strengths.append((seat, strength))

            if not eligible_strengths:
                # 没有eligible玩家（都fold了），这种情况不应该发生
                if verbose:
                    print(f"  [SidePot]   Warning: No eligible players for {pot_name}")
                continue

            # 找到最强的牌
            max_strength = max(strength for _, strength in eligible_strengths)
            winners = [seat for seat, strength in eligible_strengths if strength == max_strength]

            # 分配此边池
            share = side_pot.amount / len(winners)
            for seat in winners:
                player_winnings[seat] += share

            if verbose:
                winner_names = [players[seat].name for seat in winners]
                if len(winners) == 1:
                    print(f"  [SidePot]   {winner_names[0]} wins {side_pot.amount:.1f}BB")
                else:
                    print(f"  [SidePot]   {', '.join(winner_names)} split {side_pot.amount:.1f}BB ({share:.1f}BB each)")

        return player_winnings

    @staticmethod
    def validate_side_pots(side_pots: List[SidePot], players: List['Player']) -> bool:
        """
        验证边池计算是否正确

        检查：
        1. 所有边池金额之和 = 所有玩家投入之和
        2. 每个边池的eligible玩家都是active的

        Returns:
            True if valid, False otherwise
        """
        # 计算总投入
        total_invested = sum(p.invested for p in players)

        # 计算边池总额
        total_side_pots = sum(sp.amount for sp in side_pots)

        # 允许小数误差
        if abs(total_invested - total_side_pots) > SMALL_BLIND:
            print(f"[SidePot] ERROR: Total invested ({total_invested:.1f}BB) != "
                  f"Total side pots ({total_side_pots:.1f}BB)")
            return False

        # 验证eligible玩家
        for i, sp in enumerate(side_pots):
            for seat in sp.eligible_seats:
                if not players[seat].is_active:
                    print(f"[SidePot] ERROR: Side pot {i} includes folded player seat {seat}")
                    return False

        return True


def test_side_pot_calculation():
    """测试边池计算"""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from poker_env.player import Player, PlayerAction, GameState

    # 创建测试用的Player实现
    class TestPlayer(Player):
        def decide(self, game_state: GameState) -> PlayerAction:
            return PlayerAction('fold', 0.0)

    print("=" * 80)
    print("Testing Side Pot Calculation")
    print("=" * 80)

    # 测试1: 三人，不同投入
    print("\nTest 1: 3 players, different investments")
    players = [
        TestPlayer("A", 0, 100.0),
        TestPlayer("B", 1, 100.0),
        TestPlayer("C", 2, 100.0),
    ]

    # 模拟投入
    players[0].invest(30.0)  # A投入30BB
    players[1].invest(50.0)  # B投入50BB
    players[2].invest(100.0) # C投入100BB

    side_pots = SidePotManager.calculate_side_pots(players, verbose=True)

    assert len(side_pots) == 3
    assert abs(side_pots[0].amount - 90.0) < 0.1  # Main pot: 30x3
    assert abs(side_pots[1].amount - 40.0) < 0.1  # Side pot 1: 20x2
    assert abs(side_pots[2].amount - 50.0) < 0.1  # Side pot 2: 50x1

    assert SidePotManager.validate_side_pots(side_pots, players)
    print("✓ Test 1 passed")

    # 测试2: 两人，一方all-in
    print("\nTest 2: 2 players, one all-in")
    players = [
        TestPlayer("A", 0, 100.0),
        TestPlayer("B", 1, 100.0),
    ]

    players[0].invest(50.0)   # A投入50BB, all-in
    players[1].invest(50.0)   # B投入50BB, call

    side_pots = SidePotManager.calculate_side_pots(players, verbose=True)

    assert len(side_pots) == 1  # 只有main pot
    assert abs(side_pots[0].amount - 100.0) < 0.1  # 50x2

    assert SidePotManager.validate_side_pots(side_pots, players)
    print("✓ Test 2 passed")

    # 测试3: 四人，连续all-in
    print("\nTest 3: 4 players, cascading all-ins")
    players = [
        TestPlayer("A", 0, 100.0),
        TestPlayer("B", 1, 100.0),
        TestPlayer("C", 2, 100.0),
        TestPlayer("D", 3, 100.0),
    ]

    players[0].invest(20.0)  # A: 20BB all-in
    players[1].invest(40.0)  # B: 40BB all-in
    players[2].invest(60.0)  # C: 60BB all-in
    players[3].invest(100.0) # D: 100BB call

    side_pots = SidePotManager.calculate_side_pots(players, verbose=True)

    assert len(side_pots) == 4
    assert abs(side_pots[0].amount - 80.0) < 0.1   # Main: 20x4
    assert abs(side_pots[1].amount - 60.0) < 0.1   # Side 1: 20x3
    assert abs(side_pots[2].amount - 40.0) < 0.1   # Side 2: 20x2
    assert abs(side_pots[3].amount - 40.0) < 0.1   # Side 3: 40x1

    assert SidePotManager.validate_side_pots(side_pots, players)
    print("✓ Test 3 passed")

    # 测试4: 有人fold
    print("\nTest 4: 3 players, one folds")
    players = [
        TestPlayer("A", 0, 100.0),
        TestPlayer("B", 1, 100.0),
        TestPlayer("C", 2, 100.0),
    ]

    players[0].invest(30.0)  # A投入30BB
    players[1].invest(50.0)  # B投入50BB
    players[1].is_active = False  # B fold了
    players[2].invest(100.0) # C投入100BB

    side_pots = SidePotManager.calculate_side_pots(players, verbose=True)

    # B fold了，但他的投入还在pot中
    # Main pot: 30x3=90BB, eligible=[0,2] (B fold了不能赢)
    # Side pot 1: 20x2=40BB, eligible=[2] (只有C还active且投入≥50)
    # Side pot 2: 50x1=50BB, eligible=[2]

    assert len(side_pots) == 3
    assert 0 in side_pots[0].eligible_seats and 2 in side_pots[0].eligible_seats
    assert 1 not in side_pots[0].eligible_seats  # B fold了

    assert SidePotManager.validate_side_pots(side_pots, players)
    print("✓ Test 4 passed")

    print("\n" + "=" * 80)
    print("All tests passed! ✓")
    print("=" * 80)


if __name__ == '__main__':
    test_side_pot_calculation()
