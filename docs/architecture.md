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

`run-can-lab` 使用 python-can virtual backend 建立两个进程内节点，通过 cantools 完成 DBC 编解码。它是 Windows/CI 可运行的最低成本运行时底座，后续 SocketCAN/OpenBSW adapter 应复用报告契约，而不是重写实验语义。

`run-can-supervision` 在同一底座上增加周期观测与通信监督状态。平台只把 `RECEIVING → TIMEOUT → RECOVERED` 视为可移植业务证据；Windows 主机测得的周期和抖动只用于回归观察，不宣称硬实时性能。

日志内核采用双层证据：can-utils `.log` 保存不可被 DBC 覆盖的原始 frame/timestamp；manifest、decode Finding 和 Markdown report 保存派生工程证据。每次分析记录日志与 DBC 的 SHA-256。`BusConfig` 只选择 python-can backend，业务实验不直接依赖 virtual 或 SocketCAN。

核心层不依赖具体GUI、向量数据库或LLM。Adapter只能把外部产物转换成核心对象，不能降低外部Finding严重度，也不能伪造缺失配置。

`run-review` 实现第一个 retrieval-only 审查内核：只注册 request 显式列出的本地 JSON artifact，对标量叶子生成 JSON Pointer EvidenceUnit，使用无第三方依赖的词法匹配支持调用方 checks。Citation 同时绑定 source SHA-256、pointer 和 content SHA-256；源文件改变后引用必须失效。`answered/partial/refused` 是证据覆盖结果，不会覆盖或降级确定性 Finding。

R5d 将审查内核扩展到本地 Markdown `line-range`，并通过 `review-request-0.2` assertion 显式声明 `claim_key`、locator 和 `equals/all-equal`。词法重叠不触发冲突；只有可比较观测值不一致时才产生 `REVIEW-EVIDENCE-CONFLICT` 并引用双方。`run-review-eval` 对固定 corpus、gold locator、拒答码、Finding 保真和三次重复运行做精确评分，不使用 LLM judge。
