"""
Texas Hold'em Poker Game Engine

支持2-10人游戏的核心引擎
"""
import random
from dataclasses import dataclass
from typing import List, Optional

from advisor.range_engine import Hand, Board, create_deck, Card
from advisor.range_engine.evaluator import HandEvaluator

from .player import Player
from .betting_round import BettingRound, ActionRecord
from .utils import Street, get_blind_amounts, get_position_name, ZERO_THRESHOLD
from .side_pot import SidePotManager


@dataclass
class GameConfig:
    """游戏配置"""
    num_players: int = 2
    starting_stack: float = 100.0
    small_blind: float = 0.5
    big_blind: float = 1.0
    verbose: bool = False
    debug: bool = False


@dataclass
class GameResult:
    """单手牌结果"""
    hand_num: int
    btn_seat: int

    # 玩家手牌（按座位索引）
    player_hands: List[str]

    # 公共牌
    flop: List[str]
    turn: str
    river: str

    # 所有行动
    actions: List[ActionRecord]

    # 结果
    winner_seats: List[int]  # 获胜者座位列表（可能多人平分）
    pot: float
    player_profits: List[float]  # 每个玩家的盈亏（按座位索引）

    # 是否到showdown
    showdown: bool
    hand_strengths: List[str]  # 如果到showdown，每个玩家的牌力名称


class PokerGame:
    """
    德州扑克游戏引擎

    支持2-10人游戏，完整的4个街道决策
    """

    def __init__(self, players: List[Player], config: GameConfig):
        """
        Args:
            players: 玩家列表（座位顺序）
            config: 游戏配置
        """
        if len(players) != config.num_players:
            raise ValueError(f"Expected {config.num_players} players, got {len(players)}")

        if config.num_players < 2 or config.num_players > 10:
            raise ValueError(f"Number of players must be 2-10, got {config.num_players}")

        self.players = players
        self.config = config
        self.betting_round = BettingRound(verbose=config.verbose, debug=config.debug)

        # 验证座位索引
        for i, player in enumerate(players):
            if player.seat != i:
                raise ValueError(f"Player {player.name} seat mismatch: expected {i}, got {player.seat}")

    def play_hand(self, hand_num: int, btn_seat: int, seed: Optional[int] = None) -> GameResult:
        """
        玩一手完整的牌

        Args:
            hand_num: 手牌编号
            btn_seat: 庄家座位索引
            seed: 随机种子（可选）

        Returns:
            GameResult对象
        """
        if seed is not None:
            random.seed(seed)

        # 重置玩家状态
        for player in self.players:
            player.reset_for_new_hand(self.config.starting_stack)

        # 发牌
        deck = create_deck()
        random.shuffle(deck)

        # 给每个玩家发两张牌
        for i, player in enumerate(self.players):
            player.hand = Hand([deck[i*2], deck[i*2+1]])

        # 公共牌（5张）
        board_start = len(self.players) * 2
        board_cards = deck[board_start:board_start+5]
        flop_cards = board_cards[0:3]
        turn_card = board_cards[3]
        river_card = board_cards[4]

        # 盲注
        blind_config = get_blind_amounts(self.config.num_players,
                                        self.config.small_blind,
                                        self.config.big_blind)
        pot = 0.0
        for offset, blind_amount in blind_config.items():
            seat = (btn_seat + offset) % self.config.num_players
            player = self.players[seat]
            actual_invested = player.invest(blind_amount)
            pot += actual_invested

        # 行动记录
        actions: List[ActionRecord] = []

        if self.config.verbose:
            # 显示手牌编号和BTN信息
            btn_player = self.players[btn_seat]
            print(f"\n{'=' * 80}")
            print(f"Hand #{hand_num} - BTN: {btn_player.name} (seat {btn_seat})")
            print(f"{'=' * 80}")
            print(f"\n  === 翻前 ===")
            for player in self.players:
                pos_name = get_position_name(player.seat, btn_seat, self.config.num_players)
                print(f"  {player.name}: {player.hand} ({pos_name})")
            print(f"  Pot: {pot:.1f}BB")

        # ===== Preflop =====
        winner_name, pot = self.betting_round.run(
            Street.PREFLOP,
            self.players,
            btn_seat,
            Board([]),
            pot,
            actions
        )

        if winner_name:
            return self._finalize_result(hand_num, btn_seat, winner_name, pot, actions,
                                        flop_cards, turn_card, river_card, fold_win=True)

        # 重置街道投入
        for player in self.players:
            player.reset_for_new_street()

        # 检查是否所有人all-in
        active_non_allin = [p for p in self.players if p.is_active and not p.is_allin]
        if len(active_non_allin) == 0:
            # 所有人都all-in，直接到showdown
            return self._showdown(hand_num, btn_seat, pot, actions,
                                flop_cards, turn_card, river_card)

        # ===== Flop =====
        board = Board(flop_cards)
        if self.config.verbose:
            print(f"\n  === Flop: {' '.join(str(c) for c in flop_cards)} ===")
            print(f"  Pot: {pot:.1f}BB")

        winner_name, pot = self.betting_round.run(
            Street.FLOP,
            self.players,
            btn_seat,
            board,
            pot,
            actions
        )

        if winner_name:
            return self._finalize_result(hand_num, btn_seat, winner_name, pot, actions,
                                        flop_cards, turn_card, river_card, fold_win=True)

        # 重置街道投入
        for player in self.players:
            player.reset_for_new_street()

        # 检查all-in
        active_non_allin = [p for p in self.players if p.is_active and not p.is_allin]
        if len(active_non_allin) == 0:
            return self._showdown(hand_num, btn_seat, pot, actions,
                                flop_cards, turn_card, river_card)

        # ===== Turn =====
        board = Board(flop_cards + [turn_card])
        if self.config.verbose:
            print(f"\n  === Turn: {turn_card} ===")
            print(f"  Board: {' '.join(str(c) for c in flop_cards)} {turn_card}")
            print(f"  Pot: {pot:.1f}BB")

        winner_name, pot = self.betting_round.run(
            Street.TURN,
            self.players,
            btn_seat,
            board,
            pot,
            actions
        )

        if winner_name:
            return self._finalize_result(hand_num, btn_seat, winner_name, pot, actions,
                                        flop_cards, turn_card, river_card, fold_win=True)

        # 重置街道投入
        for player in self.players:
            player.reset_for_new_street()

        # 检查all-in
        active_non_allin = [p for p in self.players if p.is_active and not p.is_allin]
        if len(active_non_allin) == 0:
            return self._showdown(hand_num, btn_seat, pot, actions,
                                flop_cards, turn_card, river_card)

        # ===== River =====
        board = Board(board_cards)
        if self.config.verbose:
            print(f"\n  === River: {river_card} ===")
            print(f"  Board: {' '.join(str(c) for c in flop_cards)} {turn_card} {river_card}")
            print(f"  Pot: {pot:.1f}BB")

        winner_name, pot = self.betting_round.run(
            Street.RIVER,
            self.players,
            btn_seat,
            board,
            pot,
            actions
        )

        if winner_name:
            return self._finalize_result(hand_num, btn_seat, winner_name, pot, actions,
                                        flop_cards, turn_card, river_card, fold_win=True)

        # ===== Showdown =====
        return self._showdown(hand_num, btn_seat, pot, actions,
                            flop_cards, turn_card, river_card)

    def _showdown(self, hand_num: int, btn_seat: int, pot: float,
                  actions: List[ActionRecord],
                  flop_cards: List[Card], turn_card: Card, river_card: Card) -> GameResult:
        """执行showdown（支持边池）"""
        if self.config.verbose:
            print(f"\n  === Showdown ===")

        board = Board([*flop_cards, turn_card, river_card])

        # 评估所有active玩家的牌力
        active_players = [p for p in self.players if p.is_active]

        # 评估牌力
        hand_strengths_list = []  # [(seat, strength), ...]
        for player in active_players:
            all_cards = list(player.hand.cards) + list(board.cards)
            strength = HandEvaluator.evaluate_best_5(all_cards)
            hand_strengths_list.append((player.seat, strength))
            if self.config.verbose:
                print(f"  {player.name}: {strength.rank.name}")

        # 计算边池
        # 只有在真正有多个边池或不同投入时才显示详细信息
        active_invested = [p.invested for p in self.players if p.is_active]
        has_side_pots = len(set(active_invested)) > 1  # 投入金额不同

        # 边池计算（不显示详细信息）
        side_pots = SidePotManager.calculate_side_pots(self.players, verbose=False)

        # 验证边池（可选）
        if not SidePotManager.validate_side_pots(side_pots, self.players):
            print("[WARNING] Side pot validation failed!")

        # 只在真正有边池时才显示详细信息
        if self.config.verbose and has_side_pots and len(side_pots) > 1:
            print(f"\n  [Side Pots] Multiple pots due to all-in:")
            for i, sp in enumerate(side_pots):
                pot_name = "Main Pot" if i == 0 else f"Side Pot {i}"
                print(f"    {pot_name}: {sp.amount:.1f}BB (eligible: {sp.eligible_seats})")

        # 根据边池分配奖金（不显示详细信息，稍后统一显示）
        player_winnings = SidePotManager.distribute_pots(
            side_pots, self.players, hand_strengths_list, verbose=False
        )

        # 显示获胜者
        if self.config.verbose:
            winner_names = [self.players[i].name for i, w in enumerate(player_winnings) if w > ZERO_THRESHOLD]
            if len(winner_names) == 1:
                print(f"  {winner_names[0]} wins {pot:.1f}BB")
            else:
                shares = {self.players[i].name: player_winnings[i] for i in range(len(self.players)) if player_winnings[i] > ZERO_THRESHOLD}
                for name, amount in shares.items():
                    print(f"  {name} wins {amount:.1f}BB")

        # 找到获胜者（赢得任何金额的玩家）
        winner_seats = [i for i, w in enumerate(player_winnings) if w > ZERO_THRESHOLD]

        # 计算每个玩家的盈亏
        player_profits = []
        for i, player in enumerate(self.players):
            profit = player_winnings[i] - player.invested
            player_profits.append(profit)

        # 构建结果
        flop_str = [str(c) for c in flop_cards]
        turn_str = str(turn_card)
        river_str = str(river_card)

        player_hands = [str(p.hand) if p.hand else "" for p in self.players]
        hand_strength_names = []
        for player in self.players:
            if player.is_active:
                all_cards = list(player.hand.cards) + list(board.cards)
                strength = HandEvaluator.evaluate_best_5(all_cards)
                hand_strength_names.append(strength.rank.name)
            else:
                hand_strength_names.append("FOLDED")

        return GameResult(
            hand_num=hand_num,
            btn_seat=btn_seat,
            player_hands=player_hands,
            flop=flop_str,
            turn=turn_str,
            river=river_str,
            actions=actions,
            winner_seats=winner_seats,
            pot=pot,
            player_profits=player_profits,
            showdown=True,
            hand_strengths=hand_strength_names
        )

    def _finalize_result(self, hand_num: int, btn_seat: int, winner_name: str, pot: float,
                        actions: List[ActionRecord],
                        flop_cards: List[Card], turn_card: Card, river_card: Card,
                        fold_win: bool = True) -> GameResult:
        """有人fold后的结果"""
        # 找到获胜者
        winner = next(p for p in self.players if p.name == winner_name)

        # 计算盈亏
        player_profits = []
        for player in self.players:
            if player.name == winner_name:
                profit = pot - player.invested
            else:
                profit = -player.invested
            player_profits.append(profit)

        if self.config.verbose:
            print(f"  {winner_name} wins {pot:.1f}BB (fold)")

        flop_str = [str(c) for c in flop_cards] if flop_cards else []
        turn_str = str(turn_card) if turn_card else ""
        river_str = str(river_card) if river_card else ""

        player_hands = [str(p.hand) if p.hand else "" for p in self.players]

        return GameResult(
            hand_num=hand_num,
            btn_seat=btn_seat,
            player_hands=player_hands,
            flop=flop_str,
            turn=turn_str,
            river=river_str,
            actions=actions,
            winner_seats=[winner.seat],
            pot=pot,
            player_profits=player_profits,
            showdown=False,
            hand_strengths=[]
        )
