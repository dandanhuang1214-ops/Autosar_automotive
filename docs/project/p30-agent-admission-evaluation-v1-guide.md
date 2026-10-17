# P30 deterministic admission 后只读模型评测 v1

状态：**pre-inference frozen / local-accepted**。冻结 manifest ID 为 `945dfd72145acdc97a100d1d7f54bc5afafac7326d331278a2d59f56b4b0100a`；远端 CI 和真实 qwen3.5:2b 结果均待完成，不能标记 remote-accepted 或模型质量通过。

## 评测问题

旧 candidate-selection v1 的真实结果为 1/5 failed，说明小模型不适合决定精确 action、能力适用性或证据条件。typed action intent 与 deterministic admission 已把这些安全相关决定移回控制面。本 cohort 因而不再评估模型选候选或拒绝动作，只评估它能否完成 admission 之前唯一保留的模型职责：

```text
target model: choose one registered read-only tool and obtain frozen facts
       |
       v
verified paused checkpoint
       |
       +-- control plane issues sealed candidates
       +-- control plane issues frozen typed intent
       +-- deterministic admission checks capability/action/evidence
       v
approval_required / declined / refused (never authorized or executed)
```

模型每题最多实际使用一次 model call 和一次 read tool call。预算中的 `max_model_calls=2` 仅允许 runner 在第一次工具调用后进入显式 pause 检查；评分门仍要求 `cumulative_model_calls <= 1`。checkpoint 之后不再调用模型。

## 冻结内容

[v1 spec](../research/p30-agent-admission-evaluation-v1-spec.json) 和 [v1 manifest](../research/p30-agent-admission-evaluation-v1-manifest.json) 在任何目标模型推理前固定：

- qwen3.5:2b digest `324d162b…20df`；
- 项目 report SHA-256、完整 bundle digest 与 evaluator implementation digest；
- 五道新题的结构化事实、精确 action/call ID、typed intent 和期望 admission；
- 两个 exact admission、一个 no-action、一个硬件越界和一个证据条件不成立；
- 每题 read tool、gold fact ID、调用/token 上限及预期确定性状态。

五题使用 application、task bindings、mode rules、policy 和 impact 事实，不复用旧 candidate-selection v1 的 communication 问题。gold 由代理在推理前从已复验报告冻结，不冒充独立人工 gold，也不评估自然语言说明质量。

manifest ID 为 `945dfd72145acdc97a100d1d7f54bc5afafac7326d331278a2d59f56b4b0100a`，implementation SHA-256 为 `ce6ad0587441343af69462f34442ffe2e2ce37a2063e0d8c7ab3236bcf39230c`。

## 使用

冻结命令只重放证据并计算摘要，不接触模型服务：

```bash
python -m automotive_workbench.cli freeze-agent-admission-eval \
  docs/research/p30-agent-admission-evaluation-v1-spec.json \
  --root . --implementation-root . \
  --output docs/research/p30-agent-admission-evaluation-v1-manifest.json \
  --model qwen3.5:2b \
  --model-digest 324d162be6ca5629ae4517c8710434d0bd2d665bc94dbad46e9af8fbf8a2f0df
```

只有冻结实现提交自己的远端七 job 全部成功后，才允许对固定 manifest ID 运行一次目标模型：

```bash
python -m automotive_workbench.cli run-agent-admission-eval \
  docs/research/p30-agent-admission-evaluation-v1-manifest.json \
  --root . --implementation-root . \
  --manifest-id 945dfd72145acdc97a100d1d7f54bc5afafac7326d331278a2d59f56b4b0100a \
  --output output/p30-agent-admission-v1
```

停止模型服务后可重验全部 artifact、逐题评分、汇总和 result ID：

```bash
python -m automotive_workbench.cli verify-agent-admission-eval \
  docs/research/p30-agent-admission-evaluation-v1-manifest.json \
  output/p30-agent-admission-v1
```

离线 verifier 会重验 checkpoint/trace、全部 candidate、intent 和 admission，并重新计算八个分轴：checkpoint preparation、candidate issuance、intent issuance、admission status、candidate resolution、evidence binding、non-execution boundary 和 cost。它不使用 LLM judge。

## 本地验收与边界

- 504 tests 全部通过，2 项按环境跳过；15 项 admission/candidate/contract 定向回归通过。
- 81 schemas / 77 schema-bound examples / 25 syntax-only examples 通过；CI topology 为 4 jobs、3 matrices、4 controlled failures。
- Ruff、相关 mypy、compileall、pip check 和 whitespace gate 通过。
- fixture 完整运行只产生一次模型调用，确定性 admission 与停服式离线重评分通过；准备失败不会伪造 intent/admission，也不会错误归因成准入失败。
- 隔离 wheel 安装后从 `/tmp` 导入新 evaluator、加载冻结 manifest、重算相同 implementation digest 并发现新 CLI；没有从 checkout 导入。wheel SHA-256 为 `6763a6a12136a3279423ce892894907fa773cc14a8234c9afae892c7de379d03`。

本评测不会创建 approval decision、claim 或 execution artifact。`approval_required` 仍只是待 operator 审批状态；配置写入、SocketCAN、物理硬件、远端执行和认证 operator 继续关闭。内容哈希不是数字签名或身份认证。

## 下一步

先提交并推送这一冻结点，取得与实现提交 head 完全一致的远端七 job 结论。只有远端成功后，才运行一次固定 qwen3.5:2b cohort，并在停服后离线重评分。结果无论通过或失败，都不得修改或重跑本 cohort 回调；后续改进必须使用新的开发题和新的冻结版本。
