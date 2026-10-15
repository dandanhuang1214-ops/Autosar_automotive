# P30 Agent 受限 virtual CAN execute tool

状态：**local-accepted，远端 CI 待执行**。本门首次允许一个有副作用的 Agent 控制面工具，但模型仍不能直接调用它，配置写入、SocketCAN 和物理硬件仍全部关闭。

## 唯一开放动作

`virtual_can.send_once` 只接受两个精确参数：

- `frame_id`：0–0x7FF 的 classic CAN ID；
- `payload_hex`：0–8 字节十六进制数据。

调用方不能提供 interface 或 channel。执行器强制使用 `python-can virtual`，并由 transaction ID 推导唯一的 `workbench-agent-<24 hex>` 进程内通道。该工具没有进入模型可见的只读 `ToolRegistry`；当前必须由控制面从暂停 checkpoint 创建精确 approval request，取得 decision 和一次性 claim 后，再通过本地显式开关执行。

审批 artifact 仍不是身份认证或授权令牌。`--enable-virtual-execution` 是独立的本地运行门，receipt 固定记录 `authenticated_authorization=false`、`hardware_accessed=false` 和 `configuration_written=false`。

## 状态与崩溃语义

```text
approved -> claimed -> attempt(started) -> succeeded | failed
                                \
                                 -> crash/unknown: indeterminate, no auto replay
```

执行前先用与 claim 相同的原子 no-overwrite 方式发布 `execution-attempt.json`。transaction ID 同时作为工具幂等键：

- 已有通过复验的 terminal receipt 时，重试只返回原 artifact，不再次发送；
- attempt 已存在但 receipt 不存在时，不能判断进程是在发送前还是发送后崩溃，自动重试被拒绝为 `indeterminate`；
- 另一个 ledger 仍是另一个协调域，因此不是分布式 exactly-once。

`receipt.json` 使用 `agent-virtual-execution-receipt-0.1`，把三类结果分开：

1. `command_result`：底层 `send()` 返回还是抛错；
2. `effect_verification`：独立 receiver 是否观察到精确 ID 和 payload；
3. `compensation`：关闭发送/接收句柄后，新 observer 是否仍看到缓冲帧。

若 `send()` 已进入但抛错，`side_effect_status=indeterminate`，不会武断写成未发生。只有命令返回、独立效果通过、补偿通过且副作用状态为 `performed` 时 terminal status 才是 `succeeded`。

## 补偿边界

已经发出的 CAN 帧无法字面撤销，所以 receipt 明确记录 `literal_undo=false`。本门能证明的是：动作局限于唯一的进程内 virtual channel，拥有的 bus 句柄已关闭，且新 observer 未看到缓冲残留。这是瞬态动作的补偿/清理，不是持久配置的 rollback 证明。

后续若开放任何持久状态工具，必须另外记录 baseline、实际变更、独立 after observation、反向操作和恢复后的独立 observation；不能复用本门的“无持久状态”结论。

## CLI

approval 和 claim 仍使用既有命令。执行默认关闭；只有显式增加开关才运行：

```bash
python -m automotive_workbench.cli execute-agent-virtual-can \
  output/agent/checkpoint.json \
  output/agent/virtual-request.json \
  output/agent/virtual-decision.json \
  --ledger output/agent/transaction-ledger \
  --enable-virtual-execution

python -m automotive_workbench.cli verify-agent-virtual-execution \
  output/agent/checkpoint.json \
  output/agent/virtual-request.json \
  output/agent/virtual-decision.json \
  --ledger output/agent/transaction-ledger
```

## 本地验收

- 473 项全量回归通过，2 项环境条件跳过；新增 6 项覆盖默认关闭、真实 virtual 收发/独立观测/补偿、terminal 幂等重试、崩溃后禁止自动重放、观测异常不污染命令结果、精确参数和篡改拒绝、停服离线验签。
- 70 schemas / 77 schema-bound / 25 syntax-only examples；Ruff、scoped mypy、compileall、CI topology、pip check 和 diff check 通过。
- source 合成协议场景完成 approval → claim → 默认拒绝 → 显式执行 → 停服离线复验。
- 隔离 wheel、无依赖安装和排除 checkout 场景通过，SHA-256 `a32b472665ce0851ccd12173ff7940b83ea9dffd1c9166e88ccd12ac60dbe40f`。该环境故意不安装可选 `python-can`，只验收新 CLI 的默认关闭；不声称完成实际 virtual 发送。

远端验收必须记录实现提交、实际 run 和七个 job 结论后才能改为 remote-accepted。

## 下一门

下一门把这个受限动作接到 Agent 的“提议而不执行”暂停边界：模型可见 typed execute capability 后只能产生待审批 action，运行时不得自动调用；用户决定、claim、attempt 和 executor 继续由控制面承担。必须以新的 v2 frozen cohort 验收工具选择、参数、拒绝、成本和越权负例，不能回调已见 v1（3/5 failed）。配置写入与硬件仍不开放。
