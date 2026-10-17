# P30 typed action intent 与确定性准入门

状态：**remote-accepted**。实现 `36eac3b592bd060d9a27f75c0e66c57ea2987b14` 已通过 [run `38997832114`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38997832114) 的七个实际 job；P30 整阶段仍为 implementing。

## 结论

candidate-selection v1 真实基线为 1/5 failed：小模型会选错精确帧/载荷候选，也会在“不需动作”或条件不成立时选择候选。因此本轮不继续调提示，而是把安全相关的适用性判断收回 Workbench 控制面。

```text
verified paused checkpoint
  + control-plane typed action intent
  + sealed action candidates
  -> deterministic capability/action/evidence admission
     -> exactly one match: approval_required
     -> no action / unsupported / evidence mismatch: declined
     -> zero or multiple exact matches: refused
  -> existing pending approval request
```

`agent-action-intent-0.1` 由控制面发出，显式表示三种意图：

- `exact_action`：绑定唯一受限 virtual action、能力范围和至少一条 observation 条件；
- `no_action`：只能以 `action_not_required` 确定性拒绝；
- `unsupported_action`：只记录超出受限能力的 SocketCAN/硬件意图，不封装 execute action。

`agent-action-admission-0.1` 重新验证 checkpoint、intent 和全部 candidate，然后确定性比较：

- capability 必须是 `process_local_virtual / virtual / null channel`；
- action 必须与 intent 中已校验的 tool、permission、arguments 和 call ID 完全相同；
- evidence condition 只能从 checkpoint 中成功的 tool observation 取值，支持 `fact_id` 或 JSON Pointer selector；
- candidate 必须包含条件引用的 observation，且唯一精确匹配才能产生 `approval_required`。

准入过程不调用模型，artifact 固定 `model_invoked=false`、`execution_authorized=false` 和 `tool_invoked=false`。它只能生成现有 pending approval request；operator decision、一次性 claim、显式 virtual enable 和 executor 仍是独立门。

## CLI

先编写控制面 intent spec：

```json
{
  "disposition": "exact_action",
  "requested_capability": {
    "scope": "process_local_virtual",
    "interface": "virtual",
    "channel": null
  },
  "requested_action": {
    "tool_name": "virtual_can.send_once",
    "arguments": {"frame_id": 1110, "payload_hex": "BEEF"}
  },
  "evidence_conditions": [
    {
      "observation_id": "OBSERVATION_ID",
      "selector": {"kind": "fact_id", "value": "FACT_ID"},
      "expected_value": "structural_gap"
    }
  ],
  "deterministic_decline_reason": null
}
```

签发 intent、准入候选并创建待审批请求：

```bash
python -m automotive_workbench.cli issue-agent-action-intent \
  output/agent/checkpoint.json output/agent/intent-spec.json \
  --output output/agent/intent.json

python -m automotive_workbench.cli admit-agent-action-candidates \
  output/agent/checkpoint.json output/agent/intent.json \
  --candidate output/agent/candidate.json \
  --output output/agent/admission.json

python -m automotive_workbench.cli request-agent-approval-from-admission \
  output/agent/checkpoint.json output/agent/intent.json \
  output/agent/admission.json \
  --candidate output/agent/candidate.json \
  --reason "Review the deterministically admitted virtual CAN frame." \
  --output output/agent/request.json
```

服务停止后可分别运行 `verify-agent-action-intent`、`verify-agent-action-admission` 和 `verify-agent-approval-from-admission`。后两个命令需提供同一候选集，会重算准入结果并确认审批 action/evidence 没有变化。

## 验收范围

- 两份 Draft 2020-12 schema 约束 typed intent 和 admission artifact；旧 proposal/candidate/审批契约保持兼容。
- 定向回归覆盖精确候选+干扰候选、证据值不匹配、无动作、SocketCAN 越界、artifact 篡改、schema 和文件重放。
- 源码合成场景覆盖 intent -> admission -> approval，且在 fixture 服务停止后复验三者关系。
- 全量 500 tests 通过（2 项环境跳过）；79 schemas / 77 schema-bound / 25 syntax-only、Ruff、scoped mypy、CI topology、compileall、pip check 和 diff check 通过。
- 隔离无依赖 wheel 从仓库外工作目录完成两工程、12 类模型协议、typed admission 和归档重放，并确认没有从 checkout 导入；wheel SHA-256 `9412c64dbcc7df74013dae137e41c154e367fe39ae1506d9bb40312d2fb00b68`。
- 本轮不运行真实模型；它是对 1/5 failed 基线的控制面修复，不改写旧 cohort 结论。

远端实现验收：`36eac3b592bd060d9a27f75c0e66c57ea2987b14` / [run `38997832114`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38997832114) completed/success，head 完全一致。七个实际 job 均 success：runtime-currency `117294186870`；core-contracts Ubuntu `117294186640`、Windows `117294186787`；controlled-rejections Ubuntu `117295898094`、Windows `117295898136`；runtime-evidence Ubuntu `117295898158`、Windows `117295898161`。后续纯文档状态提交不替代该实现 run。

## 边界与下一门

内容哈希提供篡改检测，不是数字签名或身份认证。`workbench-control-plane` 仍是本地声明；配置写入、SocketCAN、物理 ECU 和远端执行没有开放。

下一项是冻结全新 cohort，只评估模型在确定性准入之后需要的非安全决策，不再让模型重复决定精确 action 或证据条件。一般复杂解释和真实资料适用性仍需独立人工验收，P30 保持 implementing。
