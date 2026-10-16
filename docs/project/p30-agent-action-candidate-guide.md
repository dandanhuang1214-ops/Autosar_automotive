# P30 控制面动作候选与 ID-only 模型选择

状态：**remote-accepted**。实现 `09522dd1c8733fc4ed410915348118f99f43e561` 已通过 [run `38873638394`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38873638394) 的七个实际 job；P30 整阶段仍为 implementing。

## 结论

模型不再生成 execute tool 的参数。Workbench 控制面先用现有受限 catalog 校验精确动作，绑定暂停 checkpoint、成功 observation、capability binding 和内容哈希，签发 `agent-action-candidate-0.1`。模型随后只能选择一个已签发的 `candidate_id`，或使用固定原因拒绝。

```text
verified paused checkpoint + exact caller arguments
  -> control-plane candidate validation and sealing
  -> model selects candidate_id OR agent_decline(reason)
  -> immutable selection (no invocation, no authorization)
  -> exact candidate-to-approval verification
  -> existing decision -> claim -> explicit virtual enable path
```

这修复了 proposal 0.2 开发题暴露的边界：qwen3.5:2b 曾把明确的 `0x456` 重写成 `frame_id=1`。候选路径中，模型请求仍能看到候选动作以判断是否适用，但 function schema 只有 `candidate_id`，没有 `frame_id`、`payload_hex` 或 channel；模型响应不能替换参数。

## 证据契约

候选 artifact 绑定：

- checkpoint ID、registry binding、目标和全部引用 observation；
- `virtual_can.send_once` 的精确 `tool_name`、`permission`、已校验参数和 `call_id`；
- proposal-only catalog 的 capability binding；
- `issued_by=workbench-control-plane`、`execution_authorized=false`、`tool_invoked=false`。

selection artifact 绑定候选全集（按 ID 稳定排序）、模型/服务身份、请求、可重算的归一化响应、选择结果、token/时间预算和内容哈希。原生 function calling 与结构化输出回退都只允许 candidate ID 或固定 decline reason。未知 ID、额外模型参数、候选/响应篡改、身份漂移、预算耗尽和服务失败均 fail closed；已发出但未收到响应的调用也可按真实 `model_calls=1` 离线复验。

`verify-agent-approval-from-candidate` 会在服务停止后同时验证 checkpoint、候选集合、selection 和标准 approval request，并确认 approval 的 action/evidence 与选中候选完全相同。审批仍是现有协议，不因模型选择而获得执行授权。

哈希是内容绑定，不是签名。`workbench-control-plane` 和 operator ID 仍是本地声明，不构成认证身份；当前只开放进程内 virtual CAN，配置写入、SocketCAN、硬件和远端执行仍关闭。

## CLI

先准备仅包含精确动作参数的 JSON，例如：

```json
{
  "frame_id": 1110,
  "payload_hex": "BEEF"
}
```

然后签发、选择并转换为标准待审批请求：

```bash
python -m automotive_workbench.cli issue-agent-action-candidate \
  output/agent/checkpoint.json \
  output/agent/candidate-arguments.json \
  --tool-name virtual_can.send_once \
  --evidence-id OBSERVATION_ID \
  --output output/agent/candidate.json

python -m automotive_workbench.cli select-agent-action-candidate \
  output/agent/checkpoint.json \
  --candidate output/agent/candidate.json \
  --output output/agent/selection.json \
  --ollama-url http://127.0.0.1:11434

python -m automotive_workbench.cli request-agent-approval-from-candidate \
  output/agent/checkpoint.json \
  output/agent/selection.json \
  --candidate output/agent/candidate.json \
  --reason "Review the exact control-plane-issued virtual CAN frame." \
  --output output/agent/request.json

python -m automotive_workbench.cli verify-agent-approval-from-candidate \
  output/agent/checkpoint.json \
  output/agent/selection.json \
  output/agent/request.json \
  --candidate output/agent/candidate.json
```

单独的 `verify-agent-action-candidate` 和 `verify-agent-candidate-selection` 可分别复验中间 artifact。多个 `--candidate` 可组成封存候选集；模型仍只能选择其中一个精确 ID。

## 本地验收

- 最终全量 492 tests 通过，2 项环境条件跳过；9 项候选动作单测覆盖 schema、原生/结构化选择、decline、未知 ID、额外参数、身份漂移、服务失败、预算、篡改、精确审批关系和文件重放。
- 75 schemas / 77 schema-bound / 25 syntax-only examples；Ruff、scoped mypy、CI topology、compileall、pip/diff check 通过。新模块已加入 Python 3.11 与 3.14 的 scoped mypy CI 门。
- 源码合成链完成 candidate → ID-only selection → exact approval → decision/claim → 默认关闭/显式 virtual execution，并在服务停止后复验 candidate、selection、approval 关系和执行证据；所有候选 artifact 都保持未授权、未调用。
- 隔离无依赖 wheel、排除 checkout 场景通过，SHA-256 `9c8e45866d4526ba291fd65997ca464c0ba6b0eb23a43b502e340de5bc6b1adf`。安装后候选签发、选择、审批关系和停服复验通过；没有可选 CAN 依赖时不声称实际发送。

以上是合成 HTTP 协议和确定性控制面证据，没有运行真实模型，不能改变 v2 proposal 的 0/5 failed 结论。

## 远端验收

实现提交 `09522dd1c8733fc4ed410915348118f99f43e561` 的 [run `38873638394`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38873638394) completed/success，head 完全一致。七个实际 job 均 success：runtime-currency `116883383780`；core-contracts Windows `116883384086`、Ubuntu `116883384190`；runtime-evidence Windows `116886383782`、Ubuntu `116886383901`；controlled-rejections Ubuntu `116886383809`、Windows `116886384023`。本门 remote-accepted；随后纯文档状态提交不替代该实现 run。

## 下一门

下一门是预推理冻结一个全新的 candidate-selection cohort，分别测量 checkpoint preparation、候选 ID 选择、固定原因拒绝、证据绑定和 token/时间成本；冻结实现自己的远端 CI 通过后，才运行固定 qwen3.5:2b。不得复用已见 v2 或本轮合成 fixture 冒充质量验收。

开放参数的 proposal 0.2 保持兼容和历史复验，但不再作为小模型 execute 意图的默认路径。P30 继续 implementing；一般复杂解释、真实资料适用性、认证 operator、配置写入、SocketCAN 与物理 ECU 均未验收。
