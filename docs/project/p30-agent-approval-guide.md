# P30 Agent 审批请求与决定状态

状态：**remote-accepted**。本门只记录可审计的审批状态，不注册或执行 `execute`、`write`、`hardware` 工具，也不把“已批准”解释成执行授权。

## 状态与边界

```text
paused checkpoint
      |
      +-> pending request -> approved
                         \-> denied
                         \-> expired
```

`readonly-agent-approval-request-0.1` 将一个暂停 checkpoint、registry binding、精确动作参数、权限级别、已有 observation、理由和最长 24 小时的有效期绑定为 `request_id`。动作的 `call_id` 由工具名、权限和完整参数计算，审批后替换对象或参数会使复验失败。

`readonly-agent-approval-decision-0.1` 将 `approved`、`denied` 或 `expired` 绑定到原 request、checkpoint 和 action call ID。批准/拒绝必须发生在到期前并记录本地 operator actor；过期只能在截止时间到达后由 Workbench expiry actor 记录。模型不能作为批准者，已注册的 read tool 也不能伪装成待审批动作。

请求和决定始终包含：

```json
"execution_authorized": false
```

因此本门没有副作用入口。批准记录既不认证操作者身份，也不赋予执行能力；未来执行协议必须另行验证身份、原子消费一次批准、持有事务/idempotency key，并产生执行 receipt。

## CLI

先准备只包含对象参数的 JSON 文件，例如：

```json
{
  "object": "ComSignal/WindowPosition",
  "value": 42
}
```

由暂停 checkpoint 和已存在的 observation 创建不可覆盖请求：

```bash
python -m automotive_workbench.cli request-agent-approval \
  output/agent/checkpoint.json \
  output/agent/write-arguments.json \
  --tool-name configuration.write \
  --permission write \
  --reason "需要操作者核对精确对象和值" \
  --evidence-id OBSERVATION_ID \
  --expires-in-seconds 900 \
  --output output/agent/approval-request.json

python -m automotive_workbench.cli verify-agent-approval-request \
  output/agent/checkpoint.json \
  output/agent/approval-request.json
```

记录批准或拒绝：

```bash
python -m automotive_workbench.cli decide-agent-approval \
  output/agent/checkpoint.json \
  output/agent/approval-request.json \
  --decision approved \
  --actor local-operator \
  --reason "已核对对象和值，仅记录批准" \
  --output output/agent/approval-decision.json

python -m automotive_workbench.cli verify-agent-approval-decision \
  output/agent/checkpoint.json \
  output/agent/approval-request.json \
  output/agent/approval-decision.json
```

超过截止时间后可用 `expire-agent-approval` 物化 `expired` 决定；截止时间之前调用会失败。到期不是后台定时器自动改写文件，只有显式记录并复验 expiry artifact 后才形成终态证据。

## 为什么当前不用 LangGraph 作为状态真相

当前状态内核是 Workbench 自己的版本化 JSON、哈希绑定和离线 verifier，不是 LangGraph。原因不是排斥框架，而是以下事实必须独立于编排器、模型 provider 和在线服务保持可复验：

- checkpoint 和 observation 是否来自同一事件链；
- 请求、精确动作参数和决定是否被替换；
- 当前状态是否只是一份记录，是否真的具备执行授权；
- 历史 artifact 在模型、Ollama 和知识服务停止后能否复验。

LangGraph 后续可以承载 graph scheduling、持久 checkpointer、interrupt/UI 恢复等编排职责，但只能调用这一状态协议，不能替代权限判断、证据验证器或未来的一次性消费账本。仓库当前没有 LangGraph 运行依赖。

## 验收

- 全量 462 tests 通过，其中 2 项因环境条件跳过；新增 5 项审批测试覆盖批准、拒绝、过期、篡改、模型自批、证据越界、有效期和不可覆盖输出。
- 66 schemas / 77 schema-bound / 25 syntax-only examples 通过；Ruff、scoped mypy、compileall、CI topology 和 diff check 通过。
- 源码合成 HTTP 场景完成 checkpoint → request → approved decision，并在服务停止后离线复验；`execution_authorized=false`。
- 隔离 wheel、无依赖安装、排除 checkout 后重复通过相同链路；wheel SHA-256 `11d4118ecc703d20bb70cbbba746083163eae79afa62e9e6a0e0d3b9c503624d`。

实现提交 `a713f7106db29278d13d1c68e554fbdc45a1d217` 的 [run `38499330921`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38499330921) completed/success。七个实际 job 全部 success：runtime-currency `115642281123`；core-contracts Ubuntu `115642281370`、Windows `115642281371`；runtime-evidence Windows `115644643716`、Ubuntu `115644643888`；controlled-rejections Windows `115644643801`、Ubuntu `115644643838`。本门 remote-accepted；随后纯文档状态提交不替代该实现 run。

## 尚未实现

- operator actor 目前是本地声明，不是登录、签名或组织身份认证；
- 同一 request 可在不同输出路径形成相互冲突的决定分支，当前没有中心化唯一账本；因为所有决定都不可执行，这不会开放副作用，但未来执行前必须解决；
- 没有批准的原子 claim/consume、租约、撤销、事务 outbox、执行 receipt 或幂等副作用；
- 没有 write/execute/hardware tool，不能据批准 artifact 写配置、运行总线或操作 ECU；
- v1 模型质量仍为 3/5 failed，一般复杂解释与真实资料适用性仍未验收。

下一门不是直接加写工具，而是定义一次性授权消费与副作用事务状态，先在 virtual、可回滚执行上验证并发、崩溃恢复和幂等，再决定是否注册受限 execute tool。
