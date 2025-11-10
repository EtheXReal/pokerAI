# POJ 项目路线图

> **项目名称**: POJ - 职业级德州扑克实时建议器
> **最终目标**: 在网页端5人桌实时提供职业级决策建议
> **当前阶段**: Phase 1 完成，准备开始 Phase 2

---

## 🎯 项目愿景

构建一个**实时德州扑克AI建议器**，能够：
1. 自动从网页游戏界面捕获数据
2. 在20秒时限内提供职业级决策建议
3. 达到/超越职业选手水平 (+15-25 BB/100)
4. 针对不同对手类型动态调整策略

---

## 📊 整体进度

```
Phase 1: 底层环境                ████████████████████  100%  ✅
Phase 2: 职业级AI决策             ░░░░░░░░░░░░░░░░░░░░    0%  ⏳
Phase 3: 数据捕获和UI             ░░░░░░░░░░░░░░░░░░░░    0%
Phase 4: 产品化                   ░░░░░░░░░░░░░░░░░░░░    0%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
总体进度:                        █████░░░░░░░░░░░░░░░   25%
```

---

## Phase 1: 底层环境 ✅ 已完成

**时间**: 已完成
**目标**: 搭建稳定的游戏环境和数据契约

### 交付成果

✅ **游戏引擎** ([env/engine.py](../env/engine.py))
- 完整的No-Limit Hold'em规则实现
- 支持2-5人桌
- 精确的行动顺序和下注规则
- 边池计算和摊牌逻辑

✅ **动作系统** ([env/actions.py](../env/actions.py))
- 6个标准化动作 (fold/call/r33/r66/r100/allin)
- 动作合法性校验
- 下注尺寸计算

✅ **牌力评估** ([env/evaluator.py](../env/evaluator.py))
- Hand Strength (HS) 计算
- Effective Hand Strength (EHS) 计算
- 性能优秀 (~20ms)

✅ **测试框架** ([scripts/](../scripts/))
- smoke_env.py: 随机自博弈测试
- check_eval.py: 评估器验证
- walk_showdown.py: 摊牌测试
- test_r_sizing.py: 下注尺寸测试

✅ **文档完善**
- [spec_overview.md](spec_overview.md): 项目规格
- [data_schemas.md](data_schemas.md): 数据契约
- [eval_protocol.md](eval_protocol.md): 验收清单

### 关键指标

- 代码量: ~2,673行 Python
- 测试覆盖: 主要路径覆盖
- 性能: 单次决策 < 100ms
- 稳定性: 可运行10,000手无错误

---

## Phase 2: 职业级AI决策系统 ⏳ 当前阶段

**时间**: 11-15周
**目标**: 构建达到职业选手水平的AI决策引擎

### 设计文档

📘 [职业级AI设计文档](pro_level_ai_design.md) - 完整技术设计
📘 [Phase 2开发概览](phase2_overview.md) - 详细实施计划
📘 [系统架构](architecture.md) - 更新后的架构

### 核心设计理念

**三层架构**：
```
第1层: 范围引擎        → 范围思维，不是单手牌思维
第2层: 对手建模引擎    → 识别9种玩家类型，针对性exploit
第3层: 动态策略引擎    → GTO基线 + Exploitative调整
```

**关键差异化**：
- ✅ 范围 vs 范围思维
- ✅ 9种对手类型精准建模
- ✅ GTO + Exploitative混合策略
- ✅ 5人桌多人底池专门优化
- ✅ 7个决策因素综合权重系统

### Phase 2.1: 范围引擎 (3-4周) ✅ 已完成

**目标**: 实现职业级范围思维

**Week 1-2: 范围数据库和基础框架**
- [x] 完整5人桌范围表定义
  - UTG/MP/CO/BTN/SB/BB 开池范围
  - 3-bet/4-bet 范围
  - 按紧度分级 (tight/normal/loose)
- [x] Range类和操作方法
  - 范围表示、过滤、组合
- [x] 范围vs范围equity计算
- [x] 公共牌结构分析器

**Week 3-4: 范围推断算法**
- [x] 翻前范围估计
  - 根据位置和玩家类型
- [ ] 翻后动态范围更新 (延后到 Phase 2.3)
  - 根据行动序列缩小范围
- [x] 多人底池范围处理

**交付**: ✅ 完整的范围引擎库

**测试结果**:
- ✅ Equity计算准确性验证通过
- ✅ 17个单元测试全部通过
- ✅ 范围表覆盖所有5人桌位置
- ✅ 性能 < 100ms (满足要求)

**实现文件**:
- `advisor/range_engine/preflop_ranges.py` - 翻前范围表
- `advisor/range_engine/range.py` - Range类
- `advisor/range_engine/equity.py` - Equity计算器
- `advisor/range_engine/board_texture.py` - 公共牌分析
- `tests/advisor/test_range_engine.py` - 单元测试

### Phase 2.2: 对手建模引擎 (2-3周)

**目标**: 识别对手类型并提供exploit策略

**Week 1: 统计追踪系统**
- [ ] OpponentStats数据结构
  - VPIP/PFR/AF/3bet/C-bet等20+指标
- [ ] 实时统计更新
- [ ] SQLite持久化存储

**Week 2: 对手分类器**
- [ ] 9种玩家类型分类算法
  - Nit/TAG/Calling Station/LAG/Fish/Maniac等
- [ ] 置信度评分系统
- [ ] 动态重分类

**Week 3: Exploitative策略库**
- [ ] 针对9种类型的exploit策略
  - Fish: 不bluff，薄价值
  - Nit: 高频偷池
  - LAG: trap + call down
  - ...
- [ ] 策略混合权重计算

**交付**: 完整的对手建模系统

**测试目标**:
- 50手后分类准确率 > 85%
- Exploit方向正确性

### Phase 2.3: 动态策略引擎 (4-5周)

**目标**: 整合三层，输出最终决策

**Week 1-2: GTO基线策略**
- [ ] 翻前GTO近似
  - 位置相关开池/3-bet频率
- [ ] 翻后基于equity的策略
  - MDF计算
  - 最优bluff频率
- [ ] 多人底池调整
  - equity打折
  - bluff频率降低

**Week 3: Exploitative策略整合**
- [ ] GTO + Exploit混合算法
- [ ] 动态aggression调整
- [ ] 历史互动记忆

**Week 4-5: 集成和优化**
- [ ] 端到端集成三层引擎
- [ ] 性能优化 (目标 <100ms)
- [ ] 决策质量验证

**交付**: 完整的职业级AI决策系统

**测试目标**:
- 决策延迟 < 100ms
- 内存稳定无泄漏

### Phase 2.4: 测试与验证 (2-3周)

**目标**: 全面验证AI质量

**测试维度**:
- [ ] 单元测试和集成测试
- [ ] 对局模拟 (10,000手)
  - vs Random: 目标 +60 BB/100
  - vs Fish: 目标 +45 BB/100
  - vs TAG: 目标 0~+5 BB/100
  - vs LAG: 目标 +10 BB/100
  - vs Maniac: 目标 +35 BB/100
- [ ] 典型场景测试 (50+场景)
  - 专家一致率 > 75%
- [ ] 职业玩家评审
  - 目标评分 > 7/10

**交付**: 完整测试报告

### Phase 2 成功标准

**必达 (P0)**:
- [ ] vs Random: +60 BB/100
- [ ] vs Fish: +45 BB/100
- [ ] 决策延迟 < 100ms
- [ ] 对手分类准确率 > 85%

**期望 (P1)**:
- [ ] vs TAG: 0~+5 BB/100
- [ ] 场景一致率 > 75%
- [ ] 职业玩家评分 > 7/10

**加分 (P2)**:
- [ ] vs所有类型都盈利
- [ ] 场景一致率 > 85%
- [ ] 职业玩家评分 > 8/10

---

## Phase 3: 数据捕获和UI (3-4周)

**前置条件**: Phase 2 完成

**目标**: 实现端到端实时建议器

### Phase 3.1: OCR数据捕获 (2周)

**OCR方案** (通用性强):
- [ ] PokerStars配置文件
  - 区域坐标定义
  - 52张牌模板图
- [ ] 屏幕截图和预处理
- [ ] 卡牌模板匹配 (OpenCV)
- [ ] 数字OCR (Tesseract)
- [ ] 位置和按钮识别
- [ ] 错误处理和容错

**测试目标**:
- 识别准确率 > 95%
- 延迟 < 1秒

### Phase 3.2: UI界面 (1-2周)

**桌面悬浮窗**:
- [ ] 实时显示建议
  - 主要动作 (大字体)
  - 概率分布 (柱状图)
  - 牌力评估 (EHS/SPR)
- [ ] 悬浮窗控制
  - 置顶显示
  - 位置可调
  - 半透明
- [ ] 设置面板
  - aggression等级
  - 显示详细度

**CLI测试工具**:
- [ ] 交互式测试
- [ ] 手动输入局面
- [ ] 查看决策推理

### Phase 3.3: 集成测试 (1周)

- [ ] 端到端流程测试
- [ ] 真实环境验证
- [ ] 性能和稳定性测试

**交付**: 完整可用的实时建议器

---

## Phase 4: 产品化 (选做)

**前置条件**: Phase 3 完成

### 可能的方向

**4.1 多网站支持**
- GGPoker适配
- 888Poker适配
- 其他主流网站

**4.2 高级功能**
- 历史记录和复盘
- 统计分析面板
- 对手notes系统
- 自定义策略调整

**4.3 Web界面**
- FastAPI后端
- React前端
- 实时WebSocket通信

**4.4 社区功能**
- 用户系统
- 策略分享
- 排行榜

---

## 📚 关键文档索引

### 设计文档
- [项目规格概览](spec_overview.md)
- [数据契约定义](data_schemas.md)
- [职业级AI设计](pro_level_ai_design.md) ⭐ 核心
- [系统架构](architecture.md)
- [Phase 2开发概览](phase2_overview.md) ⭐ 实施指南

### 技术文档
- [引擎文档](../env/engine.md)
- [动作集文档](../env/actions.md)
- [测试验收清单](eval_protocol.md)

### 代码文档
- [底层环境](../env/)
- [核心规则](../core/)
- [测试脚本](../scripts/)
- [工具函数](../utils/)

---

## 🎯 当前行动项

**立即开始**: Phase 2.1 - 范围引擎

**第一步**: 创建目录结构
```bash
mkdir -p advisor/range_engine
mkdir -p advisor/opponent_modeling
mkdir -p advisor/strategy_engine
mkdir -p tests/advisor
```

**第二步**: 定义5人桌翻前范围表
- 参考职业玩家chart
- 按位置分级
- 验证combo数量

**第三步**: 实现Range类
- 基本数据结构
- 操作方法
- 单元测试

**预计完成时间**:
- Week 1-2: 2-3周 (2025年1月中旬)
- 整个Phase 2.1: 3-4周 (2025年1月底)
- 整个Phase 2: 11-15周 (2025年4月中旬)

---

## 📈 长期愿景

### 6个月目标
- 完成Phase 2和Phase 3
- 产品可用，支持PokerStars
- 达到职业级胜率 (+15-25 BB/100)

### 12个月目标
- 完成Phase 4产品化
- 支持多个主流网站
- 建立用户社区
- 持续优化策略

### 终极目标
- 成为最强的扑克AI建议器
- 超越现有商业产品
- 开源核心引擎，造福社区

---

## 🤝 贡献和反馈

项目当前由核心团队开发。

如有问题或建议，请通过以下方式反馈：
- 技术问题: 查阅文档或提issue
- 策略建议: 欢迎职业玩家提供反馈
- 功能需求: 提交feature request

---

**让我们开始Phase 2.1，构建职业级的范围引擎！** 🚀
