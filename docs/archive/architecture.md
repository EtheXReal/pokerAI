# POJ 实时建议器 - 完整技术架构 (职业级)

> **设计目标**: 达到/超越职业选手水平的德州扑克AI建议系统
> **目标桌型**: 5人桌 (2-5位玩家) 现金局
> **核心理念**: 范围思维 + 对手建模 + GTO&Exploitative混合策略

## 系统概览

```
┌─────────────────────────────────────────────────────────────┐
│                    网页扑克游戏界面                          │
│               (PokerStars / GGPoker / etc)                  │
│                     【5人桌】                                │
└────────────────────┬────────────────────────────────────────┘
                     │
                 【OCR捕获】
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                  数据捕获层 (Capture Layer)                  │
│  • OCRCapture: 屏幕识别 (通用方案)                           │
│  • 捕获字段: 手牌/公共牌/底池/筹码/位置/对手行动              │
│  • 延迟: ~1秒                                                │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│               游戏环境层 (Environment Layer)                 │
│  • HeadsUpPokerEnv: 核心游戏引擎 (扩展支持5人)               │
│  • 规则校验、动作计算、合法掩码                              │
│  【已完成 ✓】                                                │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│           职业级建议器核心 (Pro-Level Advisor Core)           │
│                   【三层架构设计】                            │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  第3层: 动态策略引擎 (Dynamic Strategy Engine)         │ │
│  │  • GTO基线策略                                         │ │
│  │  • Exploitative调整 (针对对手弱点)                     │ │
│  │  • 多人底池特殊处理                                    │ │
│  │  • 动态aggression调整                                 │ │
│  │  延迟: <100ms                                          │ │
│  └────────────────────────────────────────────────────────┘ │
│                     ↑                                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  第2层: 对手建模引擎 (Opponent Modeling Engine)        │ │
│  │  • 实时统计追踪 (VPIP/PFR/AF/3bet/C-bet...)           │ │
│  │  • 9种玩家类型分类                                     │ │
│  │  • 对手范围推断                                        │ │
│  │  • Exploitative策略库                                 │ │
│  │  持久化: SQLite数据库                                  │ │
│  └────────────────────────────────────────────────────────┘ │
│                     ↑                                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  第1层: 范围引擎 (Range Engine)                        │ │
│  │  • 预定义5人桌范围表 (位置/强度分级)                   │ │
│  │  • 动态范围更新 (根据行动序列)                         │ │
│  │  • 范围vs范围 Equity计算                              │ │
│  │  • 公共牌结构分析                                      │ │
│  └────────────────────────────────────────────────────────┘ │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│         解释生成层 (Explainer Layer - 可选/后期)              │
│  • RuleBased: 规则模板 (<1ms) 【暂时搁置】                   │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                  展示层 (Presentation Layer)                 │
│  • 桌面悬浮窗: 实时显示建议                                  │
│  • CLI工具: 开发测试用                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 核心模块设计

### 1. 数据捕获层 (Capture)

#### 1.1 OCR屏幕识别

**文件**: `capture/ocr_capture.py`

```python
class OCRCapture:
    """通用屏幕识别，支持任意扑克网站"""

    def __init__(self, site_config: dict):
        self.regions = site_config['regions']
        self.card_templates = self._load_card_templates()

    def capture_state(self) -> dict:
        """捕获当前游戏状态"""
        screenshot = pyautogui.screenshot()

        return {
            'board': self._match_cards(screenshot, self.regions['board']),
            'hero_hole': self._match_cards(screenshot, self.regions['hole']),
            'pot': self._ocr_number(screenshot, self.regions['pot']),
            'hero_stack': self._ocr_number(screenshot, self.regions['hero_stack']),
            'villain_stack': self._ocr_number(screenshot, self.regions['villain_stack']),
            'to_call': self._ocr_number(screenshot, self.regions['bet']),
            'btn_is_hero': self._detect_button(screenshot),
            'street': self._infer_street(board_count),
            'timestamp': time.time()
        }

    def _match_cards(self, img, region) -> List[str]:
        """模板匹配识别牌面（快速且准确）"""
        # 使用OpenCV模板匹配
        pass

    def _ocr_number(self, img, region) -> float:
        """OCR识别数字（筹码/底池）"""
        # 图像预处理 + Tesseract OCR
        pass
```

**配置文件**: `configs/sites/pokerstars.json`

```json
{
  "site_name": "PokerStars",
  "window_title": "PokerStars",
  "resolution": "1920x1080",
  "regions": {
    "board": {"x": 700, "y": 400, "w": 520, "h": 100},
    "hole": {"x": 860, "y": 650, "w": 200, "h": 80},
    "pot": {"x": 900, "y": 350, "w": 120, "h": 40},
    "hero_stack": {"x": 860, "y": 750, "w": 100, "h": 30},
    "villain_stack": {"x": 860, "y": 200, "w": 100, "h": 30},
    "bet": {"x": 950, "y": 500, "w": 100, "h": 30},
    "button": {"x": 820, "y": 720, "w": 30, "h": 30}
  },
  "card_templates_dir": "assets/cards/pokerstars"
}
```

#### 1.2 浏览器扩展桥接

**文件**: `capture/extension_bridge.py`

```python
class ExtensionBridge:
    """连接浏览器扩展，高速直接读取DOM"""

    def __init__(self, websocket_port=8765):
        self.ws_server = WebSocketServer(port=websocket_port)

    def is_connected(self) -> bool:
        return self.ws_server.has_client()

    async def get_state(self) -> dict:
        """从扩展获取状态（延迟<50ms）"""
        return await self.ws_server.request_state()
```

**浏览器扩展**: `extension/content.js`

```javascript
// Chrome扩展 - 内容脚本
const ws = new WebSocket('ws://localhost:8765');

ws.onmessage = (event) => {
  if (event.data === 'GET_STATE') {
    const state = extractGameState();
    ws.send(JSON.stringify(state));
  }
};

function extractGameState() {
  // 针对特定网站的DOM选择器
  return {
    board: Array.from(document.querySelectorAll('.board-card'))
              .map(el => el.dataset.card),
    hero_hole: Array.from(document.querySelectorAll('.hero-card'))
                  .map(el => el.dataset.card),
    pot: parseFloat(document.querySelector('.pot-value').innerText),
    // ...
  };
}
```

---

### 2. 建议器核心 (Advisor)

#### 2.1 快速启发式 (Fast Heuristic)

**文件**: `advisor/fast_heuristic.py`

```python
class FastHeuristicAdvisor:
    """基于HS/EHS的快速建议，延迟<100ms"""

    def advise(self, state: dict) -> dict:
        start = time.perf_counter()

        # 1. 评估牌力 (~20ms)
        hs = hand_strength(
            state['hero_hole'],
            state['board'],
            nsamples=300
        )

        ehs = effective_hand_strength(
            state['hero_hole'],
            state['board'],
            nsamples=300
        )

        # 2. 计算SPR
        spr = state['hero_stack'] / max(state['pot'], 1)

        # 3. 策略映射
        if state['street'] == 'preflop':
            probs = self._preflop_strategy(state['hero_hole'], state)
        else:
            probs = self._postflop_strategy(ehs, spr, state)

        # 4. 选择动作
        action = max(probs, key=probs.get)

        latency = (time.perf_counter() - start) * 1000

        return {
            'action': action,
            'probs': probs,
            'ev_hint': {
                'hs': round(hs, 3),
                'ehs': round(ehs, 3),
                'spr': round(spr, 2)
            },
            'latency_ms': round(latency, 1)
        }

    def _postflop_strategy(self, ehs: float, spr: float, state: dict) -> dict:
        """翻牌后策略"""
        to_call = state['to_call']
        pot = state['pot']

        # 超强牌 (EHS > 75%)
        if ehs > 0.75:
            if to_call == 0:  # 未开池
                return {'fold': 0, 'call': 0.1, 'r33': 0.2,
                        'r66': 0.4, 'r100': 0.2, 'allin': 0.1}
            else:  # 面对下注
                pot_odds = to_call / (pot + to_call)
                if to_call < state['hero_stack'] * 0.3:
                    return {'fold': 0, 'call': 0.2, 'r33': 0.3,
                            'r66': 0.3, 'r100': 0.2, 'allin': 0}
                else:
                    return {'fold': 0, 'call': 0.5, 'r33': 0,
                            'r66': 0.2, 'r100': 0.1, 'allin': 0.2}

        # 强牌 (EHS 60-75%)
        elif ehs > 0.60:
            return {'fold': 0, 'call': 0.3, 'r33': 0.3,
                    'r66': 0.3, 'r100': 0.1, 'allin': 0}

        # 中等牌 (EHS 45-60%)
        elif ehs > 0.45:
            pot_odds = to_call / (pot + to_call) if to_call > 0 else 0
            if ehs > pot_odds + 0.1:  # 有足够胜率
                return {'fold': 0.1, 'call': 0.7, 'r33': 0.2,
                        'r66': 0, 'r100': 0, 'allin': 0}
            else:
                return {'fold': 0.8, 'call': 0.2, 'r33': 0,
                        'r66': 0, 'r100': 0, 'allin': 0}

        # 弱牌 (EHS < 45%)
        else:
            if to_call == 0:  # 可以过牌
                return {'fold': 0, 'call': 1.0, 'r33': 0,
                        'r66': 0, 'r100': 0, 'allin': 0}
            elif to_call < pot * 0.3:  # 小额下注，偶尔诈唬
                return {'fold': 0.7, 'call': 0.1, 'r33': 0,
                        'r66': 0.1, 'r100': 0.1, 'allin': 0}
            else:
                return {'fold': 1.0, 'call': 0, 'r33': 0,
                        'r66': 0, 'r100': 0, 'allin': 0}
```

#### 2.2 范围对抗 (Range-Based)

**文件**: `advisor/range_based.py`

```python
class RangeBasedAdvisor:
    """基于对手范围的精确评估，延迟1-3秒"""

    def advise(self, state: dict) -> dict:
        start = time.perf_counter()

        # 1. 估计对手范围
        villain_range = self._estimate_villain_range(state)

        # 2. 对抗范围计算胜率
        equity = hand_strength(
            state['hero_hole'],
            state['board'],
            villain_range=villain_range,
            nsamples=1000  # 更高精度
        )

        # 3. 计算各动作EV
        action_evs = {}
        for action in ['fold', 'call', 'r33', 'r66', 'r100', 'allin']:
            action_evs[action] = self._calculate_action_ev(
                state, action, equity, villain_range
            )

        # 4. 转换为概率分布（softmax）
        probs = self._softmax_policy(action_evs, temperature=0.5)

        latency = (time.perf_counter() - start) * 1000

        return {
            'action': max(probs, key=probs.get),
            'probs': probs,
            'ev_hint': {
                'equity': round(equity, 3),
                'action_evs': {k: round(v, 2) for k, v in action_evs.items()},
                'villain_range_size': len(villain_range)
            },
            'latency_ms': round(latency, 1)
        }

    def _estimate_villain_range(self, state: dict) -> List[Tuple[int, int]]:
        """根据行动历史估计对手范围"""
        # 简化实现：基于规则
        # 未来可用ML模型
        pass

    def _calculate_action_ev(self, state, action, equity, villain_range) -> float:
        """计算单个动作的期望值"""
        # 简化EV计算
        # EV(call) = equity * pot - (1-equity) * to_call
        # EV(raise) = fold_equity * pot + (1-fold_equity) * [equity * new_pot - ...]
        pass
```

---

### 3. 解释生成层 (Explainer)

#### 3.1 规则模板

**文件**: `advisor/explainer/rule_based.py`

```python
class RuleBasedExplainer:
    """规则模板生成解释，延迟<1ms"""

    def explain(self, state: dict, decision: dict) -> str:
        components = []

        # 1. 牌力
        ehs = decision['ev_hint'].get('ehs', 0)
        if ehs > 0.75:
            components.append("超强牌")
        elif ehs > 0.60:
            components.append("强牌")
        elif ehs > 0.45:
            components.append("中等牌")
        else:
            components.append("弱牌")

        # 2. 位置
        if state.get('btn_is_hero'):
            components.append("位置优势")

        # 3. 公共牌
        if len(state.get('board_cards', [])) >= 3:
            texture = self._board_texture(state['board_cards'])
            components.append(texture)

        # 4. 动作原因
        action = decision['action']
        if action in ['r33', 'r66', 'r100']:
            if ehs > 0.65:
                components.append("→ 价值下注")
            else:
                components.append("→ 半诈唬")
        elif action == 'call':
            components.append("→ 保留决策权")
        elif action == 'fold':
            components.append("→ 牌力不足")

        return " | ".join(components)

    def _board_texture(self, board: List[str]) -> str:
        """分析公共牌结构"""
        suits = [c[1] for c in board]
        ranks = [c[0] for c in board]

        if suits.count(suits[0]) >= 3:
            return "同花面"
        elif self._is_connected(ranks):
            return "连牌面"
        else:
            return "干燥面"
```

#### 3.2 LLM增强（可选）

**文件**: `advisor/explainer/llm_enhanced.py`

```python
class LLMExplainer:
    """LLM增强解释，延迟1-3秒"""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.base_explainer = RuleBasedExplainer()

    def explain(self, state: dict, decision: dict,
                use_llm: bool = True) -> str:
        # 快速降级
        if not use_llm:
            return self.base_explainer.explain(state, decision)

        # 构建prompt
        prompt = self._build_prompt(state, decision)

        try:
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=60,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            # 降级到规则模板
            return self.base_explainer.explain(state, decision)

    def _build_prompt(self, state: dict, decision: dict) -> str:
        base = self.base_explainer.explain(state, decision)

        return f"""你是德州扑克教练，用一句话(15-25字)解释这个决策。

局面：
- 手牌: {state['hero_hole']}
- 公共牌: {state.get('board_cards', '未发')}
- 底池: {state['pot']}BB, 需跟注: {state['to_call']}BB
- 胜率估计: {decision['ev_hint'].get('ehs', 0):.0%}

建议: {decision['action']} ({decision['probs'][decision['action']]:.0%})

基础分析: {base}

用口语化一句话解释(直接输出，不要引号)："""
```

---

### 4. 展示层 (Presentation)

#### 4.1 桌面悬浮窗

**文件**: `ui/overlay.py`

```python
import tkinter as tk
from tkinter import ttk

class OverlayWindow:
    """桌面悬浮窗，实时显示建议"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("POJ Advisor")
        self.root.attributes('-topmost', True)  # 置顶
        self.root.attributes('-alpha', 0.9)     # 半透明

        self._setup_ui()

    def _setup_ui(self):
        # 主要建议
        self.action_label = ttk.Label(
            self.root,
            text="等待局面...",
            font=('Arial', 24, 'bold')
        )
        self.action_label.pack(pady=10)

        # 概率分布
        self.probs_frame = ttk.Frame(self.root)
        self.probs_frame.pack()

        # 解释文本
        self.explanation_label = ttk.Label(
            self.root,
            text="",
            font=('Arial', 12),
            wraplength=300
        )
        self.explanation_label.pack(pady=10)

        # EV提示
        self.ev_label = ttk.Label(self.root, text="")
        self.ev_label.pack()

    def update_advice(self, decision: dict, explanation: str):
        """更新显示"""
        # 主建议
        action = decision['action'].upper()
        self.action_label.config(text=f"建议: {action}")

        # 概率
        probs_text = " | ".join([
            f"{k}: {v:.0%}"
            for k, v in decision['probs'].items()
            if v > 0.05
        ])

        # 解释
        self.explanation_label.config(text=explanation)

        # EV
        ev_hint = decision.get('ev_hint', {})
        ev_text = f"胜率: {ev_hint.get('ehs', 0):.0%} | SPR: {ev_hint.get('spr', 0):.1f}"
        self.ev_label.config(text=ev_text)
```

---

## 性能预算

### 总时限: 20秒

| 模块 | 最坏情况延迟 | 备注 |
|------|-------------|------|
| 数据捕获 (OCR) | 1秒 | 扩展模式<0.1秒 |
| 状态解析 | 0.1秒 | 轻量 |
| 快速建议器 | 0.1秒 | 足够实时 |
| 范围建议器 | 3秒 | 可选升级 |
| CFR建议器 | 15秒 | 可选高级 |
| 规则解释 | <0.01秒 | 几乎零延迟 |
| LLM解释 | 3秒 | 可选 |
| UI渲染 | 0.1秒 | 轻量 |

**策略**：
- 默认模式：OCR(1s) + 快速建议(0.1s) + 规则解释(0s) = **1.2秒** ✅
- 平衡模式：扩展(0.1s) + 范围建议(3s) + 模板解释(0.01s) = **3.1秒** ✅
- 高级模式：扩展(0.1s) + CFR(15s) + LLM解释(3s) = **18秒** ✅

---

## 技术栈

### 核心依赖
```txt
# 游戏逻辑 (已有)
treys==0.1.8

# 数据捕获
pyautogui>=0.9.54        # 屏幕截图
pytesseract>=0.3.10      # OCR
opencv-python>=4.8.0     # 图像处理
Pillow>=10.0.0           # 图像处理

# WebSocket (扩展桥接)
websockets>=11.0

# UI
tkinter                  # Python内置

# LLM (可选)
anthropic>=0.25.0        # Claude API

# 工具
numpy>=1.24.0
```

### 可选依赖
```txt
# Web界面 (Phase 3)
fastapi>=0.100.0
uvicorn>=0.23.0
react (前端)

# 高级策略 (Phase 2.5)
torch>=2.0.0             # 如果使用神经网络
```

---

## 开发路线图 (职业级AI)

### Phase 1: 底层环境 ✅ 已完成
- [x] HeadsUpPokerEnv游戏引擎
- [x] 动作系统和规则校验
- [x] 基础评估器 (HS/EHS)
- [x] 测试框架

### Phase 2: 职业级AI决策系统 (11-15周)

#### Phase 2.1: 范围引擎 (3-4周)
- [ ] Week 1-2: 范围数据库和基础框架
  - 完整5人桌范围表定义
  - Range类和操作方法
  - 范围vs范围equity计算
  - 公共牌结构分析

- [ ] Week 3-4: 范围推断算法
  - 翻前范围估计
  - 翻后动态范围更新
  - 多人底池范围处理

**交付**: 完整的范围引擎，支持复杂的范围操作和equity计算

#### Phase 2.2: 对手建模引擎 (2-3周)
- [ ] Week 1: 统计追踪系统
  - OpponentStats数据结构
  - 实时统计更新 (VPIP/PFR/AF/3bet/...)
  - SQLite持久化

- [ ] Week 2: 对手分类器
  - 9种玩家类型分类
  - 置信度评分
  - 动态重分类

- [ ] Week 3: Exploitative策略库
  - 针对各类型的exploit策略
  - 策略混合权重计算

**交付**: 完整的对手建模系统，能识别对手类型并提供针对性策略

#### Phase 2.3: 动态策略引擎 (4-5周)
- [ ] Week 1-2: GTO基线策略
  - 翻前GTO近似
  - 翻后基于equity的策略
  - 多人底池调整

- [ ] Week 3: Exploitative策略整合
  - GTO + Exploit混合
  - 动态aggression调整
  - 历史互动记忆

- [ ] Week 4-5: 集成和优化
  - 三层引擎端到端集成
  - 性能优化 (<100ms)
  - 决策质量验证

**交付**: 完整的职业级AI决策系统

#### Phase 2.4: 测试与验证 (2-3周)
- [ ] 单元测试和集成测试
- [ ] 对局模拟 (10,000手 vs 不同对手)
- [ ] 典型场景测试 (50+场景)
- [ ] 职业玩家评审

**交付**: 测试报告和质量验证

**Phase 2 成功标准**:
- vs Random: +60 BB/100
- vs Fish: +45 BB/100
- vs TAG: break-even到+5 BB/100
- 典型场景专家一致率 > 75%
- 决策延迟 < 100ms

---

### Phase 3: 数据捕获和UI (3-4周)
- [ ] OCR屏幕识别
- [ ] PokerStars适配
- [ ] 桌面悬浮窗UI
- [ ] 端到端集成测试

**交付**: 完整可用的实时建议器产品

---

### Phase 4: 产品化 (选做)
- [ ] 多网站支持
- [ ] Web界面
- [ ] 用户设置和个性化
- [ ] 历史记录与复盘

---

## 总结

### 核心设计优势

1. ✅ **职业级决策能力**
   - 范围思维代替单手牌思维
   - 对手建模和Exploitative策略
   - GTO基线防止被exploit
   - 多因素综合决策权重系统

2. ✅ **5人桌专门优化**
   - 多人底池特殊处理
   - 位置价值放大
   - 隐含赔率和死钱计算

3. ✅ **性能完全满足**
   - 决策延迟 < 100ms
   - 远低于20秒时限
   - 留有大量优化空间

4. ✅ **可测试可验证**
   - 明确的成功标准
   - 对局模拟验证
   - 职业玩家评审

5. ✅ **渐进式开发**
   - Phase 2.1-2.4 分阶段实施
   - 每阶段有明确交付物
   - 风险可控，持续验证

### 关键差异化

| 维度 | 简单AI | 我们的职业级AI |
|------|--------|---------------|
| 思维方式 | 单手牌强度 | 范围 vs 范围 |
| 对手意识 | 无 | 9种类型精准建模 |
| 策略类型 | 固定规则 | GTO + Exploitative混合 |
| 多人处理 | 简单 | 专门优化 |
| 可exploit性 | 高 | 低 (GTO保护) |

### 预期效果

**vs 不同对手的胜率**:
- Fish: +45 BB/100 (极易击败)
- Nit: +25 BB/100 (利用可预测性)
- Calling Station: +35 BB/100 (薄价值下注)
- LAG: +10 BB/100 (trap + call down)
- TAG: +5 BB/100 (接近GTO，小赢)
- Maniac: +35 BB/100 (bluff catch)

**整体期望**: 在混合桌型中达到 +15-25 BB/100 的职业水平胜率

### 下一步行动

**推荐**: 开始实施 **Phase 2.1: 范围引擎**

详细设计和实施计划请参考: [docs/pro_level_ai_design.md](pro_level_ai_design.md)
