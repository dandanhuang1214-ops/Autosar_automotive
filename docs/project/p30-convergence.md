# P30 收敛记录

状态：`convergence_review`（2026-11-03）。本页区分已通过远端工程门的能力、真实模型内容结果和仍需人工完成的质量门；它不改变冻结试验，也不把 P30 标为完成。

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

## 关闭条件与下一步

当前 P30 保持 `implementing`，先由**独立审阅者**完成两份已备材料：0.7 工作表须先记录报告支持的预期，再看模型文本；四题 Agent 包须填写 `review-template.json` 并用现有 `finalize-agent-human-review` / `verify-agent-human-review-assessment` 固化。审阅者若已见 Codex 结论或模型答案，须如实标明非盲；不能由代理替填人工意见。

审阅后选择一条可审核的收敛路径：

1. **受限范围收敛**：明确接受“已复验工程事实 + 确定性呈现 + 标记未审的 AI 草稿/项目候选”为 P30 交付；一般复杂解释、资料适用性与模型自主选择留在后续阶段。记录范围决定和人工审阅实际结果后，才更新 P30 阶段状态。
2. **完整质量门**：若要求一般复杂解释可用，应先在新版本和新 development 题解决当前遗漏/无依据推断，再预冻结新的 held-out 与人工判据，取得其实现提交远端 CI 后只运行新题；完成独立人工审阅后才能宣称通过。旧开发题和旧 held-out 不调参重跑。

两条路径都不以协议通过、CI 全绿或 Codex 自审代替模型语义验收。MCP 服务化是后续架构课题，不作为 P30 当前关闭门；P25 人工演示与外部反馈继续单列。
