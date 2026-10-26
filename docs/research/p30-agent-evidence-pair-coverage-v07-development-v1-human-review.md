# P30 0.7 development v1 独立审阅工作表

状态：`pending_human_review`。本表只为单个公开合成 `static-rejection` 案例准备审阅顺序，不记录人工结论；它不能替代另行冻结的 held-out 或资料适用性 cohort。

## 第一阶段：先看来源，记录独立预期

1. 打开项目报告 `output/p30-pair-presentation-v05-development-v1/scenarios/relocated/projects/static-rejection/bundle/project-report.json`，SHA-256 `46c6602b10cc67c13a45696c604df6367b56297efd2bd74054d5a74dcce5aaad`；按报告内相对路径查看 `ecuc-stage.json`。先不要打开模型结果、确定性呈现、冻结参考或 Codex 审阅。
2. 独立记录 COMMUNICATION、SIGNAL_SIZE、RUNTIME、RX_RUNTIME 的 status/reason、项目整体 status、四项验收原文，以及这些字段直接支持或没有支持的关系。

| 审阅者先填 | 独立记录 |
|---|---|
| 审阅日期、标识与是否已看过模型答案 |  |
| 四项原值与项目状态 |  |
| 可直接支持的关系及报告位置 |  |
| 需要拒绝推断的关系或根因 |  |

## 第二阶段：再看归档，记录适用性

先离线复验来源、呈现和覆盖产物。来源模型文本位于 `output/p30-pair-coverage-v07-development-v1/static-rejection-result-v06.json` 的 `summary`；确定性用户事实表位于同目录 `static-rejection-presentation-v06.json`，字面覆盖位于 `static-rejection-coverage-v07.json`。三个产物的原始 SHA-256 分别为 `9e66bb83621ac8f76391ee23b6b80957c1d7c341c50ce5275488c8c6e7a1edfe`、`fd42bd208ed122aff383d26ab5525ab0112af4ddee77756b8892249857e59742`、`aed533402aabe9e38542ca9f079aae2a2e0b1dbb373b1af1cb70a2e94890eebe`。

| 审阅者再填 | 人工判断与具体依据 |
|---|---|
| 来源/呈现/覆盖离线复验 |  |
| 模型是否逐项覆盖问题 |  |
| 模型因果关系是否由报告支持 |  |
| 静态、virtual CAN、物理 ECU 边界是否准确 |  |
| 未执行事项与建议边界 |  |
| 资料适用性 | 本题未检索外部资料，应记 `not_assessable` |
| 可用性：direct / needs_edits / not_usable |  |
| 修改所需内容与时间 |  |
| 分歧、补充与审阅者已见信息 |  |

记录第一阶段后才查看[预冻结参考](p30-agent-evidence-pair-coverage-v07-development-v1.json)与[Codex 非盲审阅](p30-agent-evidence-pair-coverage-v07-development-v1-review.json)。如果审阅者已看到这些材料，应如实标记为非盲；协议复验通过和 0.7 字面计数都不预填人工语义判定。
