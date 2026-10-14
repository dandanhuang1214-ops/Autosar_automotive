# P30 Agent 本地一次性 claim 与非执行事务

状态：**local-accepted，remote pending**。本门在审批记录之后增加本地单账本内的排他 claim、崩溃后恢复入口和幂等终态 receipt，但不注册或调用任何副作用工具。

## 状态

```text
approved decision
       |
       +-> claimed -> simulated
                  \-> aborted
```

`readonly-agent-approval-claim-0.1` 的 transaction ID 只由 checkpoint、request 和精确 action call ID 决定。因此同一 request 的两个批准分支会竞争同一 transaction 目录，先成功写入的 decision 被绑定，另一分支复验失败。

`readonly-agent-transaction-receipt-0.1` 只允许：

- `simulated`：完成了非执行演练；
- `aborted`：在任何副作用前终止。

claim 和 receipt 都固定 `execution_authorized=false`、`side_effect_performed=false`。当前协议没有 `executed` 状态，不能被用来声称配置已写入、总线已运行或 ECU 已操作。

## 并发与恢复语义

账本路径固定为 `<ledger>/<transaction_id>/claim.json` 和 `receipt.json`。发布 artifact 时先在同目录写完并 `fsync` 临时文件，再用 no-overwrite 硬链接原子发布最终名字：

- 多个相同 claim 并发时只会有一个最终文件，其他调用复验并返回同一 artifact；
- 不同 decision 分支竞争同一 request 时，已有 claim 与另一 decision 不匹配并 fail closed；
- claim 已存在、receipt 尚未产生时，可在进程重启后继续记录终态；
- 相同 outcome/reason 的完成重试返回原 receipt，不改写完成时间；
- 不同 outcome 或 reason 的终态竞争被拒绝。

如果进程在临时文件写入期间崩溃，最终 claim/receipt 尚不可见；临时文件可能保留，但 verifier 只读取固定最终名字。当前未实现临时文件垃圾回收，以避免自动删除不明证据。

## CLI

```bash
python -m automotive_workbench.cli claim-agent-approval \
  output/agent/checkpoint.json \
  output/agent/approval-request.json \
  output/agent/approval-decision.json \
  --ledger output/agent/transaction-ledger

python -m automotive_workbench.cli complete-agent-transaction \
  output/agent/checkpoint.json \
  output/agent/approval-request.json \
  output/agent/approval-decision.json \
  --ledger output/agent/transaction-ledger \
  --outcome simulated \
  --reason "No side-effect tool was invoked"

python -m automotive_workbench.cli verify-agent-transaction \
  output/agent/checkpoint.json \
  output/agent/approval-request.json \
  output/agent/approval-decision.json \
  --ledger output/agent/transaction-ledger
```

批准必须在 request 到期前被 claim；到期后即使已有 approved decision 也拒绝新 claim。已在到期前成功 claim 的事务可以在之后记录 `simulated/aborted` receipt。

## 本地验收

- 全量 467 tests 完成，2 项环境条件跳过；新增 5 项事务测试，含 16 次并发 claim、决定分支冲突、过期/拒绝、崩溃恢复、终态冲突、schema 与篡改拒绝。
- 68 schemas / 77 schema-bound / 25 syntax-only examples，Ruff、scoped mypy、compileall、CI topology、pip check 和 diff check 通过。
- 源码合成 HTTP 场景完成 approval → claim → simulated receipt，并在模型/知识服务停止后离线复验。
- 隔离 wheel、无依赖安装、排除 checkout 后重复通过；wheel SHA-256 `783c2a36c3c548c44340a9dde85ce371a74bf533dfe3baca7fe79c9d426411c8`。

本地成功不等于远端验收；实现提交和七 job run 尚待记录。

## 限制与下一门

- 唯一性只在一个受信任的本地 ledger 路径内成立；复制 ledger 或选择另一个 root 会形成新的协调域，不是分布式 exactly-once。
- 本轮不认证 operator，不签名 artifact，也不抵御拥有同等文件系统写权限的恶意进程。
- 原子发布依赖同一文件系统支持硬链接；跨平台能力须由本实现的 Windows/Ubuntu CI 结论确认。
- 未实现执行前后事务、补偿、真实 side-effect idempotency key 或执行结果的独立观测。

远端验收后，下一门才考虑一个默认禁用、virtual-only、可回滚的 execute tool。它必须消费 claim、以 transaction ID 作为工具幂等键，并把“命令返回”和“独立验证到的实际效果”分开记录；硬件与配置写入仍不开放。
