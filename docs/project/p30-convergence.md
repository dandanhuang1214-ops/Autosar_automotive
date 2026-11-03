# P30 收敛记录

状态：`restricted_scope_accepted`（2026-11-03）；原定的一般复杂解释质量门 **未通过，未纳入本次交付范围**。本页区分已通过远端工程门的能力、真实模型内容结果和人工可用性意见；不改变冻结试验或既有结果。

## 当前可交付范围

| 能力 | 当前结论 | 边界 |
|---|---|---|
| 项目报告复验、精确事实和引用 | 工程门 remote-accepted | 来源、状态、值与完整性由 Workbench 校验；模型不改写工程结论。 |
| 确定性证据对呈现与固定边界句 | 工程门 remote-accepted | 用户可见的逐项 `status/reason` 从已复验报告重建；原始模型文本单列 `unassessed`。 |
| 只读 Agent 证据准备与确定性动作准入 | 受限评测已通过 | 不覆盖自由文本解释；配置写入、SocketCAN、硬件与认证执行仍未开放。 |
| AI 需求到静态 ECUC 项目验收入口 | 工程门 remote-accepted | 只从已有验收项选一个 ID、生成项目验收声明并执行原项目引擎；选择相关性未经独立审阅，不生成 ARXML/ECUC。 |
| 一般复杂解释、因果建议与资料适用性 | **未验收** | 现有冻结模型评测失败，人工审阅未完成；不得作为工程判定或推广承诺。 |

## 本次离线核对

- `static-rejection` 封存报告 SHA-256 `46c6602b10cc67c13a45696c604df6367b56297efd2bd74054d5a74dcce5aaad`：`verify-ecuc-project` 为 `passed`，报告内项目状态为 `failed`。同一 [0.7 冻结题](../research/p30-agent-evidence-pair-coverage-v07-development-v1.json)的 0.6 模型结果、确定性呈现与 0.7 覆盖结果均离线复验 `passed`；模型协议 `passed`，四项证据对完整，呈现四项准确，但模型原文字面覆盖为 `incomplete`、0/4。此前 Codex 非盲[内容审阅](../research/p30-agent-evidence-pair-coverage-v07-development-v1-review.json)指出无依据的共同根因推断，结论 `failed_for_the_requested_task`；这不是独立人工结论。原始输出不修改、不重跑。
- [四题 Agent 评测](p30-agent-explanation-review-v1-guide.md)离线重评分 `status=passed`、`evaluation_status=failed`、0/4；对应[人工审阅包](../../output/p30-agent-explanation-human-review-v1/review-pack.md)离线验签 `passed`、4 项 `pending_human_review`。其中两题没有可审正文。已有 Codex 对照属于非盲诊断，不算独立人工验收。
- 本页只复验已有产物，没有启动模型、生成新回答或重评分既有人工意见。复验命令与原始材料见[0.7 独立审阅工作表](../research/p30-agent-evidence-pair-coverage-v07-development-v1-human-review.md)及[Agent 人工审阅指南](p30-agent-human-review-guide.md)。

## 用户审阅反馈

用户看过分开的五题问题与实际回答后，认为**有最终回答的 Q1、Q2、Q5 可以视作通过**。此[人工可用性记录](../research/p30-user-content-review-20261103.md)限定于 3/3 个有回答的样本；Q3、Q4 没有最终回答。用户意见是非盲、整体可用性判断，未提供正式 review template 所需的逐项来源和因果判断。它与冻结格式门 0/4、Agent 任务门 0/4 并列保存，均不互相覆盖。

## 受限收口决定与后续

本轮依照用户“先把 P30 收敛”的目标，采用**受限范围**结束 P30 的当前实现阶段。受限交付为：已复验工程事实、确定性证据对呈现、受控只读 Agent 基础和静态 ECUC 项目的 AI 验收候选入口。模型原文仅作可见草稿；无回答必须显示拒绝/阻断，由确定性事实继续承载工程结论。用户对 3/3 有回答样本的非盲认可作为样本可用性证据；2/5 无回答、0.7 格式门 0/4 与 Agent 任务门 0/4 均保留。

这不是原定“一般复杂解释、完整引用、资料适用性”的验收。0.7 工作表与四题 Agent `review-template.json` 仍为 pending，不能由代理按一句整体意见填成完整 assessment；历史失败和 held-out 不修改、不重跑。如以后要求广泛模型解释可用，须在新版本和新 development/held-out 题解决无回答、遗漏与无依据推断，并完成逐项人工审阅。MCP 服务化是后续架构课题；P25 人工演示与外部反馈继续单列。
