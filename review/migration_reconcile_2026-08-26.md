# 规则冷热迁移对账报告（2026-08-26）

- 运行模式：--dry-run --report（未动盘）
- 总规则：170 条（rule_heat 键数）

## ① 建议降级候选（0 条）
- 无（当前 demoted_at 均为 08-06，保护期 30 天未满，首跑预期零候选）

## ② 未满阈值候补（0 条，预计达标日期）

## ③ 冲突/疑似项（7 条，默认不动盘）
- Forbidden #11（P0，状态=cold，落点=cold）：P0 却 cold（设计文档规定 P0 永不降级）
- Forbidden #19（P2，状态=cold，落点=cold）：cold 但近 5 天有触发（疑似应 recovered）
- Forbidden #21（P0，状态=cold，落点=cold）：P0 却 cold（设计文档规定 P0 永不降级）
- Forbidden #23（P0，状态=cold，落点=cold）：P0 却 cold（设计文档规定 P0 永不降级）
- Rule26（P0，状态=cold，落点=none）：P0 却 cold（设计文档规定 P0 永不降级）
- Rule42（P0，状态=cold，落点=cold）：P0 却 cold（设计文档规定 P0 永不降级）
- Rule55（P0，状态=cold，落点=cold）：P0 却 cold（设计文档规定 P0 永不降级）

## ④ 安全闸拦截（5 条）
- Forbidden #1（—，状态=cold，落点=hot）：G3 基础 Forbidden F1-6
- Forbidden #2（—，状态=cold，落点=hot）：G3 基础 Forbidden F1-6
- Forbidden #3（—，状态=cold，落点=hot）：G3 基础 Forbidden F1-6
- Forbidden #5（—，状态=cold，落点=hot）：G3 基础 Forbidden F1-6
- Forbidden #6（—，状态=cold，落点=hot）：G3 基础 Forbidden F1-6

## 升温候选（本期不动作，v0.2）（0 条）

## 豁免（幽灵编号 / 无独立正文块）与一致项
- 幽灵编号豁免：5 条：Rule24, Rule25, Rule28, Rule29, Rule30
- 无独立正文块豁免：24 条：Rule1, Rule2, Rule3, Rule4, Rule5, Rule6, Rule7, Rule8, Rule9, Rule10, Rule11, Rule12, Rule13, Rule14, Rule15, Rule16, Rule17, Rule18, Rule19, Rule20, Rule21, Rule22, Rule23, Rule27
- 状态一致（无需动作）：129 条

- 运行状态已落盘：C:\Users\admin\.workbuddy\skills\history-today-writer\review\migration_state.json