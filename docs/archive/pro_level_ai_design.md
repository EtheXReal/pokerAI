# 职业级AI决策系统设计文档

## 目标

构建达到/超越职业选手水平的德州扑克AI建议系统，针对**5人桌**（2-5位玩家）现金局。

---

## 核心设计理念

### 职业选手 vs 业余玩家的本质区别

| 维度 | 业余玩家 | 职业选手 | 我们的AI |
|------|---------|---------|---------|
| 决策依据 | 手牌强度 | 范围 vs 范围 | ✅ 范围思维 |
| 对手意识 | 忽略对手 | 根据对手调整 | ✅ 对手建模 |
| 策略类型 | 固定策略 | GTO + Exploitative | ✅ 动态混合 |
| 多人底池 | 简单处理 | 复杂equity计算 | ✅ 多对手建模 |
| 位置理解 | 基础 | 深刻理解价值 | ✅ 位置权重系统 |

---

## 系统架构：三层设计

```
┌─────────────────────────────────────────────────────────────┐
│      第3层: 动态策略层 (Dynamic Strategy Engine)             │
│                                                               │
│  输入: 对手模型 + 当前局面 + 我方范围                          │
│  输出: 6个动作的概率分布                                       │
│                                                               │
│  核心逻辑:                                                     │
│  • GTO基线策略（防止被exploit）                               │
│  • Exploitative调整（针对对手弱点）                           │
│  • 多人底池特殊处理                                           │
│  • 动态aggression调整                                        │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│      第2层: 对手建模层 (Opponent Modeling Engine)            │
│                                                               │
│  输入: 对手历史行动数据                                        │
│  输出: 对手类型 + 对手当前范围 + 统计指标                       │
│                                                               │
│  核心功能:                                                     │
│  • 实时统计对手数据 (VPIP/PFR/AF/3bet/C-bet...)             │
│  • 分类对手类型 (9种画像)                                     │
│  • 动态推断对手当前范围                                       │
│  • 识别对手倾向和弱点                                         │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│      第1层: 范围引擎层 (Range Engine)                        │
│                                                               │
│  输入: 手牌 + 公共牌 + 行动历史                               │
│  输出: 我方范围 + 对手范围 + Equity计算                       │
│                                                               │
│  核心功能:                                                     │
│  • 预定义开池/3bet/4bet范围表                                │
│  • 根据行动序列更新范围                                       │
│  • 范围 vs 范围 equity计算                                   │
│  • 考虑公共牌结构的范围优势分析                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 第1层: 范围引擎 (Range Engine)

### 1.1 预定义范围表

#### 翻前开池范围（5人桌）

基于位置的开池范围（按紧度分级）：

```python
PREFLOP_OPEN_RANGES = {
    'UTG': {
        'tight': [
            'AA', 'KK', 'QQ', 'JJ', 'TT',
            'AKs', 'AKo', 'AQs'
        ],  # 8% 范围，40 combos

        'normal': [
            ...  # tight的所有
            '99', 'AQo', 'AJs', 'KQs'
        ],  # 12% 范围，60 combos

        'loose': [
            ...  # normal的所有
            '88', '77', 'ATs', 'KJs', 'QJs', 'AJo'
        ],  # 15% 范围，75 combos
    },

    'MP': {
        'tight': [...],    # 10%, 50 combos
        'normal': [...],   # 15%, 75 combos
        'loose': [...],    # 20%, 100 combos
    },

    'CO': {
        'tight': [...],    # 15%, 75 combos
        'normal': [...],   # 22%, 110 combos
        'loose': [...],    # 28%, 140 combos
    },

    'BTN': {
        'tight': [...],    # 20%, 100 combos
        'normal': [...],   # 30%, 150 combos
        'loose': [...],    # 45%, 225 combos
    },

    'SB': {
        'tight': [...],    # 12%, 60 combos
        'normal': [...],   # 18%, 90 combos
        'loose': [...],    # 25%, 125 combos
    },

    'BB': {
        # 大盲位特殊：防守而非主动开池
        # 根据对手偷盲范围决定防守范围
        'vs_tight_steal': [...],   # 30% 防守
        'vs_normal_steal': [...],  # 40% 防守
        'vs_loose_steal': [...],   # 50% 防守
    }
}
```

**关键概念：Combo (组合)**
- 每个特定手牌有多个组合
- AA: 6 combos (A♠A♥, A♠A♦, A♠A♣, A♥A♦, A♥A♣, A♦A♣)
- AKs: 4 combos (A♠K♠, A♥K♥, A♦K♦, A♣K♣)
- AKo: 12 combos (16种组合 - 4种同花)
- 总共1326种起手牌组合

#### 3-Bet 范围

```python
THREE_BET_RANGES = {
    # 价值3-bet（强牌）
    'value': {
        'vs_UTG': ['AA', 'KK', 'QQ', 'AKs', 'AKo'],
        'vs_CO': ['AA', 'KK', 'QQ', 'JJ', 'AKs', 'AKo', 'AQs'],
        'vs_BTN': ['AA', 'KK', 'QQ', 'JJ', 'TT', '99', 'AKs', 'AKo', 'AQs', 'AQo'],
    },

    # 诈唬3-bet（弱牌，有改进潜力）
    'bluff': {
        'vs_UTG': [],  # 对UTG很少bluff 3-bet
        'vs_CO': ['A5s', 'A4s', 'K9s', 'Q9s'],
        'vs_BTN': ['A5s-A2s', 'K9s-K7s', 'Q9s', 'J9s', '65s', '54s'],  # 松得多
    },

    # 线性3-bet（包含中等强度）
    'linear': {
        'vs_UTG': ['AA', 'KK', 'QQ', 'JJ', 'TT', 'AKs', 'AKo', 'AQs'],
        'vs_CO': [...],  # 扩展到更多中等牌
        'vs_BTN': [...],
    },

    # 极化3-bet（强牌+弱牌，没有中间）
    'polarized': {
        'value': ['AA', 'KK', 'QQ', 'JJ', 'AKs', 'AKo'],
        'bluff': ['A5s', 'A4s', 'K9s', 'Q9s', '76s', '65s'],
    }
}
```

**3-Bet策略选择**：
- **对紧玩家**: 线性3-bet（他fold很多，我们用宽范围价值3-bet）
- **对松玩家**: 极化3-bet（他call很多，我们需要真牌或诈唬）
- **位置考虑**: 有位置时可以更松地3-bet

### 1.2 范围更新算法

```python
根据行动序列动态缩小/更新范围：

初始范围 → 翻前行动 → 翻牌行动 → 转牌行动 → 河牌行动

示例：对手在CO位open raise

初始假设范围：CO_normal = 22% (110 combos)

翻牌圈：K♠ 7♦ 3♣

对手c-bet 60% pot:
  → 移除弱的air hands（他可能会check这些）
  → 保留所有强牌和听牌
  → 新范围：约18% (90 combos)
    包含：所有对K+, 超对, 中对+, flush draws, 部分A-high

Hero call:

转牌：T♥

对手check:
  → 移除最强的nuts（他可能会再次下注）
  → 移除完全的air（他可能会放弃）
  → 新范围：约12% (60 combos)
    包含：中等牌力的made hands，控制底池的强牌

河牌：2♠

对手bet 75% pot:
  → 极化范围：强牌(value) + 少量bluff
  → Value: 两对+, 顶对好踢脚
  → Bluff: 错失的听牌
  → 新范围：约6% (30 combos)
```

**关键：根据对手类型调整更新规则**
- **Nit**: check通常是弱牌，bet通常是强牌
- **LAG**: check可能是陷阱，bet范围很宽
- **Fish**: 不能用逻辑推断，主要看统计数据

### 1.3 Equity计算

#### 单手牌 vs 范围

```python
计算我的具体手牌 vs 对手整个范围的equity：

我的手牌: A♠ K♦
对手范围: [QQ+, AK, AQ, KQ, JTs, T9s]  (假设40 combos)
公共牌: K♠ 7♦ 3♣

方法：
1. 枚举对手范围中的每个combo
2. 对每个combo，蒙特卡洛模拟剩余公共牌
3. 计算胜率加权平均

伪代码：
total_equity = 0
for villain_combo in villain_range:
    if conflicts_with_known_cards(villain_combo):
        continue
    equity = monte_carlo_equity(hero_hand, villain_combo, board, runs=500)
    total_equity += equity * combo_weight

average_equity = total_equity / total_combos

结果：我方equity = 68%
```

#### 范围 vs 范围（高级）

```python
计算我方整个范围 vs 对手整个范围的equity：

我方范围: [AA, KK, QQ, AK, AQ]  (35 combos)
对手范围: [JJ, TT, 99, AJ, KQ]  (50 combos)
公共牌: K♠ 7♦ 3♣

方法：
1. 对我方每个combo，计算vs对手范围的equity
2. 加权平均

my_range_equity = {
    'AA': 72%,
    'KK': 85%,  # 击中顶set
    'QQ': 68%,
    'AK': 78%,  # 顶对顶踢脚
    'AQ': 65%,
}

weighted_avg = sum(equity * combos) / total_combos
             = (72%*6 + 85%*3 + 68%*6 + 78%*16 + 65%*16) / 47
             = 73%

用途：
- 决定整体策略方向（我方范围是否有优势）
- 计算最优下注尺寸
- 判断是否应该check还是bet
```

### 1.4 公共牌结构分析

```python
分析公共牌对双方范围的影响：

关键维度：

1. 高牌 vs 低牌
   - 高牌面（K-Q-7）：开池者范围优势大
   - 低牌面（7-5-2）：大盲防守范围可能有更多小对

2. 连接性
   - 干燥面（K-7-2 rainbow）：听牌少，强牌清晰
   - 连牌面（9-8-6）：顺子听牌多，复杂度高
   - 双连面（J-T-9-8）：大量顺子组合，难以游戏

3. 同花可能
   - Rainbow（三种花色）：无同花听牌
   - 两同花：flush draw存在
   - 三同花：大量flush draws，已成同花

4. 对子
   - 无对子：标准牌面
   - 有对子（K-K-7）：葫芦可能，少人有牌

纹理评分系统：
texture_score = {
    'static': 1.0,    # K-7-2 rainbow (最干燥)
    'somewhat_static': 0.8,  # Q-9-4 two-tone
    'dynamic': 0.5,   # J-T-8 rainbow (连牌)
    'very_dynamic': 0.2,  # 9♠-8♠-7♠ (同花+连牌)
}

应用：
- 静态面：c-bet频率更高，范围更宽
- 动态面：更谨慎，需要更强牌力下注
```

---

## 第2层: 对手建模引擎

### 2.1 统计指标追踪

```python
class OpponentStats:
    """对手统计数据"""

    # 基础指标
    hands_observed: int = 0          # 观察手数
    vpip: float = 0.0                # 主动入池率
    pfr: float = 0.0                 # 翻前加注率
    af: float = 0.0                  # 激进度

    # 翻前指标
    three_bet_pct: float = 0.0       # 3-bet频率
    fold_to_three_bet: float = 0.0   # 面对3-bet弃牌率
    four_bet_pct: float = 0.0        # 4-bet频率

    # 翻后指标
    cbet_flop: float = 0.0           # 翻牌圈c-bet频率
    cbet_turn: float = 0.0           # 转牌圈c-bet频率
    cbet_river: float = 0.0          # 河牌圈c-bet频率

    fold_to_cbet_flop: float = 0.0   # 对翻牌c-bet弃牌率
    fold_to_cbet_turn: float = 0.0   # 对转牌c-bet弃牌率
    fold_to_cbet_river: float = 0.0  # 对河牌c-bet弃牌率

    raise_cbet: float = 0.0          # 加注c-bet频率
    checkraise_flop: float = 0.0     # 翻牌圈check-raise频率
    checkraise_turn: float = 0.0     # 转牌圈check-raise频率

    # 摊牌指标
    wtsd: float = 0.0                # 看到摊牌率
    w_sd: float = 0.0                # 摊牌胜率

    # 位置指标
    steal_btn: float = 0.0           # 按钮位偷盲率
    steal_co: float = 0.0            # CO位偷盲率
    fold_bb_to_steal: float = 0.0    # BB对偷盲弃牌率

    # 下注尺寸倾向
    avg_bet_size_flop: float = 0.0   # 平均翻牌下注（pot%）
    avg_bet_size_turn: float = 0.0   # 平均转牌下注
    avg_bet_size_river: float = 0.0  # 平均河牌下注

    # 高级指标（需要更多样本）
    donk_bet_pct: float = 0.0        # 主动下注频率（OOP）
    float_pct: float = 0.0           # Float频率（位置跟注后下注）
    probe_bet_pct: float = 0.0       # Probe bet频率

计算方法：

VPIP = (主动投钱手数) / (总手数)
     = (open raise + limp + call raise + 3bet + ...) / hands_observed

PFR = (翻前加注手数) / (总手数)
    = (open raise + 3bet + 4bet) / hands_observed

AF = (bet次数 + raise次数) / (call次数)
   注意：不包括check和fold

3-Bet% = (3-bet次数) / (面对raise次数)

C-Bet% = (翻前加注后翻牌下注次数) / (翻前加注后看到翻牌次数)

WTSD = (看到摊牌次数) / (看到翻牌次数)

W$SD = (摊牌赢钱次数) / (看到摊牌次数)
```

### 2.2 对手分类系统（9种画像）

```python
基于 VPIP 和 PFR 的二维分类：

              Passive          Balanced         Aggressive
              (PFR/VPIP<0.4)  (PFR/VPIP=0.6-0.8) (PFR/VPIP>0.8)
              │                │                │
Tight ────────┼────────────────┼────────────────┼────
(VPIP<22%)    │  1. Nit/Rock   │  2. TAG        │  3. LAG-Tight
              │  超紧被动       │  紧凶           │  (罕见)
              │                │                │
Medium ───────┼────────────────┼────────────────┼────
(VPIP 22-32%) │  4. Calling    │  5. Solid Reg  │  6. LAG
              │     Station    │  稳健常规       │  松凶
              │  跟注站         │                │
              │                │                │
Loose ────────┼────────────────┼────────────────┼────
(VPIP>32%)    │  7. Fish/Whale │  8. LAP        │  9. Maniac
              │  鱼玩家         │  松被动         │  疯子

详细特征：

1. Nit/Rock (超紧被动)
   识别：VPIP<18%, PFR<12%, PFR/VPIP<0.7, AF<1.5
   特征：
     - 只玩超强牌
     - 很少bluff
     - 容易被偷盲
     - 3-bet% < 3%
     - Fold to C-Bet > 65%
   弱点：可预测性极强，容易被偷底池
   样本量需求：30手

2. TAG (紧凶)
   识别：VPIP 18-25%, PFR 15-22%, PFR/VPIP>0.7, AF 2-4
   特征：
     - 接近GTO打法
     - 有位置意识
     - 会适度bluff
     - 3-bet% 5-8%
     - C-Bet% 60-70%
   弱点：较少，难以exploit
   样本量需求：50手

3. Calling Station (跟注站)
   识别：VPIP 28-40%, PFR<15%, PFR/VPIP<0.5, AF<1.2
   特征：
     - 用弱牌跟注太多
     - 很少主动加注
     - 追听牌过度
     - Fold to C-Bet < 45%
     - WTSD > 32%
   弱点：不能bluff，但可以薄价值下注
   样本量需求：40手

4. Solid Reg (稳健常规)
   识别：VPIP 22-28%, PFR 18-24%, PFR/VPIP 0.7-0.85, AF 2-3.5
   特征：
     - 平衡的打法
     - 理解位置价值
     - 混合策略
     - 有一定对手意识
   弱点：较少，默认尊重策略
   样本量需求：60手

5. LAG (松凶)
   识别：VPIP 26-35%, PFR 22-30%, PFR/VPIP>0.75, AF 3-6
   特征：
     - 范围宽但有侵略性
     - 频繁3-bet/4-bet
     - 大量偷盲/c-bet
     - 3-bet% > 10%
     - C-Bet% > 70%
   弱点：范围宽意味着边缘牌多
   样本量需求：50手

6. Fish/Whale (鱼玩家)
   识别：VPIP>38%, PFR<15%, PFR/VPIP<0.4, WTSD>30%, W$SD<48%
   特征：
     - 玩太多垃圾牌
     - 不弃牌
     - 追听牌不考虑赔率
     - 忽略位置
     - 容易tilt
   弱点：到处都是，最容易赢钱
   样本量需求：30手

7. LAP (松被动)
   识别：VPIP>32%, PFR 12-20%, AF<1.5
   特征：
     - 入池多但不激进
     - 经常limp
     - call多，raise少
     - 容易被施压
   弱点：可以用任何牌位置下注偷池
   样本量需求：40手

8. Maniac (疯子)
   识别：VPIP>38%, PFR>32%, AF>6
   特征：
     - 极度激进
     - 频繁bluff
     - 过度3-bet/4-bet
     - 下注尺寸极端
   弱点：bluff太频繁，可以宽范围call down
   样本量需求：40手

9. LAG-Tight (罕见)
   识别：VPIP<22%, PFR 18-22%, PFR/VPIP>0.8
   特征：不常见的类型，可能是短时间波动
   策略：观察更多样本再判断
```

### 2.3 对手范围推断算法

```python
class OpponentRangeEstimator:
    """根据对手类型和行动推断范围"""

    def estimate_preflop_range(self,
                               opponent_type: str,
                               action: str,
                               position: str,
                               facing_raise: bool) -> List[str]:
        """
        估计对手翻前范围

        例子：
        opponent_type = 'TAG'
        action = 'raise'
        position = 'CO'
        facing_raise = False

        返回：['AA','KK','QQ',...,'87s'] (约22%范围)
        """

        if opponent_type == 'Nit':
            ranges = TIGHT_RANGES
        elif opponent_type == 'TAG':
            ranges = TAG_RANGES
        elif opponent_type == 'LAG':
            ranges = LOOSE_RANGES
        elif opponent_type == 'Fish':
            ranges = FISH_RANGES
        # ... 其他类型

        if action == 'fold':
            return []
        elif action == 'raise' and not facing_raise:
            return ranges[position]['open']
        elif action == 'raise' and facing_raise:
            return ranges[position]['3bet']
        elif action == 'call':
            return ranges[position]['call_range']

    def update_range_postflop(self,
                              current_range: List[str],
                              action: str,
                              board: List[str],
                              opponent_type: str,
                              bet_size_pot_pct: float) -> List[str]:
        """
        根据翻后行动更新范围

        例子：
        current_range = ['AA','KK',...,'JTs'] (100 combos)
        action = 'bet'
        board = ['K♠','7♦','3♣']
        bet_size = 60% pot

        返回：缩小后的范围 (约70 combos)
        """

        if action == 'fold':
            return []

        if action == 'check':
            # 移除最强的nuts（他们可能会下注）
            return self._remove_strongest_hands(current_range, board, top_pct=0.15)

        if action == 'bet':
            # 根据下注尺寸和对手类型判断
            if opponent_type == 'Nit':
                # Nit下注通常是真牌
                return self._keep_strong_hands(current_range, board, threshold=0.65)

            elif opponent_type == 'LAG':
                # LAG下注范围宽
                if bet_size_pot_pct < 50:
                    # 小注可能是任何牌
                    return self._remove_weakest(current_range, board, bottom_pct=0.2)
                else:
                    # 大注稍微极化
                    return self._polarize_range(current_range, board,
                                                top_pct=0.6, bottom_pct=0.1)

            elif opponent_type == 'Fish':
                # Fish难以推断，主要看made hand
                return self._keep_made_hands(current_range, board)

        if action == 'raise':
            # 加注通常极化：强牌 + 少量诈唬
            if opponent_type in ['Nit', 'TAG']:
                # 紧玩家加注主要是价值
                return self._keep_very_strong(current_range, board, threshold=0.75)
            else:
                # 松玩家可能包含诈唬
                return self._polarize_range(current_range, board,
                                           top_pct=0.5, bottom_pct=0.15)

        return current_range

    def _remove_conflicting_combos(self,
                                   range_list: List[str],
                                   known_cards: List[str]) -> List[str]:
        """移除与已知牌冲突的组合"""
        # 实现：检查每个combo是否使用了已知的牌
        pass

    def _calculate_range_equity(self,
                                hero_range: List[str],
                                villain_range: List[str],
                                board: List[str]) -> float:
        """计算范围vs范围equity"""
        # 对每个hero combo，计算vs villain range的平均equity
        pass
```

### 2.4 Exploitative策略数据库

```python
EXPLOIT_STRATEGIES = {
    'Nit': {
        'preflop': {
            'steal_frequency': 0.8,      # 高频偷盲
            'fold_to_3bet': 0.3,         # 他3-bet时多弃牌
            '3bet_bluff_freq': 0.0,      # 不对他bluff 3-bet
        },
        'postflop': {
            'cbet_frequency': 0.7,       # 标准c-bet
            'bluff_frequency': 0.4,      # 较高bluff频率
            'value_bet_thin': False,     # 不要薄价值下注
            'fold_to_aggression': 0.7,   # 他激进时多弃牌
            'call_down_light': False,    # 不要轻易call down
        }
    },

    'TAG': {
        'preflop': {
            'steal_frequency': 0.5,
            'fold_to_3bet': 0.6,         # 平衡防守
            '3bet_bluff_freq': 0.05,     # 少量3-bet bluff
        },
        'postflop': {
            'cbet_frequency': 0.65,
            'bluff_frequency': 0.25,     # 适度bluff
            'value_bet_thin': False,     # 不要过度薄
            'fold_to_aggression': 0.55,  # 平衡决策
            'call_down_light': False,
        }
    },

    'Calling_Station': {
        'preflop': {
            'steal_frequency': 0.4,      # 他会call偷盲
            'fold_to_3bet': 0.5,
            '3bet_bluff_freq': 0.0,      # 绝不bluff 3-bet
        },
        'postflop': {
            'cbet_frequency': 0.4,       # 减少c-bet（他不弃牌）
            'bluff_frequency': 0.05,     # ⚠️ 几乎不bluff
            'value_bet_thin': True,      # ✅ 薄价值下注
            'fold_to_aggression': 0.5,
            'call_down_light': False,
        }
    },

    'LAG': {
        'preflop': {
            'steal_frequency': 0.3,      # 他会反击
            'fold_to_3bet': 0.7,         # 他3-bet范围宽，可以多弃牌
            '3bet_bluff_freq': 0.1,      # 增加3-bet频率
            '4bet_bluff_freq': 0.05,     # 可以偶尔4-bet bluff
        },
        'postflop': {
            'cbet_frequency': 0.5,       # 他经常float
            'bluff_frequency': 0.15,     # 减少bluff
            'value_bet_thin': True,      # 他call范围宽
            'fold_to_aggression': 0.4,   # 他激进时不要过度弃牌
            'call_down_light': True,     # ✅ 用中等牌call down
            'slowplay_freq': 0.2,        # 增加慢打频率
        }
    },

    'Fish': {
        'preflop': {
            'steal_frequency': 0.6,
            'fold_to_3bet': 0.5,
            '3bet_bluff_freq': 0.0,
            'isolate_freq': 0.8,         # ✅ 高频隔离加注
        },
        'postflop': {
            'cbet_frequency': 0.7,
            'bluff_frequency': 0.0,      # ⚠️ 绝不bluff
            'value_bet_thin': True,      # ✅ 极薄价值下注
            'value_bet_sizing': 0.8,     # ✅ 大尺寸价值下注
            'fold_to_aggression': 0.4,   # 他可能用弱牌激进
            'call_down_light': False,
            'barrel_frequency': 0.8,     # 持续多条街下注
        }
    },

    'Maniac': {
        'preflop': {
            'steal_frequency': 0.2,      # 他会疯狂反击
            'fold_to_3bet': 0.8,         # 他3-bet太多
            '3bet_bluff_freq': 0.0,
            '4bet_value_only': True,     # 只用价值牌4-bet
        },
        'postflop': {
            'cbet_frequency': 0.3,       # 让他bluff
            'bluff_frequency': 0.0,      # 绝不bluff
            'value_bet_thin': False,     # 不要复杂化
            'fold_to_aggression': 0.2,   # ✅ 他bluff太多，多call
            'call_down_light': True,     # ✅ 宽范围bluff catch
            'checkraise_freq': 0.05,     # 偶尔check-raise陷阱
            'slowplay_freq': 0.3,        # 经常慢打
        }
    }
}
```

---

## 第3层: 动态策略引擎

### 3.1 决策因素权重系统

```python
考虑因素（按重要性排序）：

1. 位置 (Position) - 权重: 25%
   - 按钮位 vs UTG的策略差异巨大
   - 翻后有位置 = 信息优势 + 操控底池能力

2. 对手类型 (Opponent Type) - 权重: 20%
   - 对Fish和对TAG的打法完全不同
   - Exploitative调整的核心依据

3. 我方范围优势 (Range Advantage) - 权重: 18%
   - 谁的范围在这个牌面更强
   - 决定是否应该持续施压

4. 筹码深度 (Stack Depth / SPR) - 权重: 15%
   - SPR < 3: 简化决策，倾向commit
   - SPR > 10: 需要多街规划

5. 底池赔率 (Pot Odds) - 权重: 12%
   - 数学基础
   - 决定是否有直接赔率跟注

6. 我方牌力 (Hand Strength / Equity) - 权重: 10%
   - 不是孤立的"我拿什么牌"
   - 而是"我的牌在我的范围中的相对强度"

综合评分公式：

decision_score = (
    position_factor * 0.25 +
    opponent_exploit * 0.20 +
    range_advantage * 0.18 +
    spr_factor * 0.15 +
    pot_odds_factor * 0.12 +
    equity_factor * 0.10
)

每个因素返回[-1, 1]的值：
  1.0 = 极有利，应该激进
  0.0 = 中性
 -1.0 = 极不利，应该保守/弃牌
```

### 3.2 GTO基线 + Exploitative调整

```python
两阶段决策：

Stage 1: GTO基线策略
  → 防止被exploit的平衡策略
  → 基于范围、位置、SPR的理论最优打法

Stage 2: Exploitative调整
  → 根据对手弱点偏离GTO
  → 调整幅度取决于：
    - 对手偏离GTO的程度
    - 样本量的置信度
    - 风险承受度

混合公式：

final_strategy = (
    GTO_baseline * (1 - exploit_weight) +
    exploitative_adjustment * exploit_weight
)

exploit_weight计算：

exploit_weight = min(
    opponent_deviation * confidence_factor * aggression_setting,
    0.7  # 最多偏离GTO 70%
)

opponent_deviation: 对手偏离GTO的程度 [0, 1]
  - Nit: 0.8 (严重偏离)
  - Fish: 0.9 (极度偏离)
  - TAG: 0.2 (轻微偏离)
  - Maniac: 0.85

confidence_factor: 样本量置信度 [0, 1]
  - hands < 30: 0.3
  - hands 30-50: 0.6
  - hands 50-100: 0.8
  - hands > 100: 1.0

aggression_setting: 用户设置 [0, 1]
  - Conservative: 0.3 (更接近GTO)
  - Balanced: 0.6
  - Exploitative: 0.9 (最大化exploit)

示例：

对手是Fish (deviation=0.9), 观察了60手 (confidence=0.8), 用户设置Balanced (0.6)
exploit_weight = 0.9 * 0.8 * 0.6 = 0.432

GTO建议: call 60%, fold 40%
Exploit建议: call 80%, fold 20% (Fish不bluff，可以多call)

最终:
  call: 0.6 * (1-0.432) + 0.8 * 0.432 = 0.341 + 0.346 = 68.7%
  fold: 0.4 * (1-0.432) + 0.2 * 0.432 = 0.227 + 0.086 = 31.3%
```

### 3.3 多人底池特殊处理

```python
5人桌的特殊考虑（vs 单挑）：

1. 范围收紧
   - 需要同时击败多个对手
   - 边缘牌的EV下降

   多人底池equity调整：
   adjusted_equity = raw_equity * (1 - 0.1 * num_opponents_behind)

   例：AJ在2人底池equity=65%，在4人底池约=55%

2. 位置价值放大
   - 多人底池中，晚位置的信息优势更大
   - 早位置更容易被squeeze（多次加注）

3. 隐含赔率增加
   - 听牌成牌后可以从多人获利
   - 小对子找set的价值上升

   implied_odds_multiplier = 1 + 0.3 * (num_opponents - 1)

   例：3人底池，隐含赔率提高60%

4. Bluff频率下降
   - 需要同时让多人弃牌，难度指数增长
   - 多人底池更倾向showdown value

   bluff_frequency_adj = base_bluff_freq * 0.5^(num_opponents - 1)

   例：单挑bluff 30%，3人底池降到7.5%

5. 下注尺寸调整
   - 价值下注可以更大（多人支付）
   - 保护性下注需要更大（防止多人追牌）

   value_bet_size = base_size * (1 + 0.15 * num_opponents)
   protection_bet_size = max(0.75 * pot, base_size)

6. 死钱 (Dead Money) 价值
   - 翻前有limper时，隔离加注价值高
   - 已弃牌玩家的投入是死钱，提高赔率

   pot_odds = to_call / (pot + to_call + dead_money)

特殊场景：

场景A：翻前多人limp
  → 隔离加注（Isolation Raise）
  → 范围：中等及以上强度
  → 尺寸：3BB + 1BB per limper
  → 目的：单挑limp对手（通常弱玩家）

场景B：翻前多人call raise
  → c-bet频率降低
  → 只用强牌/强听牌下注
  → 中等牌倾向check-call或check-fold

场景C：翻牌圈多人check to我
  → 位置下注价值高
  → 但需要真牌（多人容易有牌）
  → 尺寸：50-60% pot（不要太大）

场景D：我在中间位，前面bet + call
  → Cold call范围极紧
  → 需要能击败两个范围
  → 考虑squeeze（加注）的机会
```

### 3.4 动态Aggression调整

```python
根据局面动态调整激进度：

基础aggression level = f(
    我方范围强度,
    对手类型,
    位置,
    筹码深度,
    历史互动
)

场景1：我有范围优势 + 好位置
  → 高频c-bet (70-80%)
  → 可以多次barrel (转牌/河牌继续下注)
  → 增加下注尺寸

场景2：对手是Nit + 他check
  → 极高bluff频率 (60%+)
  → 他弃牌太多，exploit机会

场景3：对手是Calling Station
  → 几乎不bluff (5%)
  → 只用真牌下注
  → 薄价值下注

场景4：筹码深度 > 150BB
  → 降低激进度
  → 保护筹码
  → 避免边缘spot

场景5：短筹码 < 30BB
  → 简化策略
  → Push/fold更多
  → 减少fancy play

场景6：对手刚刚bad beat（可能tilt）
  → 增加激进度
  → 他可能loosening up
  → 预期他会用弱牌激进

历史互动记忆：

recent_history_weight = 0.3  # 最近历史权重30%

if opponent_just_bluffed_me:
    # 他刚bluff成功，可能会再次尝试
    expect_bluff_freq += 0.15
    call_down_wider = True

if i_just_bluffed_opponent:
    # 我刚bluff成功，他可能警觉
    reduce_bluff_freq = 0.1
    expect_light_call += 0.1

if opponent_folded_strong_hand:
    # 他之前弃了强牌，可能后悔，下次更sticky
    expect_fold_less = True
    require_stronger_bluff = True
```

---

## Phase 2 实施计划

### Phase 2.1: 范围引擎 (3-4周)

**Week 1-2: 范围数据库和基础框架**

目标：
- [ ] 定义完整的5人桌范围表
- [ ] 实现范围类和操作方法
- [ ] 实现范围vs范围equity计算

交付：
```python
# advisor/range_engine/range_database.py
PREFLOP_RANGES_5MAX = {...}  # 完整范围定义
THREE_BET_RANGES = {...}
FOUR_BET_RANGES = {...}

# advisor/range_engine/range.py
class Range:
    def __init__(self, combos: List[str])
    def remove_conflicting(self, known_cards: List[str]) -> Range
    def filter_by_strength(self, threshold: float) -> Range
    def equity_vs_range(self, villain_range: Range, board: List[str]) -> float

# advisor/range_engine/board_analyzer.py
class BoardAnalyzer:
    def analyze_texture(self, board: List[str]) -> Dict
    def range_advantage(self, range1: Range, range2: Range, board) -> float
```

测试：
- 验证范围定义的combo数量正确
- Equity计算与已知结果对比（如PokerStove）
- 公共牌分析分类准确

**Week 3-4: 范围推断算法**

目标：
- [ ] 实现翻前范围估计
- [ ] 实现翻后范围更新
- [ ] 多人底池范围处理

交付：
```python
# advisor/range_engine/range_estimator.py
class RangeEstimator:
    def estimate_open_range(position, player_type) -> Range
    def estimate_3bet_range(position, player_type, vs_position) -> Range
    def update_postflop(current_range, action, board, context) -> Range
    def estimate_multiway(position, player_types, actions) -> Dict[player_id, Range]
```

测试：
- 典型场景范围推断准确性
- 与专业玩家的范围假设对比

---

### Phase 2.2: 对手建模引擎 (2-3周)

**Week 1: 统计追踪系统**

目标：
- [ ] 实现对手统计数据结构
- [ ] 实时更新统计指标
- [ ] 持久化对手数据（保存/加载）

交付：
```python
# advisor/opponent_modeling/stats_tracker.py
class OpponentStatsTracker:
    def __init__(self, player_id: str)
    def update_preflop_action(self, action, position, facing_raise)
    def update_postflop_action(self, action, street, context)
    def get_stats(self) -> OpponentStats
    def save_to_db(self, filepath)
    def load_from_db(self, filepath)

# advisor/opponent_modeling/database.py
# SQLite数据库，存储历史对手数据
# 表结构：players, hands, actions, stats
```

测试：
- 统计计算准确性
- 数据持久化完整性
- 多手牌累积统计正确

**Week 2: 对手分类器**

目标：
- [ ] 实现9种玩家类型分类器
- [ ] 置信度评分系统
- [ ] 动态重分类（随样本增加）

交付：
```python
# advisor/opponent_modeling/classifier.py
class OpponentClassifier:
    def classify(self, stats: OpponentStats) -> Tuple[str, float]:
        # 返回：(类型, 置信度)
        # 例：('LAG', 0.85)

    def get_tendencies(self, player_type: str) -> Dict:
        # 返回该类型的典型倾向

    def confidence_level(self, hands_observed: int) -> float:
        # 样本量→置信度映射
```

测试：
- 模拟数据分类准确性
- 边界情况处理（样本少时）

**Week 3: Exploitative策略库**

目标：
- [ ] 针对9种类型的exploit策略
- [ ] 策略参数可配置
- [ ] 策略混合权重计算

交付：
```python
# advisor/opponent_modeling/exploit_策略.py
class ExploitStrategy:
    def get_adjustments(self, opponent_type: str, context: Dict) -> Dict:
        # 返回策略调整参数
        # 例：{'bluff_freq': -0.2, 'value_bet_thin': True}

    def calculate_exploit_weight(self,
                                 opponent_type: str,
                                 confidence: float,
                                 user_setting: str) -> float:
        # GTO vs Exploit的混合权重
```

---

### Phase 2.3: 动态策略引擎 (4-5周)

**Week 1-2: GTO基线策略**

目标：
- [ ] 翻前GTO近似策略
- [ ] 翻后基于equity和范围的策略
- [ ] 多人底池调整

交付：
```python
# advisor/strategy_engine/gto_baseline.py
class GTOStrategy:
    def preflop_strategy(self,
                        position: str,
                        facing_action: str,
                        num_players: int) -> Dict[str, float]:
        # 返回动作概率分布

    def postflop_strategy(self,
                         hero_range: Range,
                         villain_ranges: Dict[str, Range],
                         board: List[str],
                         context: Dict) -> Dict[str, float]:
        # 基于范围equity的策略

    def multiway_adjustment(self,
                           base_strategy: Dict,
                           num_opponents: int) -> Dict:
        # 多人底池调整
```

理论基础：
- MDF (Minimum Defense Frequency) = pot / (pot + bet)
- Optimal bluff frequency = risk / (risk + reward)
- c-bet frequency基于range advantage

**Week 3: Exploitative策略整合**

目标：
- [ ] GTO + Exploit混合
- [ ] 动态aggression调整
- [ ] 历史互动记忆

交付：
```python
# advisor/strategy_engine/exploitative.py
class ExploitativeEngine:
    def __init__(self, gto_baseline, opponent_model)

    def decide(self,
              state: Dict,
              opponent_stats: OpponentStats,
              user_settings: Dict) -> Dict:
        # 主决策函数

        gto_strategy = self.gto_baseline.get_strategy(state)
        exploit_adj = self.opponent_model.get_exploit(opponent_stats)

        final_strategy = self.blend_strategies(
            gto_strategy,
            exploit_adj,
            weight=self.calculate_exploit_weight(...)
        )

        return {
            'action_probs': final_strategy,
            'recommended_action': max(final_strategy, key=final_strategy.get),
            'reasoning': self.generate_reasoning(...)
        }
```

**Week 4-5: 集成和优化**

目标：
- [ ] 端到端集成三层引擎
- [ ] 性能优化（目标<100ms）
- [ ] 决策质量验证

交付：
```python
# advisor/pro_advisor.py
class ProLevelAdvisor:
    def __init__(self):
        self.range_engine = RangeEngine()
        self.opponent_model = OpponentModel()
        self.strategy_engine = StrategyEngine()

    def advise(self, game_state: Dict) -> Dict:
        # 完整决策流程

        # 1. 范围推断
        ranges = self.range_engine.estimate_ranges(game_state)

        # 2. 对手建模
        opponent_profiles = self.opponent_model.analyze_opponents(game_state)

        # 3. 策略决策
        decision = self.strategy_engine.decide(
            game_state,
            ranges,
            opponent_profiles
        )

        return decision
```

---

### Phase 2.4: 测试与验证 (2-3周)

**测试维度**：

1. **单元测试**
   - 每个模块的功能正确性
   - 边界情况处理
   - 性能benchmark

2. **集成测试**
   - 端到端决策流程
   - 多场景覆盖
   - 错误处理

3. **策略质量测试**

   a. 对局模拟 (10,000手)
   ```
   ProAdvisor vs Random: 期望 +60 BB/100
   ProAdvisor vs SimpleHeuristic: 期望 +15 BB/100
   ProAdvisor vs 不同类型对手:
     - vs Nit: +25 BB/100
     - vs TAG: +5 BB/100
     - vs Fish: +45 BB/100
     - vs LAG: +10 BB/100
     - vs Maniac: +35 BB/100
   ```

   b. 典型场景测试 (50+场景)
   ```
   专家标注的"正确决策"
   AI决策与专家一致率 > 75%
   ```

   c. Exploitative测试
   ```
   对每种对手类型：
   - 识别率 > 85% (50手后)
   - Exploit调整方向正确
   - 收益率显著高于GTO baseline
   ```

4. **职业玩家评审**
   - 邀请职业玩家试用
   - 收集反馈
   - 调整参数

**交付：测试报告**
```
docs/phase2_test_report.md
- 单元测试覆盖率
- 性能benchmark结果
- 对局模拟结果
- 场景测试准确率
- 专家评审反馈
- 已知问题和限制
```

---

## 总结：达到职业水平的关键

### 核心差异化要素

1. ✅ **范围思维**
   - 不是"我拿AK怎么打"
   - 而是"我的范围 vs 对手范围在这个牌面的优势"

2. ✅ **对手建模**
   - 9种玩家类型精确分类
   - 实时统计追踪
   - Exploitative策略调整

3. ✅ **多因素综合决策**
   - 位置、筹码深度、对手类型、范围优势...
   - 权重系统量化每个因素
   - 动态aggression调整

4. ✅ **GTO + Exploit混合**
   - GTO作为基线，防止被exploit
   - 根据对手弱点动态调整
   - 样本量决定偏离程度

5. ✅ **5人桌特殊处理**
   - 多人底池equity调整
   - Bluff频率降低
   - 隐含赔率增加

### 时间线

```
Phase 2.1: 范围引擎          3-4周
Phase 2.2: 对手建模          2-3周
Phase 2.3: 策略引擎          4-5周
Phase 2.4: 测试验证          2-3周
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
总计:                       11-15周 (约3-4个月)
```

### 成功标准

- [ ] vs Random: +60 BB/100
- [ ] vs Fish: +45 BB/100
- [ ] vs TAG: break-even到+5 BB/100
- [ ] 典型场景专家一致率 > 75%
- [ ] 决策延迟 < 100ms
- [ ] 职业玩家评分 > 7/10

---

## 附录：技术栈

```python
# 核心依赖
treys==0.1.8          # 已有
numpy>=1.24.0         # 数值计算
scipy>=1.10.0         # 统计函数

# 数据存储
sqlite3               # 对手数据库（Python内置）

# 可选优化
numba>=0.57.0         # JIT加速equity计算
joblib>=1.3.0         # 并行处理

# 测试
pytest>=7.4.0
pytest-benchmark      # 性能测试
```

---

**下一步：开始Phase 2.1实施**
