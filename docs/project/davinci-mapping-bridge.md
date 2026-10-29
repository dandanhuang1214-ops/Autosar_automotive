# DaVinci 显式信号映射只读接入

`audit-signal-mappings` 消费 AUTOSAR 4 ARXML 中显式的 `SENDER-RECEIVER-TO-SIGNAL-MAPPING`。输入可以是 Developer 导出的 ECUProject ARXML，再加上定义数据元素的 PortInterface ARXML。每份输入记录路径、字节数和 SHA-256；每条映射输出端口、数据元素、SystemSignal 的完整引用、由端口类型确定的 Rx/Tx 和未解析引用。零映射及悬空引用返回 `attention-required`（退出码 2）。

```sh
workbench audit-signal-mappings --source exported-ecu-project.arxml \
  --source port-interfaces.arxml --output mapping-audit.json
```

这项检查证明输入文件内的三类对象引用可解析，并不证明 COM/PduR/CanIf 配置、DBC 导入、任务映射、CFG 生成或 CAN 总线运行。供应商 CFG 的原生校验结果应单独保存，与本报告并列审查。运行时只读，不调用商业工具或修改工程；工具导出应先在隔离副本上完成。公开回归使用合成 ARXML，不包含本地商业工程和 SIP。

CFG 原生 XML 报告现在可由 `inspect-cfg-validation` 读取，核对声明计数与实际条目，输出按 ID/来源聚合的严重度、各 generator 状态与输入 SHA-256。`verify-cfg-validation` 重新读取源文件并验证摘要；报告依赖本地源文件，不是可脱离商业输入迁移的证据胶囊。XML 不含工具版本时，版本须由实际执行记录单独提供。

```sh
workbench inspect-cfg-validation validation.xml --output cfg-summary.json
workbench verify-cfg-validation cfg-summary.json
```

统一能力评估入口消费四份已经产生的报告，并在组合前各自复验原始输入或快照。输出保留每层结论与报告 SHA-256；CAN 总线层固定 `unassessed`，直到另有实际运行证据接入。它不会因为 Developer 映射闭合或 ECUC 路径存在就推断 CFG 可生成。

```sh
workbench assess-davinci-workflow --mapping mapping-audit.json \
  --cfg cfg-summary.json --communication ecuc-communication.json \
  --review ecuc-review.json --output workflow-assessment.json
workbench verify-davinci-workflow workflow-assessment.json
```

| 能力层 | 目前可验证的对象 | 本地隔离工程结果 |
|---|---|---|
| Developer 显式映射 | 端口、数据元素、SystemSignal 完整引用 | 2/2 resolved |
| ECUC 通信 | 配置范围内的通信对象路径 | 73 条，resolved-in-scope |
| ECUC 工程审查 | 应用、任务及结构发现 | 102 项发现，attention-required |
| CFG 原生校验 | 严重度计数与 generation 状态 | 25 errors，generation ERROR |
| CAN 总线/ECU | 实际收发和运行效果 | unassessed |

跨工具追踪使用 Developer 已核对的 SystemSignal 映射、System ARXML 的 `I-SIGNAL` 与 `I-SIGNAL-TO-I-PDU-MAPPING`、ECUC `ComSystemTemplateSystemSignalRef` 的完整引用，再接现有 COM/PduR/CanIf 路径。候选必须唯一且方向一致才标记 `resolved`；缺引用、多候选、方向冲突和 ECUC 局部路径分别保留原因。它不会按短名或字串相似度配对。两版追踪按端口与数据元素身份比较，报告 SystemSignal、COM、路由和 CanIf 的实际字段变化；追踪与比较都可从原输入重算复验。

```sh
workbench trace-cross-tool --mapping mapping-audit.json --system communication.arxml \
  --project project.dpa --output cross-tool-trace.json
workbench verify-cross-tool cross-tool-trace.json
workbench compare-cross-tool before.json after.json --output cross-tool-impact.json
workbench verify-cross-tool-impact cross-tool-impact.json
```

本地隔离工程的 1 条 Rx、1 条 Tx 跨工具链均为 `resolved-in-scope`，只证明这些显式引用与方向在输入范围内闭合。CFG 原生校验仍有 25 个错误，生成与 CAN 实测未通过本项证明。公开回归从两个结构不同的合成 ECUC 项目构造 Developer/System 输入，覆盖正常链、断引用、方向冲突和 SystemSignal 变化。

跨工具变更到验收项使用显式绑定表。每条绑定含 Developer 端口、数据元素、已解析的 ECUC ComSignal 完整路径和已有项目报告中的验收 ID；平台核验 ComSignal 来自变更前或后的已解析追踪，验收 ID 存在，且其上一轮 evidence 文件的哈希、JSON 指针与记录的 actual 值一致。受影响项输出 `rerun_required=true` 和 `previous_status`，不把上一轮通过解释为变更后通过。无绑定的变化保留为 `unbound`。绑定由工程人员声明，关系语义仍需审阅。

```json
{"schema_version":"cross-tool-acceptance-bindings-0.1","project_name":"Demo acceptance","links":[{"port":"/Components/Node/Out","data_element":"/Interfaces/State/Ready","com_signal":"/Demo/Com/ValueA","acceptance_ids":["TX_VECTOR"]}]}
```

```sh
workbench assess-cross-tool-acceptance --impact cross-tool-impact.json \
  --bindings bindings.json --project-report bundle/project-report.json \
  --output acceptance-impact.json
workbench verify-cross-tool-acceptance acceptance-impact.json
```

这项能力已用公开合成项目的真实跨工具变更和项目验收证据做正负例。隔离商业工程的同源 Workbench 项目验收基线在随后建立；公开示例绑定只用于说明契约，不指代该商业工程。

严格来源门可选用 `--require-project-provenance`。它保留旧 0.1 调用，输出新 `cross-tool-acceptance-impact-0.2`，先重放完整 ECUC 项目验收包，再要求跨工具前/后追踪的 DPA SHA-256 分别等于项目包前/后 DPA 快照。它验证的是 **ECUC DPA 同源**；Developer 导出 ARXML 的语义一致性仍需单独检查。严格结果的离线 verifier 会重复这些核验。

```sh
workbench assess-cross-tool-acceptance --impact cross-tool-impact.json \
  --bindings bindings.json --project-report bundle/project-report.json \
  --require-project-provenance --output acceptance-impact.json
```

隔离商业工程现已建立只要求通信结构的 Workbench 静态项目基线：项目报告 `passed`，项目包重放 `passed`。额外声明的影响覆盖检查为 `unassessed`，所以它没有被计入这个窄范围基线。受控演练仅在忽略目录复制 Developer 导出并改变一条映射；跨工具差异为 `changed`，严格来源门给出 `COMMUNICATION` 前次 `passed`、本次 `rerun_required=true`，结果离线复验通过。该演练不是新的实际 CFG 配置，也不是 CAN 总线运行。

本地能力复核：Developer 导出的两条显式映射均解析；现有 ECUC 通信 trace 形成 73 条范围内路径且离线复验通过；现有工程审查离线复验通过，但审查状态为 `attention-required`。CFG 原生 XML 摘要则明确为 25 errors、59 warnings、生成阶段 `ERROR`（6 个 generator failed）。这些是不同层次的结论：引用闭合只覆盖输入文件内的结构，原生配置错误仍要在 CFG 中处理；CAN 总线收发和物理 ECU 尚无本工程实测。

七周实操计划与平台的接点：先用 Developer 导出验证现有 Rx/Tx data mapping；随后在 CFG 配置 COM/PduR/CanIf 时使用既有 ECUC 审查和通信 trace；Week 6 的候选建议只能引用本审计的已解析映射，Week 7 的写回仍需在隔离工程执行并由 CFG 重新校验。当前基础设施不把学习练习完成情况当成配置链已验收。计划标称每周 18 小时，若连续两周执行则为 36 小时，超过路线图原每两周总计 20–30 小时预算；应在实际排期中明确新预算或减少并行平台工作。计划中的测试 DBC 是经典 CAN 8 字节帧，CAN FD 仍需另备样本与配置证据。
