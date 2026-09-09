# Architecture v0

```text
CLI / future API
       ↓
Application Services
  inspect | trace | validate | run/report
       ↓
Workbench Core
  Artifact | Finding | TraceLink | TestResult
       ↓
Adapters
  Generate-Arxml | future CAN/OpenBSW/UDS/vendor bridges
```

`run-suite` 当前执行一条基线和五条故障注入实验，将所有 adapter 的 Finding 汇总为可归档 JSON/Markdown。故障样例只在临时目录中生成，不修改基线资产。

`run-can-lab` 使用 python-can virtual backend 建立两个进程内节点，通过 cantools 完成 DBC 编解码。0.2 契约分别执行 BODY_ECU 发送 `WindowStatus` 和接收 `WindowCommand`，在运行证据中保留 message identity、direction、frame ID、payload 和 decoded signals。它是 Windows/CI 可运行的最低成本运行时底座，后续 SocketCAN/OpenBSW adapter 应复用报告契约，而不是重写实验语义。

`run-communication-chain` 编排 P4/P6 静态与运行时闭环：先运行 DBC/BSW intent 校验，再以 `BusConfig` 在 virtual 或 SocketCAN 上执行双向 CAN 通信，最后以 `DBC message + signal` 为稳定 identity，对比静态/运行方向和 frame ID。通信 runtime 对 `0x100/0x200` 使用精确过滤，并保存 backend probe 与入口锁证据。报告固定 DBC、intent 与实际 runtime JSON 的 SHA-256；任一静态失败、runtime 失败、identity 缺失、frame ID 或方向漂移均使证据失败，backend 不可用则独立返回 `blocked`。

P5a 的 `index-evidence` 在报告生成之后建立只读 bundle inventory。artifact identity 使用 bundle 内 POSIX 相对路径；JSON 文件保留自身声明的 artifact type/schema，其他文件按媒体类型分类。若 JSON 报告携带 `source_artifacts`，索引器会把来源解析为 bundle 内 artifact 或 portable base 下的 external dependency，并逐字节核对声明哈希。manifest 写在 bundle 外，避免自引用。

P5b 的 `verify-evidence` 将 manifest 结构有效性与 bundle 完整性分层：非法/不闭合 manifest 直接拒绝；合法 manifest 对应的缺失、额外、大小/哈希变化、符号链接及外部依赖变化进入 `evidence-bundle-verification-0.1`。P5c 在 CI 复制正常 bundle 后只向固定 runtime JSON 追加一个换行，要求真实 CLI 返回非零，并用独立检查器确认 `EVIDENCE-SIZE-MISMATCH` 后再上传拒绝证据。

`run-can-supervision` 在同一底座上增加周期观测与通信监督状态。平台只把 `RECEIVING → TIMEOUT → RECOVERED` 视为可移植业务证据；Windows 主机测得的周期和抖动只用于回归观察，不宣称硬实时性能。

日志内核采用双层证据：can-utils `.log` 保存不可被 DBC 覆盖的原始 frame/timestamp；manifest、decode Finding 和 Markdown report 保存派生工程证据。每次分析记录日志与 DBC 的 SHA-256。`BusConfig` 只选择 python-can backend，业务实验不直接依赖 virtual 或 SocketCAN。

核心层不依赖具体GUI、向量数据库或LLM。Adapter只能把外部产物转换成核心对象，不能降低外部Finding严重度，也不能伪造缺失配置。

`run-review` 实现第一个 retrieval-only 审查内核：只注册 request 显式列出的本地 JSON artifact，对标量叶子生成 JSON Pointer EvidenceUnit，使用无第三方依赖的词法匹配支持调用方 checks。Citation 同时绑定 source SHA-256、pointer 和 content SHA-256；源文件改变后引用必须失效。`answered/partial/refused` 是证据覆盖结果，不会覆盖或降级确定性 Finding。

R5d 将审查内核扩展到本地 Markdown `line-range`，并通过 `review-request-0.2` assertion 显式声明 `claim_key`、locator 和 `equals/all-equal`。词法重叠不触发冲突；只有可比较观测值不一致时才产生 `REVIEW-EVIDENCE-CONFLICT` 并引用双方。`run-review-eval` 对固定 corpus、gold locator、拒答码、Finding 保真和三次重复运行做精确评分，不使用 LLM judge。

R5e 不改变审查判定逻辑，只扩展评测平面。evaluation case 显式记录 `domain`，结果输出总 check 数、各域 check 数和各域准确率。当前域为 `core/dbc/can/uds/dtc`；`dbc` 引用 DBC-derived canonical contract，其他汽车域直接引用公开 BSW/UDS/DTC intent。所有源文件由 request `expected_sha256` 锁定。

R5h 将跨运行比较升级到 `review-request-0.3`：每个 assertion observation 必须显式携带 `variant`、`software_version`、`calibration_version` 和 `backend`。只有 profile 完全一致时才解析并比较稳定字段；任一字段不同都会产生 `REVIEW-APPLICABILITY-MISMATCH`、将 check 标为 `blocked` 且不生成数值 citation，避免把版本或后端差异误报为 drift。当前 profile 仍由调用方声明，尚未绑定到 runner 自身生成的受证据保护元数据。

R5i 将该边界升级到 `review-request-0.4`。CAN、UDS 和 DTC runner 在报告内生成 `applicability_profile`：variant 来自输入模型、software version 来自 runner 契约、calibration version 是有效输入文件名与内容 SHA-256 的规范化组合哈希、backend 来自实际执行配置。Observation 使用 `applicability_locator` 指向报告内 profile；报告 source SHA-256、profile 与被比较值因此属于同一证据封套。绝对路径不进入 calibration identity，同内容迁移目录不产生假 drift。

R5j 新增 `review-request-0.5` cohort assertion。每个 observation 显式标记唯一 `baseline` 或一个 `candidate`；系统逐 candidate 先比较 artifact-bound applicability，再与 baseline 的稳定字段比较，输出 `stable`、`drifted` 或 `not-comparable`。一个不可比较 candidate 不会抹去其他 candidate 的有效引用；drift catalog validator 会验证候选覆盖、citation ID 和 relation，防止 catalog 与证据不一致。首个 evaluator 0.7 竖切固定为三次 CAN 运行。

R5k 保持三运行和显式 baseline 边界，将 cohort 扩展到 UDS decoded VIN 与 DTC confirmed state。evaluator 0.8 在保留逐 case 精确 catalog gate 的同时输出全局和按 domain 的 `stable/drifted/not-comparable` 计数；这些计数仅是确定性样例覆盖摘要，不构成时间趋势、统计显著性或版本兼容性结论。
