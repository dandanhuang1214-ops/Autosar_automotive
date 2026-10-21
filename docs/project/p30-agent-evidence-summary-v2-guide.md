# P30 控制面证据纯文本摘要 0.2

状态：**remote-accepted**（2026-10-21）。本门解决模型输出协议可靠性，不声称自然语言质量已经通过，也不修改任何已见 cohort。

## 为什么单独版本化

Codex-reference / Qwen 对比 v1 已证明固定 evidence plan 能稳定取得预期项目事实与已审核资料，但 qwen3.5:2b 的四次唯一调用仍因两个错误对象形状、一个非法 JSON 和一个无有效响应得到 0/4。旧 `agent-evidence-plan-result-0.1`、模型适配器和 frozen comparison manifest 都已进入实现摘要；直接修改它们会破坏历史复验。

因此 0.2 复用不可变 `agent-evidence-plan-0.1`，新增独立 `agent-evidence-summary-result-0.2`。旧结构化路径、result、manifest、唯一真实结果与离线 verifier 均保持原样。

## 接口与控制边界

`run-agent-evidence-summary` 仍由控制面按 plan 顺序执行 `project_query_facts`、`knowledge_retrieve_reviewed` 或二者；模型不能增删、重排或参数化 read tool。所有成功 observation ID 由控制面附加，模型不选择引用。

模型阶段只有一次 Ollama `/api/chat` 调用：

- 请求不含 `format` 或 `tools`，显式固定 `stream=false`、`think=false`、temperature/seed、context、输出 token 与 keep-alive。
- 模型只返回 1–1000 字符纯文本；空文本、截断、错误模型、非法 usage、控制字符、身份漂移或预算超限均 fail closed。
- 最终 artifact 分别保存真实 request/response、兼容的只读 trace、规范化 summary、完整控制面 evidence IDs 和 `semantic_status=unassessed`。
- 离线 verifier 从原 plan、实际 tool projection、预算与模型身份重新推导完整请求，并核对原始响应、usage、规范化 summary、事件链、trace/result ID 和全部引用。只把所有字段一起重新哈希也不能改变计划输入后通过复验。

纯文本通过只表示“模型协议产生了可归档文本”，不表示文字正确、资料适用或可供工程决策。配置写入、SocketCAN、物理硬件、审批身份和外部工具执行权限均未增加。

## CLI

先使用既有命令建立不可变计划，再执行 0.2：

```bash
python -m automotive_workbench.cli create-agent-evidence-plan \
  --goal "解释项目阻断原因并说明已审核资料的适用边界" \
  --scope project_and_reviewed_knowledge \
  --output output/agent-evidence-plan.json

python -m automotive_workbench.cli run-agent-evidence-summary \
  path/to/project-report.json output/agent-evidence-plan.json \
  --model qwen3.5:2b \
  --knowledge-url http://127.0.0.1:8000 \
  --knowledge-policy examples/knowledge/p30-vector-official-policy.json \
  --output output/agent-evidence-summary-result.json

python -m automotive_workbench.cli verify-agent-evidence-summary-result \
  output/agent-evidence-plan.json \
  output/agent-evidence-summary-result.json
```

输出路径必须不存在。真实模型验证前还必须固定模型完整 digest、报告/bundle、资料 policy/corpus 和预算；本地合成通过不能替代该门。

## 本地验收

- 完整回归 521 tests 通过，2 项按环境跳过。沙箱内首次全量唯一错误为禁止绑定 `127.0.0.1`；允许回环 socket 后同一完整套件通过。
- 3 项 0.2 专项覆盖纯文本成功、实际 payload、完整控制面引用、截断响应、模型身份漂移、预算、输出保护、字段篡改和“请求/trace/result 一起重算”的负例。
- 源码合成 HTTP 全链通过：2 个固定 read tool、1 次纯文本模型调用、2 个控制面引用；服务停止后离线复验通过。
- 90 schemas / 79 schema-bound examples / 25 syntax-only examples、Ruff、scoped mypy、CI topology、compileall、pip 与 diff check 通过。
- 隔离无依赖 wheel 从 checkout 外运行两工程与完整模型协议，0.2 result `5b4def5f…6e99c6` 停服复验通过；wheel SHA-256 `50e69ce8e86eb3886f6abd1f4fcb7841d7411c67a465c82fb248dacb11f77f6e`。安装环境再次复验旧 comparison manifest `67d55634…2cab`，证明历史实现摘要未漂移。

## 远端验收

实现提交 `fc56a68a6ef57f08b1af5c943599e08d8c348387` 对应 [GitHub Actions run `39543371725`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/39543371725)，head 一致且 completed/success。七个实际 job 全部 success：

- core-contracts Windows `119035959876`、Ubuntu `119035960195`
- runtime-currency `119035960097`
- runtime-evidence Ubuntu `119038400800`、Windows `119038400871`
- controlled-rejections Windows `119038400809`、Ubuntu `119038400814`

因此 0.2 实现 remote-accepted；这仍只验收协议、可移植性与回归，不提升模型自然语言质量结论。

## Qwen 单次开发观察

远端门完成后，使用一个全新、未冻结的 development-only 问题。报告、plan `e5dbda4d…5b13c`、qwen3.5:2b digest `324d162b…20df` 和预算在推理前固定。非法 transport timeout 与不兼容的旧 0.1 project report 都在模型调用前被拒绝并保留工件，二者 `model_calls=0`；随后使用新生成的 `project-acceptance-0.6` integration 报告，真实模型只调用一次。

result `46f65aaf377b035eb569d6f22996a97a6c45041d09c7a7236db17d1aba799570` 为协议 `passed`：1 个固定 read、1 个模型调用、617 prompt / 82 output / 699 total tokens、1 个控制面 citation。result SHA-256 `a6c95577136dc28af2ec10d837589bd60291d63d55203a15d593cc1f4498b907`；Ollama 停止后离线 verifier 返回同一 result ID。

但语义不通过。top-6 事实只包含 APPLICATION、COMMUNICATION、IMPACT 的 status/reason，遗漏问题明确要求的 TASK-BINDINGS 与 MODE-RULES；Qwen 仍声称五项均 passed，并把 `linked_in_scope` / `explicit_dependencies_assessed` 合并为未逐项绑定的 alternatives。Codex 透明事后诊断为 `not_usable`，review SHA-256 `caad468e6f8acce9b0ab8e9be85e8bc0144f2a3d35f97709cae4bebf96461691`。该诊断不是预登记 gold 或独立人工审阅。

## 下一门

0.2 已消除本题的 JSON 结构失败，但暴露了控制面证据选择不完整时模型补写缺失事实的问题。下一门先用新协议版本实现成对字段完整选择与缺项显式拒绝，保留 0.2、旧 result 和 frozen manifest 不变；新的开发题通过后，再固定 reference/criteria 与全新 held-out cohort，比较 Qwen 和可审计的更强文本模型并生成独立人工审阅包。旧复杂解释 v1 和 Codex-reference/Qwen v1 均不修改、不重跑。
