# Equity引擎融合方案 - 取长补短，合二为一

## 📋 方案概览

**目标**：保留新实现的高质量底层（已验证正确），添加旧实现的高级功能。

**核心原则**：
- ✅ **Zero-Dependency**：保持Pure Python，不引入Treys
- ✅ **Test-Driven**：所有新功能必须有测试覆盖
- ✅ **Precision-Verified**：保持0.007%误差级别精度
- ✅ **API-Compatible**：参考旧实现的API设计

---

## 🎯 Phase 1: 增强Range解析（高优先级）

### 目标：支持"+"符号，提升用户体验

#### 1.1 当前实现回顾

```python
# advisor/equity/range.py (当前)
class RangeParser:
    def parse(self, range_str: str) -> Set[HandCombo]:
        """
        当前支持：
        - "AA,KK,QQ" ✅
        - "AKs,AKo" ✅

        不支持：
        - "77+" ❌ (应该是77,88,99,TT,JJ,QQ,KK,AA)
        - "A5s+" ❌ (应该是A5s,A6s,...,AKs)
        """
```

#### 1.2 新增功能

```python
class RangeParser:
    """增强版Range解析器"""

    def parse(self, range_str: str) -> Set[HandCombo]:
        """
        支持格式：
        - 基础: "AA,KK,AKs,AKo"
        - 口袋对+: "77+" = 77,88,99,TT,JJ,QQ,KK,AA
        - 同花+: "A5s+" = A5s,A6s,A7s,A8s,A9s,ATs,AJs,AQs,AKs
        - 非同花+: "ATo+" = ATo,AJo,AQo,AKo
        - 组合: "QQ+,AK,A9s+" = QQ,KK,AA,AKs,AKo,A9s,ATs,AJs,AQs,AKs
        """
        parts = [p.strip() for p in range_str.split(',')]
        combos = set()

        for part in parts:
            if not part:
                continue

            if part.endswith('+'):
                # 处理"+"符号
                combos.update(self._parse_plus_notation(part[:-1]))
            else:
                # 处理单个手牌
                combos.update(self._parse_single(part))

        return combos

    def _parse_plus_notation(self, hand: str) -> Set[HandCombo]:
        """
        解析"+"符号

        Examples:
            "77+" -> {77,88,99,TT,JJ,QQ,KK,AA}
            "A5s+" -> {A5s,A6s,A7s,A8s,A9s,ATs,AJs,AQs,AKs}
            "KTo+" -> {KTo,KJo,KQo}
        """
        if len(hand) == 2 and hand[0] == hand[1]:
            # 口袋对: "77+"
            return self._expand_pair_plus(hand[0])

        elif len(hand) == 3:
            r1, r2, suit_flag = hand[0], hand[1], hand[2]
            if suit_flag == 's':
                # 同花: "A5s+"
                return self._expand_suited_plus(r1, r2)
            elif suit_flag == 'o':
                # 非同花: "KTo+"
                return self._expand_offsuit_plus(r1, r2)

        return set()

    def _expand_pair_plus(self, start_rank: str) -> Set[HandCombo]:
        """
        扩展口袋对+

        Example: "77+" -> {77,88,99,TT,JJ,QQ,KK,AA}
        """
        ranks = '23456789TJQKA'
        start_idx = ranks.index(start_rank)

        combos = set()
        for rank in ranks[start_idx:]:
            # 生成该rank的所有口袋对组合 (6个)
            combos.update(self._generate_pair(rank))

        return combos

    def _expand_suited_plus(self, high: str, low: str) -> Set[HandCombo]:
        """
        扩展同花+

        Example: "A5s+" -> {A5s,A6s,A7s,A8s,A9s,ATs,AJs,AQs,AKs}
        """
        ranks = '23456789TJQKA'
        high_idx = ranks.index(high)
        low_idx = ranks.index(low)

        combos = set()
        for kicker in ranks[low_idx:high_idx]:
            # 生成high+kicker的所有同花组合 (4个)
            combos.update(self._generate_suited(high, kicker))

        return combos

    def _expand_offsuit_plus(self, high: str, low: str) -> Set[HandCombo]:
        """
        扩展非同花+

        Example: "KTo+" -> {KTo,KJo,KQo}
        """
        ranks = '23456789TJQKA'
        high_idx = ranks.index(high)
        low_idx = ranks.index(low)

        combos = set()
        for kicker in ranks[low_idx:high_idx]:
            # 生成high+kicker的所有非同花组合 (12个)
            combos.update(self._generate_offsuit(high, kicker))

        return combos
```

#### 1.3 测试用例

```python
class TestRangePlusNotation(unittest.TestCase):
    """测试"+"符号解析"""

    def test_pair_plus(self):
        """测试口袋对+"""
        range_obj = Range("77+")

        # 77+ = 77,88,99,TT,JJ,QQ,KK,AA (8种对 * 6组合 = 48)
        self.assertEqual(len(range_obj.combos), 48)

        # 验证包含所有对
        self.assertIn("7c7d", range_obj.combos)  # 77
        self.assertIn("AsAh", range_obj.combos)  # AA

    def test_suited_plus(self):
        """测试同花+"""
        range_obj = Range("A5s+")

        # A5s+ = A5s,A6s,A7s,A8s,A9s,ATs,AJs,AQs,AKs (9种 * 4花色 = 36)
        self.assertEqual(len(range_obj.combos), 36)

        self.assertIn("Ah5h", range_obj.combos)
        self.assertIn("AsKs", range_obj.combos)

    def test_offsuit_plus(self):
        """测试非同花+"""
        range_obj = Range("ATo+")

        # ATo+ = ATo,AJo,AQo,AKo (4种 * 12组合 = 48)
        self.assertEqual(len(range_obj.combos), 48)

        self.assertIn("AhTd", range_obj.combos)
        self.assertIn("AsKc", range_obj.combos)

    def test_combined_range(self):
        """测试组合范围"""
        range_obj = Range("QQ+,AK,A9s+")

        # QQ+ = 18, AK = 16, A9s+ = 24
        expected = 18 + 16 + 24
        self.assertEqual(len(range_obj.combos), expected)
```

---

## 🎯 Phase 2: Hand vs Range Equity（核心功能）

### 目标：计算手牌对抗范围的equity

#### 2.1 API设计

```python
class EquityCalculator:
    """增强版Equity计算器"""

    def calculate_hand_vs_range(
        self,
        hero_hand: Hand,
        villain_range: Range,
        board: Board,
        iterations: int = 1000
    ) -> RangeEquityResult:
        """
        计算手牌 vs 范围的equity

        Args:
            hero_hand: 我方手牌 (如 AsKd)
            villain_range: 对手范围 (如 Range("QQ+,AK"))
            board: 公共牌 (可以是0/3/4/5张)
            iterations: 每个combo的采样次数

        Returns:
            RangeEquityResult: 包含平均equity、权重分布等

        Example:
            >>> calc = EquityCalculator()
            >>> hero = Hand.from_str("AsKh")
            >>> villain_range = Range("QQ+,AK,A9s+")
            >>> board = Board.from_str("Ah5c2d")
            >>> result = calc.calculate_hand_vs_range(hero, villain_range, board)
            >>> print(f"Equity: {result.equity:.1%}")
            Equity: 65.3%
        """
```

#### 2.2 实现思路

```python
def calculate_hand_vs_range(
    self,
    hero_hand: Hand,
    villain_range: Range,
    board: Board,
    iterations: int = 1000
) -> RangeEquityResult:
    """
    实现策略：
    1. 移除死牌（hero手牌+公共牌）
    2. 获取villain范围内所有有效combos
    3. 对每个combo运行equity计算
    4. 加权平均（考虑阻挡效应）
    """
    # 1. 移除死牌
    dead_cards = set(hero_hand.cards) | set(board.cards)
    valid_combos = villain_range.get_valid_combos(dead_cards)

    if not valid_combos:
        return RangeEquityResult(equity=1.0, combos_count=0)

    # 2. 对每个combo计算equity
    combo_equities = []
    for combo in valid_combos:
        villain_hand = Hand.from_combo(combo)

        # 使用现有的hand vs hand计算
        result = self.calculate_equity(
            hero_hand,
            villain_hand,
            board,
            iterations=iterations
        )

        combo_equities.append({
            'combo': combo,
            'equity': result.equity,
            'weight': 1.0  # 初始权重相等
        })

    # 3. 计算加权平均equity
    total_weight = sum(ce['weight'] for ce in combo_equities)
    avg_equity = sum(
        ce['equity'] * ce['weight']
        for ce in combo_equities
    ) / total_weight

    return RangeEquityResult(
        equity=avg_equity,
        combos_count=len(valid_combos),
        combo_breakdown=combo_equities
    )
```

#### 2.3 数据结构

```python
@dataclass
class RangeEquityResult:
    """Range Equity计算结果"""
    equity: float                    # 平均equity
    combos_count: int                # 有效combo数量
    combo_breakdown: List[dict]      # 每个combo的详细结果

    def __str__(self):
        return f"Equity: {self.equity:.1%} (vs {self.combos_count} combos)"

    def get_top_combos(self, n: int = 5) -> List[dict]:
        """获取equity最高的N个对手combo"""
        return sorted(
            self.combo_breakdown,
            key=lambda x: x['equity'],
            reverse=True
        )[:n]

    def get_bottom_combos(self, n: int = 5) -> List[dict]:
        """获取equity最低的N个对手combo"""
        return sorted(
            self.combo_breakdown,
            key=lambda x: x['equity']
        )[:n]
```

#### 2.4 测试用例

```python
class TestHandVsRange(unittest.TestCase):
    """测试Hand vs Range"""

    def setUp(self):
        self.calc = EquityCalculator(iterations=1000)

    def test_overpair_vs_range(self):
        """测试超对 vs 范围"""
        hero = Hand.from_str("AsAh")
        villain_range = Range("KK,QQ,JJ,AKs,AKo")
        board = Board.from_str("")

        result = self.calc.calculate_hand_vs_range(
            hero, villain_range, board, iterations=5000
        )

        # AA vs {KK,QQ,JJ,AK} 应该有75%+的equity
        self.assertGreater(result.equity, 0.75)
        self.assertLess(result.equity, 0.85)

        print(f"\nAA vs {villain_range}:")
        print(f"  Equity: {result.equity:.1%}")
        print(f"  Combos: {result.combos_count}")

    def test_top_pair_vs_calling_range(self):
        """测试顶对 vs 跟注范围"""
        hero = Hand.from_str("AhKd")
        villain_range = Range("99+,AJs+,KQs")
        board = Board.from_str("As7c2h")

        result = self.calc.calculate_hand_vs_range(
            hero, villain_range, board
        )

        print(f"\nAK on As7c2h vs {villain_range}:")
        print(f"  Equity: {result.equity:.1%}")

        # 查看最佳/最差对抗
        print("\n  Best matchups:")
        for combo_data in result.get_bottom_combos(3):
            print(f"    vs {combo_data['combo']}: {combo_data['equity']:.1%}")

        print("\n  Worst matchups:")
        for combo_data in result.get_top_combos(3):
            print(f"    vs {combo_data['combo']}: {combo_data['equity']:.1%}")
```

---

## 🎯 Phase 3: Range vs Range Equity（高级功能）

### 目标：计算范围对抗范围的平均equity

#### 3.1 API设计

```python
def calculate_range_vs_range(
    self,
    hero_range: Range,
    villain_range: Range,
    board: Board,
    samples: int = 1000
) -> float:
    """
    计算范围 vs 范围的平均equity

    采样策略：
    1. 从hero_range随机选择combo
    2. 从villain_range随机选择combo（避免冲突）
    3. 计算equity
    4. 重复samples次，返回平均值

    Args:
        hero_range: 我方范围
        villain_range: 对手范围
        board: 公共牌
        samples: 采样次数

    Returns:
        float: 平均equity (0.0-1.0)

    Example:
        >>> hero_range = Range("AA,KK,AKs")
        >>> villain_range = Range("QQ,JJ,TT")
        >>> equity = calc.calculate_range_vs_range(hero_range, villain_range, board)
        >>> print(f"Equity: {equity:.1%}")
        Equity: 80.5%
    """
```

#### 3.2 实现

```python
def calculate_range_vs_range(
    self,
    hero_range: Range,
    villain_range: Range,
    board: Board,
    samples: int = 1000,
    iterations_per_sample: int = 100
) -> float:
    """
    Range vs Range equity计算

    采用双重采样：
    - 外层：从两个范围采样combos
    - 内层：对每对combos进行Monte Carlo
    """
    import random

    # 移除死牌
    dead_cards = set(board.cards)
    hero_combos = list(hero_range.get_valid_combos(dead_cards))
    villain_combos = list(villain_range.get_valid_combos(dead_cards))

    if not hero_combos:
        return 0.0
    if not villain_combos:
        return 1.0

    total_equity = 0.0
    valid_samples = 0

    for _ in range(samples):
        # 随机选择hero combo
        hero_combo = random.choice(hero_combos)
        hero_hand = Hand.from_combo(hero_combo)

        # 选择不冲突的villain combos
        hero_cards = set(hero_hand.cards)
        available_villain = [
            c for c in villain_combos
            if not any(card in hero_cards for card in Hand.from_combo(c).cards)
        ]

        if not available_villain:
            continue

        villain_combo = random.choice(available_villain)
        villain_hand = Hand.from_combo(villain_combo)

        # 计算这对combos的equity
        result = self.calculate_equity(
            hero_hand,
            villain_hand,
            board,
            iterations=iterations_per_sample
        )

        total_equity += result.equity
        valid_samples += 1

    return total_equity / valid_samples if valid_samples > 0 else 0.5
```

#### 3.3 测试用例

```python
class TestRangeVsRange(unittest.TestCase):
    """测试Range vs Range"""

    def test_premium_vs_medium(self):
        """测试高级范围 vs 中等范围"""
        calc = EquityCalculator()

        hero_range = Range("AA,KK,AKs")
        villain_range = Range("QQ,JJ,TT,99")
        board = Board.from_str("")

        equity = calc.calculate_range_vs_range(
            hero_range,
            villain_range,
            board,
            samples=500
        )

        print(f"\n{hero_range} vs {villain_range}:")
        print(f"  Equity: {equity:.1%}")

        # AA/KK/AK vs QQ-99 应该有75-85%的equity
        self.assertGreater(equity, 0.75)
        self.assertLess(equity, 0.85)

    def test_polarized_vs_linear(self):
        """测试极化范围 vs 线性范围"""
        calc = EquityCalculator()

        # 3-bet范围：value + bluff
        hero_range = Range("QQ+,AK,A5s")
        # 防守范围：较宽
        villain_range = Range("99+,AQ+,KQs")

        board = Board.from_str("")

        equity = calc.calculate_range_vs_range(
            hero_range,
            villain_range,
            board,
            samples=500
        )

        print(f"\nPolarized vs Linear:")
        print(f"  Equity: {equity:.1%}")
```

---

## 🎯 Phase 4: Range集合操作（工具函数）

### 目标：支持Range的交集、并集、差集操作

#### 4.1 API设计

```python
class Range:
    """增强版Range类"""

    def intersect(self, other: 'Range') -> 'Range':
        """
        范围交集

        Example:
            >>> r1 = Range("AA,KK,QQ,AKs")
            >>> r2 = Range("QQ,JJ,AKs,AQs")
            >>> r3 = r1.intersect(r2)
            >>> print(r3.combos)
            {'QQ', 'AKs'}  # 共同部分
        """
        result = Range()
        result.combos = self.combos & other.combos
        return result

    def union(self, other: 'Range') -> 'Range':
        """
        范围并集

        Example:
            >>> value = Range("AA,KK")
            >>> bluff = Range("A5s,A4s")
            >>> raise_range = value.union(bluff)
            >>> print(raise_range.combos)
            {'AA', 'KK', 'A5s', 'A4s'}
        """
        result = Range()
        result.combos = self.combos | other.combos
        return result

    def subtract(self, other: 'Range') -> 'Range':
        """
        范围差集

        Example:
            >>> open_range = Range("77+,ATs+,KJs+")
            >>> vs_3bet_fold = Range("77,88,99")
            >>> call_range = open_range.subtract(vs_3bet_fold)
            # call_range = TT+,ATs+,KJs+
        """
        result = Range()
        result.combos = self.combos - other.combos
        return result

    def filter_by_board(
        self,
        board: Board,
        condition: Callable[[Hand, Board], bool]
    ) -> 'Range':
        """
        根据公共牌过滤范围

        Example:
            >>> range_obj = Range("99+,AK,AQ")
            >>> board = Board.from_str("AsKs5h")
            >>>
            >>> # 只保留有对子或更好的牌
            >>> def has_pair_or_better(hand, board):
            ...     # 实现逻辑
            ...     return True
            >>>
            >>> made_hand_range = range_obj.filter_by_board(board, has_pair_or_better)
        """
        result = Range()
        for combo in self.combos:
            hand = Hand.from_combo(combo)
            if condition(hand, board):
                result.combos.add(combo)
        return result
```

---

## 🎯 Phase 5: Multiway Equity（可选增强）

### 目标：支持3人或更多玩家的equity计算

#### 5.1 API设计

```python
def calculate_multiway(
    self,
    hero_hand: Hand,
    villain_ranges: List[Range],
    board: Board,
    samples: int = 500
) -> float:
    """
    多人底池equity计算

    Args:
        hero_hand: 我方手牌
        villain_ranges: 多个对手的范围列表
        board: 公共牌
        samples: 采样次数（多人底池计算量大，减少采样）

    Returns:
        float: 我方equity (0.0-1.0)

    Example:
        >>> hero = Hand.from_str("AsAh")
        >>> v1_range = Range("KK,QQ")
        >>> v2_range = Range("AKs,AQs")
        >>> board = Board.from_str("")
        >>>
        >>> equity = calc.calculate_multiway(
        ...     hero,
        ...     [v1_range, v2_range],
        ...     board
        ... )
        >>> print(f"3-way equity: {equity:.1%}")
        3-way equity: 65.2%  # AA在3人底池equity下降
    """
```

---

## 📊 开发计划和优先级

### Sprint 1: Range解析增强（1周）

**目标**：支持"+"符号

- [ ] 实现 `_parse_plus_notation()`
- [ ] 实现 `_expand_pair_plus()`
- [ ] 实现 `_expand_suited_plus()`
- [ ] 实现 `_expand_offsuit_plus()`
- [ ] 编写测试用例（10个）
- [ ] 文档和示例

**验收标准**：
```python
Range("77+").size() == 48          # ✅
Range("A5s+").size() == 36         # ✅
Range("QQ+,AK,A9s+").size() == 58  # ✅
```

---

### Sprint 2: Hand vs Range（2周）

**目标**：核心功能实现

- [ ] 实现 `calculate_hand_vs_range()`
- [ ] 实现 `RangeEquityResult` 数据结构
- [ ] 实现 `Range.get_valid_combos()`
- [ ] 编写测试用例（15个）
- [ ] 性能优化（并行计算）
- [ ] 文档和示例

**验收标准**：
```python
# AA vs {KK,QQ,JJ,AK} 精度 ±2%
result = calc.calculate_hand_vs_range(AA, range, board)
assert 0.75 < result.equity < 0.85
```

---

### Sprint 3: Range vs Range（2周）

**目标**：高级功能实现

- [ ] 实现 `calculate_range_vs_range()`
- [ ] 实现采样策略优化
- [ ] 实现阻挡效应处理
- [ ] 编写测试用例（15个）
- [ ] 性能优化
- [ ] 文档和示例

**验收标准**：
```python
# {AA,KK,AK} vs {QQ,JJ,TT} 精度 ±3%
equity = calc.calculate_range_vs_range(hero_range, villain_range, board)
assert 0.75 < equity < 0.85
```

---

### Sprint 4: Range集合操作（1周）

**目标**：工具函数

- [ ] 实现 `Range.intersect()`
- [ ] 实现 `Range.union()`
- [ ] 实现 `Range.subtract()`
- [ ] 实现 `Range.filter_by_board()`
- [ ] 编写测试用例（10个）
- [ ] 文档和示例

---

### Sprint 5: Multiway Equity（可选，2周）

**目标**：多人底池支持

- [ ] 实现 `calculate_multiway()`
- [ ] 实现多人采样策略
- [ ] 编写测试用例（10个）
- [ ] 性能优化
- [ ] 文档和示例

---

## 🧪 测试策略

### 单元测试覆盖

| 模块 | 当前覆盖 | 目标覆盖 |
|------|---------|---------|
| Range解析 | 25个 | 40个 (+15) |
| Hand vs Hand | 36个 | 36个 (保持) |
| Hand vs Range | 0个 | 20个 (+20) |
| Range vs Range | 0个 | 20个 (+20) |
| Range集合操作 | 0个 | 15个 (+15) |
| Multiway | 0个 | 15个 (+15) |
| **总计** | **61个** | **146个** |

### 精度验证

**Hand vs Range**：
- 至少10个场景与PokerStove对比
- 误差 < 2%

**Range vs Range**：
- 至少10个场景验证
- 误差 < 3%（采样导致的额外误差）

---

## 📈 性能优化

### 并行计算

```python
from concurrent.futures import ProcessPoolExecutor

def calculate_hand_vs_range(self, ..., parallel=True):
    if parallel and len(valid_combos) > 10:
        # 使用多进程并行计算
        with ProcessPoolExecutor() as executor:
            futures = [
                executor.submit(self._calc_single_combo, hero, combo, board)
                for combo in valid_combos
            ]
            results = [f.result() for f in futures]
    else:
        # 串行计算
        results = [...]
```

### 缓存策略

```python
from functools import lru_cache

class Range:
    @lru_cache(maxsize=1000)
    def get_valid_combos(self, dead_cards_tuple):
        """缓存valid combos结果"""
        # 实现
```

---

## 📚 文档和示例

### 用户指南

创建 `docs/RANGE_EQUITY_GUIDE.md`：

```markdown
# Range Equity使用指南

## 基础用法

### 1. 解析Range
\`\`\`python
from advisor.equity import Range

# 基础语法
r1 = Range("AA,KK,QQ")

# 使用"+"符号
r2 = Range("77+")        # 所有口袋对 >= 77
r3 = Range("A5s+")       # 所有A同花 >= A5s
r4 = Range("KTo+")       # 所有K非同花 >= KTo

# 组合语法
r5 = Range("QQ+,AK,A9s+,KJs+")
\`\`\`

### 2. Hand vs Range
\`\`\`python
from advisor.equity import Hand, Board, EquityCalculator

calc = EquityCalculator()
hero = Hand.from_str("AsKh")
villain_range = Range("QQ+,AK,AQ")
board = Board.from_str("Ah5c2d")

result = calc.calculate_hand_vs_range(hero, villain_range, board)
print(f"Equity: {result.equity:.1%}")
print(f"Combos: {result.combos_count}")
\`\`\`

### 3. Range vs Range
\`\`\`python
hero_range = Range("AA,KK,AKs")
villain_range = Range("QQ,JJ,TT")

equity = calc.calculate_range_vs_range(hero_range, villain_range, board)
print(f"Range equity: {equity:.1%}")
\`\`\`
```

---

## 🎬 总结

### 完整功能对比

| 功能 | 旧实现 | 当前新实现 | 融合后 |
|------|--------|----------|--------|
| Hand vs Hand | ✅ | ✅ | ✅ |
| Hand vs Range | ✅ | ❌ | ✅ |
| Range vs Range | ✅ | ❌ | ✅ |
| Multiway | ✅ | ❌ | ✅ |
| "+"符号解析 | ✅ | ❌ | ✅ |
| Range集合操作 | ✅ | ❌ | ✅ |
| 测试覆盖 | ❌ | ✅ 58个 | ✅ 146个 |
| 精度验证 | ❌ | ✅ 0.007% | ✅ 保持 |
| 零依赖 | ❌ Treys | ✅ | ✅ |
| **综合评分** | **7/10** | **8/10** | **10/10** |

### 预期成果

完成后将实现：
- ✅ **功能完整性**：所有Poker AI需要的equity计算功能
- ✅ **测试覆盖**：146个测试用例，覆盖所有场景
- ✅ **精度保证**：Hand vs Hand 0.007%误差，Range计算 <3%误差
- ✅ **零依赖**：Pure Python，完全可控
- ✅ **性能优化**：并行计算，缓存策略
- ✅ **用户友好**：符合poker玩家习惯的API

### 时间估算

- Sprint 1-4（必须）：6周
- Sprint 5（可选）：2周
- **总计**：6-8周

---

**下一步行动**：从Sprint 1开始，逐步实现Range解析增强功能！
