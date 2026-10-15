# P30 Agent 模型提案与控制面执行边界

状态：**remote-accepted**。P30 整阶段仍为 implementing，模型质量仍沿用 v1 的 3/5 failed。

## 结论

暂停后的只读 Agent checkpoint 现在可以交给独立的 `ActionProposalRunner`。模型能看见一个 typed execute capability，并可选择精确参数，但模型侧没有任何可执行 handler：结果只能是待审批 proposal、主动 decline、refused 或 blocked。

```text
verified paused checkpoint
  -> ActionProposalRunner + proposal-only ActionCatalog
  -> immutable proposal (execution_authorized=false, tool_invoked=false)
  -> control-plane exact-action approval request
  -> operator decision -> one-shot claim -> explicit local enable
  -> restricted virtual executor
```

状态真相继续来自 Workbench 的版本化 artifact、内容哈希和离线 verifier。当前没有用 LangGraph 承载权限、审批或副作用状态；以后即使增加 LangGraph，也只能作为 scheduling/checkpointer/interrupt 适配层。

## 为什么不是把 execute tool 注册给 Agent

`ActionCatalog` 只保存名称、描述、JSON Schema、权限和参数校验器，故意没有 `invoke` 方法或 handler。Ollama 原生 function call 在这里仅是结构化“选择”，provider 不执行函数，Workbench 也不会在提案阶段分派动作。

目前 catalog 只有 `virtual_can.send_once`：

- 参数仍严格限制为 classic CAN `frame_id` 与最多 8 字节 `payload_hex`；
- interface/channel 不进入模型参数；
- capability manifest 和 binding SHA-256 写入 proposal；
- proposal 绑定 checkpoint、模型 identity、service version、请求、响应、usage 与全部成功 observation ID；
- `requested_action.call_id` 与后续 approval request 必须逐字段相同，控制面不能静默替换模型参数。

模型可以调用 `agent_decline`，但只能使用固定原因码。未知工具、额外参数、模型 identity 漂移、预算不足或响应不完整都 fail closed。proposal 本身不是批准，更不是认证授权。

## Token 与执行边界

提案只进行一次模型调用，并继承 checkpoint 尚未消费的模型调用、token、单次输出、context window 和墙钟预算。请求只发送目标、已成功工具的紧凑 projection、一个延迟加载的 execute capability 和剩余预算，不发送完整工程或所有工具 schema。

`agent-action-proposal-0.1` 固定记录本次及累计 token。若调用后越过 token/时间上限，只能生成 `refused`，不能产生 requested action。任何 `approval_required`/`declined` 结果都必须有一次模型调用和响应证据。

## CLI

```bash
python -m automotive_workbench.cli propose-agent-action \
  output/agent/checkpoint.json \
  --output output/agent/proposal.json \
  --ollama-url http://127.0.0.1:11434

python -m automotive_workbench.cli verify-agent-action-proposal \
  output/agent/checkpoint.json \
  output/agent/proposal.json

python -m automotive_workbench.cli request-agent-approval-from-proposal \
  output/agent/checkpoint.json \
  output/agent/proposal.json \
  --reason "Review the exact model-proposed virtual frame." \
  --output output/agent/virtual-request.json
```

后续 decision、claim 和 virtual execution 继续使用既有控制面 CLI。执行仍默认关闭，必须显式增加 `--enable-virtual-execution`。

CLI 自动生成的账本时间增加“不得早于前置 artifact”的逻辑下限，以抵抗宿主机跨进程时钟回拨；底层构造器和离线 verifier 对显式倒序时间仍保持拒绝。

## 本地验收

- 478 项全量回归通过，2 项环境条件跳过；新增 5 项 proposal 单测覆盖原生/结构化选择、decline、非法参数、模型漂移、精确审批转换与篡改拒绝。
- 71 schemas / 77 schema-bound / 25 syntax-only examples；Ruff、scoped mypy、compileall、CI topology、pip check 与 diff check 通过。
- source 合成链完成 checkpoint → 原生 function proposal → exact approval → decision → claim → 默认拒绝 → 显式 virtual 执行 → 停服离线复验；命令、效果和补偿均 passed。
- 隔离无依赖 wheel、排除 checkout 场景通过，SHA-256 `af74bc144b48c34df0e5be023d6f07c97c35d7c88d8ac1dbc78a5dd562a1dac3`。proposal 与精确审批转换在安装后通过；该环境没有可选 `python-can`，因此只验证执行默认关闭，不宣称完成实际发送。

以上是合成 HTTP 协议与控制面安全边界证据，不是真实模型质量证据。

实现 `541a7df588a6aa029f2293aa92321a25caa471df` 的 [run `38674052274`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/38674052274) completed/success。七个实际 job 均 success：runtime-currency `116223488395`；core-contracts Ubuntu `116223488653`、Windows `116223488692`；controlled-rejections Ubuntu `116225842956`、Windows `116225842989`；runtime-evidence Windows `116225842973`、Ubuntu `116225843079`。本门 remote-accepted；本条之后的纯文档状态提交不替代该实现 run。

## 下一门

在不使用 v1 已见题回调实现的前提下，先冻结新的 v2 cohort，再运行绑定的真实模型。v2 分开计量 execute proposal 的工具选择、精确参数、主动拒绝、越权负例、引用和 token 成本；冻结前不得推理，冻结后不得用结果修改同一版本。配置写入、SocketCAN、硬件和认证 operator 继续关闭。
