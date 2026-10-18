# P30 Agent 独立人工审阅包

状态：local-accepted（2026-10-18）；尚待本实现自己的远端 CI。此门只建立可复验的审阅协议，不代表任何模型回答已获人工认可。

## 解决的问题

`readonly-agent-evaluation-0.1` 能冻结题目、结构化 gold、模型身份和预算，也能离线重评分工具选择、参数、引用及成本；它有意不判断自然语言语义。人工审阅包从已经通过离线复验的评测目录派生，并把以下内容交给审阅者：

- 原始问题；
- 未经语义认证的模型回答或无回答状态；
- 回答实际引用的完整、哈希绑定只读 observation；
- 固定的逐题审阅字段。

包中不包含 case ID、类别、冻结 gold、自动逐题分数或开发者结论。`review_item_id` 由 manifest 和原 case 身份哈希派生，仅用于稳定关联。审阅者仍应先写独立预期，再阅读答案；如果审阅者已经看过 gold 或答案，须在 notes 中记录，不能把结果称作盲审。

## 产物和边界

`prepare-agent-human-review` 生成：

- `review-pack.json`：问题、答案、引用 observation，以及来源 manifest/result/trace 身份；
- `review-template.json`：初始为 `pending`，不预填任何判断；
- `review-pack.md`：便于阅读的同源视图。

`finalize-agent-human-review` 只接受与原始 pending template ID 和 pack ID 同时匹配的完整模板，生成 `agent-human-review-assessment-0.1`。assessment 记录审阅者标识、带时区时间、逐题判断和 usability 汇总；验证器只证明字段完整、身份关系、摘要重算和内容哈希成立，不证明人工判断正确，也不认证审阅者身份。

本协议不调用模型、不调用知识服务、不写配置、不访问 SocketCAN 或硬件，也不生成 approval、claim 或 execution artifact。

## 操作

先从冻结评测产生待审包：

```bash
workbench prepare-agent-human-review \
  path/to/manifest.json path/to/evaluation \
  --implementation-root . --output output/human-review

workbench verify-agent-human-review \
  path/to/manifest.json path/to/evaluation output/human-review \
  --implementation-root .
```

复制 `review-template.json` 到审阅者工作文件，保留 `template_id`，填写 reviewer、reviewed_at 和所有逐题字段，并把 status 改为 `completed`。然后固化并离线复验：

```bash
workbench finalize-agent-human-review \
  output/human-review/review-pack.json completed-review.json \
  --output output/human-review-assessment.json

workbench verify-agent-human-review-assessment \
  output/human-review/review-pack.json \
  output/human-review-assessment.json
```

`independent_expected_answer` 必须非空。coverage、causal support、boundary fidelity 和 recommendation boundary 使用 `pass` / `fail` / `not_assessable`；资料适用性另有 `applicable` / `not_applicable` / `uncertain` / `not_assessable`；可用性使用 `direct` / `needs_edits` / `not_usable` / `not_assessable`。

## 验证证据与下一门

本地 506 tests 全部通过（2 项环境跳过）；84 个 schema、77 个 schema-bound example 和 25 个 syntax-only example 通过。源码合成全链及停服复验通过。隔离、无依赖、排除 checkout 导入的 wheel 流程也通过，wheel SHA-256 为 `1e96a37ce92aa7c8e519d027eff52652a4a29d24a0970b70378e17870b7f0c90`。其中完成态 assessment 的 reviewer 明确为 `synthetic-contract-fixture`，全部语义项为 `not_assessable`；它只测试协议，不是假造的人工质量结论。

远端 CI 通过后，下一门才冻结新的复杂解释与可信资料 cohort。题目、结构化期望、项目报告、资料策略、资料内容摘要、模型 digest 和预算必须在目标模型调用前固定；真实运行只执行一次。随后把模型结果转换为本协议的审阅包，交给独立审阅者。未取得完成的人工 assessment 前，P30 的一般复杂解释、资料适用性和人工可用性继续保持 pending。
