#!/usr/bin/env python
"""
扑克牌基础类 (Poker Card Classes)

定义:
- Rank: 牌面大小 (2-A)
- Suit: 花色 (♠♥♦♣)
- Card: 单张牌
- Hand: 手牌 (2张)
- Board: 公共牌 (0-5张)
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional, Set, FrozenSet


class Rank(IntEnum):
    """牌面大小 (2最小，A最大)"""
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    def __str__(self) -> str:
        rank_map = {
            2: '2', 3: '3', 4: '4', 5: '5', 6: '6',
            7: '7', 8: '8', 9: '9', 10: 'T',
            11: 'J', 12: 'Q', 13: 'K', 14: 'A'
        }
        return rank_map[self.value]

    @staticmethod
    def from_str(s: str) -> Rank:
        """从字符串解析牌面"""
        rank_map = {
            '2': Rank.TWO, '3': Rank.THREE, '4': Rank.FOUR,
            '5': Rank.FIVE, '6': Rank.SIX, '7': Rank.SEVEN,
            '8': Rank.EIGHT, '9': Rank.NINE, 'T': Rank.TEN,
            'J': Rank.JACK, 'Q': Rank.QUEEN, 'K': Rank.KING, 'A': Rank.ACE
        }
        return rank_map[s.upper()]


class Suit(IntEnum):
    """花色"""
    CLUBS = 1      # ♣
    DIAMONDS = 2   # ♦
    HEARTS = 3     # ♥
    SPADES = 4     # ♠

    def __str__(self) -> str:
        suit_map = {
            1: 'c',  # clubs
            2: 'd',  # diamonds
            3: 'h',  # hearts
            4: 's',  # spades
        }
        return suit_map[self.value]

    @staticmethod
    def from_str(s: str) -> Suit:
        """从字符串解析花色"""
        suit_map = {
            'c': Suit.CLUBS,
            'd': Suit.DIAMONDS,
            'h': Suit.HEARTS,
            's': Suit.SPADES,
        }
        return suit_map[s.lower()]


@dataclass(frozen=True)
class Card:
    """
    单张牌

    Example:
        Card(Rank.ACE, Suit.SPADES)  # A♠
        Card.from_str("As")           # A♠
    """
    rank: Rank
    suit: Suit

    def __post_init__(self):
        # 允许 Card('A', 's') 这样的字符串参数，归一化为枚举
        # （frozen dataclass 需要用 object.__setattr__）
        if isinstance(self.rank, str):
            object.__setattr__(self, 'rank', Rank.from_str(self.rank))
        if isinstance(self.suit, str):
            object.__setattr__(self, 'suit', Suit.from_str(self.suit))

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"

    def __repr__(self) -> str:
        return f"Card('{self}')"

    def __hash__(self) -> int:
        return hash((self.rank, self.suit))

    def __eq__(self, other) -> bool:
        if not isinstance(other, Card):
            return False
        return self.rank == other.rank and self.suit == other.suit

    def __lt__(self, other: Card) -> bool:
        """按牌面大小排序 (花色不影响大小)"""
        return self.rank < other.rank

    @staticmethod
    def from_str(s: str) -> Card:
        """
        从字符串创建牌

        Args:
            s: 2字符字符串，如 "As" (A♠), "Th" (10♥)

        Returns:
            Card对象

        Example:
            Card.from_str("As")  # A♠
            Card.from_str("Kh")  # K♥
        """
        if len(s) != 2:
            raise ValueError(f"Invalid card string: {s}")

        rank = Rank.from_str(s[0])
        suit = Suit.from_str(s[1])
        return Card(rank, suit)


@dataclass
class Hand:
    """
    玩家手牌 (2张)

    Example:
        Hand([Card.from_str("As"), Card.from_str("Ks")])
        Hand.from_str("AsKs")
    """
    cards: List[Card]

    def __post_init__(self):
        if len(self.cards) != 2:
            raise ValueError(f"Hand must have exactly 2 cards, got {len(self.cards)}")

    def __str__(self) -> str:
        return ''.join(str(c) for c in self.cards)

    def __repr__(self) -> str:
        return f"Hand('{self}')"

    def __iter__(self):
        return iter(self.cards)

    def __getitem__(self, index):
        return self.cards[index]

    def __eq__(self, other) -> bool:
        """顺序无关的相等性: Hand('AsKh') == Hand('KhAs')"""
        if not isinstance(other, Hand):
            return False
        return frozenset(self.cards) == frozenset(other.cards)

    def __hash__(self) -> int:
        return hash(frozenset(self.cards))

    @staticmethod
    def from_str(s: str) -> Hand:
        """
        从字符串创建手牌

        Args:
            s: 4字符字符串，如 "AsKs" (A♠K♠)

        Returns:
            Hand对象

        Example:
            Hand.from_str("AsKs")  # A♠K♠
            Hand.from_str("QhJh")  # Q♥J♥
        """
        if len(s) != 4:
            raise ValueError(f"Invalid hand string: {s}")

        card1 = Card.from_str(s[0:2])
        card2 = Card.from_str(s[2:4])
        return Hand([card1, card2])

    def is_pocket_pair(self) -> bool:
        """是否是对子"""
        return self.cards[0].rank == self.cards[1].rank

    def is_suited(self) -> bool:
        """是否同花"""
        return self.cards[0].suit == self.cards[1].suit

    def to_cards_set(self) -> FrozenSet[Card]:
        """转换为不可变集合 (用于检查重复)"""
        return frozenset(self.cards)


@dataclass
class Board:
    """
    公共牌 (0-5张)

    Example:
        Board([])  # 翻前
        Board.from_str("AsKsQs")  # 翻牌圈 (flop)
        Board.from_str("AsKsQsJs")  # 转牌圈 (turn)
        Board.from_str("AsKsQsJsTs")  # 河牌圈 (river)
    """
    cards: List[Card]

    def __post_init__(self):
        if len(self.cards) > 5:
            raise ValueError(f"Board can have at most 5 cards, got {len(self.cards)}")

    def __str__(self) -> str:
        if not self.cards:
            return ""
        return ''.join(str(c) for c in self.cards)

    def __repr__(self) -> str:
        if not self.cards:
            return "Board([])"
        return f"Board('{self}')"

    def __iter__(self):
        return iter(self.cards)

    def __getitem__(self, index):
        return self.cards[index]

    def __len__(self):
        return len(self.cards)

    @staticmethod
    def from_str(s: str) -> Board:
        """
        从字符串创建公共牌

        Args:
            s: 0-10字符字符串 (每张牌2字符)

        Returns:
            Board对象

        Example:
            Board.from_str("")  # 空牌面
            Board.from_str("AsKsQs")  # 翻牌
            Board.from_str("AsKsQsJs")  # 转牌
            Board.from_str("AsKsQsJsTs")  # 河牌
        """
        if not s:
            return Board([])

        if len(s) % 2 != 0:
            raise ValueError(f"Invalid board string: {s}")

        cards = []
        for i in range(0, len(s), 2):
            cards.append(Card.from_str(s[i:i+2]))

        return Board(cards)

    def is_preflop(self) -> bool:
        """是否翻前"""
        return len(self.cards) == 0

    def is_flop(self) -> bool:
        """是否翻牌圈"""
        return len(self.cards) == 3

    def is_turn(self) -> bool:
        """是否转牌圈"""
        return len(self.cards) == 4

    def is_river(self) -> bool:
        """是否河牌圈"""
        return len(self.cards) == 5

    def to_cards_set(self) -> FrozenSet[Card]:
        """转换为不可变集合 (用于检查重复)"""
        return frozenset(self.cards)


def create_deck() -> List[Card]:
    """
    创建一副完整的52张牌

    Returns:
        52张牌的列表
    """
    deck = []
    for suit in Suit:
        for rank in Rank:
            deck.append(Card(rank, suit))
    return deck


def validate_no_duplicates(hand: Hand, board: Board) -> None:
    """
    验证手牌和公共牌没有重复

    Args:
        hand: 手牌
        board: 公共牌

    Raises:
        ValueError: 如果有重复牌
    """
    all_cards = list(hand.cards) + list(board.cards)

    if len(all_cards) != len(set(all_cards)):
        raise ValueError(f"Duplicate cards found: hand={hand}, board={board}")


def cards_to_str(cards: List[Card]) -> str:
    """
    将牌列表转换为字符串

    Args:
        cards: 牌列表

    Returns:
        字符串表示，如 "AsKsQs"
    """
    return ''.join(str(c) for c in cards)
