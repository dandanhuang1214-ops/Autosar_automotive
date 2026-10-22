# P30 控制面完整证据对摘要 0.3

状态：local-accepted，等待本实现提交与远端 CI。日期：2026-10-22。

## 为什么新增版本

0.2 已把结构化输出故障收敛为一次纯文本摘要，但开发题暴露了另一个独立问题：`project_query_facts` 的 top-6 投影只给出五个指定检查中的三组 `status/reason`，模型仍概括全部五项。0.2 的协议与真实结果保持不变；0.3 不修改旧 plan、旧 result、旧 manifest 或旧 verifier。

0.3 将问题拆成两个明确门：控制面先证明所需证据完整，随后模型才能压缩文字。外层结果分别报告 `protocol_status`、`evidence_completeness` 和 `semantic_assessment`，因此“传输成功”“证据齐全”和“文字可用”不再共用一个状态。

## 用户路径

先显式列出问题要求的检查 ID。ID 对应项目报告 `requirements[].id`，计划会固定顺序和每项必须具备的 `status/reason` 字段。

```bash
python -m automotive_workbench.cli create-agent-evidence-pair-plan \
  --goal "给出 COMMUNICATION、APPLICATION、TASK-BINDINGS、MODE-RULES、IMPACT 各自状态和原因。" \
  --check-id COMMUNICATION \
  --check-id APPLICATION \
  --check-id TASK-BINDINGS \
  --check-id MODE-RULES \
  --check-id IMPACT \
  --output output/agent-evidence-pair-plan.json

python -m automotive_workbench.cli run-agent-evidence-pair-summary \
  path/to/project-report.json output/agent-evidence-pair-plan.json \
  --model qwen3.5:2b \
  --ollama-url http://127.0.0.1:11434 \
  --output output/agent-evidence-pair-summary-result.json

python -m automotive_workbench.cli verify-agent-evidence-pair-summary-result \
  path/to/project-report.json \
  output/agent-evidence-pair-plan.json \
  output/agent-evidence-pair-summary-result.json
```

计划也可单独离线复验：

```bash
python -m automotive_workbench.cli verify-agent-evidence-pair-plan \
  output/agent-evidence-pair-plan.json
```

## 完整性语义

控制面复验项目报告并读取完整事实集，不进行 top-k 截断。每个 `check_id` 必须唯一映射到一个项目 requirement；requirement 的 `/checks/<check>/status` 指针必须可解析；对应 stage artifact 中必须恰有一个 status fact 和一个 reason fact。

- 全部成对解析：`evidence_completeness=complete`，才允许查询模型服务身份并进行一次纯文本调用。
- 检查不存在、重复、指针不可解析或任一事实缺失：`protocol_status=refused`、`evidence_completeness=incomplete`、`model_calls=0`。
- 报告无法复验或读取失败：`protocol_status=blocked`、`evidence_completeness=unavailable`、`model_calls=0`。
- 模型文字始终为 `semantic_assessment=unassessed`；协议通过不表示文字通过人工质量判断。

成功路径只向模型提供已排序的完整 pair 列表。每项包含用户可见 check ID、内部 check key，以及 status/reason 各自的 fact ID、JSON Pointer 和原值。模型不能选择检查、字段、工具或引用。结果保存精确 request/response、选择结果、兼容 trace 和哈希链；服务停止后可离线复验。

## 本地验收

- 新增三项定向测试：五个完整证据对进入一次纯文本调用；不存在的检查在任何模型服务访问前拒绝；计划和结果篡改 fail closed。
- 离线 verifier 要求原始报告、计划和结果，并重放完整选择；替换成另一份有效报告也会拒绝，防止仅凭自洽哈希接受错误事实来源。
- 完整合成 HTTP 场景通过：5/5 pair complete、1 次 read、1 次 model、离线复验 passed；缺项场景为 incomplete/refused、0 次 model，停服离线复验 passed。
- 0.2 合成场景和既有 P30 审批、事务、受限 virtual CAN、评测与人工审阅协议在同次脚本中继续通过。

当前结论仅为 local-accepted。合成 fixture 不是实际模型推理，`semantic_assessment` 仍为 unassessed；必须等待实现提交自己的远端七 job 后，才能称该版本 remote-accepted。

## 边界与下一步

0.3 只覆盖项目 acceptance report 中显式 requirement 的直接 `status/reason` 对，不声称已解决任意自然语言到任意 JSON 字段的自动规划。它不写配置、不调用商业工具、不访问 SocketCAN 或硬件，也不生成 approval、claim 或 execution。

远端验收后，用全新 development-only 问题对固定 Qwen 运行一次，确认模型面对完整 pair 时不再补写缺失证据；不得修改或重跑 0.2 的既有结果。开发通过后才冻结新的 held-out cohort，并比较 Qwen 与可审计的更强文本模型。一般复杂解释和独立人工可用性仍为 pending。
