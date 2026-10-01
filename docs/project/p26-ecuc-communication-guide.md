# ECUC 通信跨层引用定位

从 DPA/collection 选中的 ECUC 模块重建 Com → EcuC/PduR → CanIf → Can 引用链。使用与首轮体检相同的只读输入解析器，保留 `ecuc-project-inspection-0.1` 输出兼容；新报告独立版本为 `ecuc-communication-0.1`。

```bash
workbench trace-ecuc-communication /path/to/project.dpa --output output/ecuc-chain
workbench verify-ecuc-communication output/ecuc-chain/ecuc-communication.json
```

源码环境用 `PYTHONPATH=src python -m automotive_workbench.cli` 替换 `workbench`。输出须为空或不存在，并位于源工程目录之外；输入沿用 UTF-8、r4.0 XML namespace、每文件 64 MiB/总量 256 MiB 的边界。最多输出 20000 条路径，超限在写输出前拒绝。

## 连接规则

| 起点 | 连接依据 | 目标 |
|---|---|---|
| ComIPdu | ComIPduSignalRef / ComIPduSignalGroupRef | ComSignal / ComSignalGroup |
| ComSignalGroup | 实际子容器关系 | ComGroupSignal |
| ComIPdu | ComPduIdRef | EcuC Pdu |
| PduRRoutingPath 的源/目标子容器 | PduRSrcPduRef / PduRDestPduRef | 各自的 EcuC Pdu |
| CanIf Tx/Rx PDU | CanIfTxPduRef / CanIfRxPduRef | EcuC Pdu |
| CanIf Tx PDU | CanIfTxPduBufferRef → CanIfBufferHthRef → CanIfHthIdSymRef | Buffer → HTH → CanHardwareObject |
| CanIf Rx PDU | CanIfRxPduHrhIdRef → CanIfHrhIdSymRef | HRH → CanHardwareObject |
| CanHardwareObject | CanControllerRef | CanController |

`ComIPduDirection=SEND/RECEIVE` 决定 tx/rx：Tx 从 Com 对应 PduR source 连接 destination 及 CanIf Tx；Rx 从 Com 对应 destination 反查 source 及 CanIf Rx。CanObjectType 同时须为 TRANSMIT/RECEIVE。名称和 Tx/Rx 后缀不参与判定。PduR 两端可以引用不同全局 PDU，连接必须经过实际同一个 routing path；多目标分支分别保留。一个全局 PDU 对应多个 CanIf 配置时全部分支标 partial，等待明确配置选择。

报告的路径按“从 Com 向硬件定位”的顺序排列，**不是 Rx 实际数据流方向**。`edges` 的 owner/target 始终忠实记录 XML 引用或父子关系；路径可逆向使用引用以完成定位。节点 `source` 及参数/边的 `source` 提供文件、完整对象路径和带兄弟序号的 XML 定位。

## 输出与结果含义

- `ecuc-communication.json`：来源 hash、选定模块、节点及原始参数、引用边、每条路径的信号/组成员、缺口与未评估引用。`snapshot/` 保留原字节。
- `resolved-in-scope` / 退出 0：所有列出的 ComIPdu 路径在受支持规则内完成引用和方向连接。
- `partial` / 退出 2：有缺引用、类型错误、重复身份、必需引用数量异常、未知方向、条件配置或链路断点；每条路径 `gaps` 说明原因。
- `no-paths` / 退出 2：没有受支持的 ComIPdu；不能以空路径列表宣称成功。
- 输入/报告非法 / 退出 1。复验成功退出 0，包括可信复现的 partial/no-paths 报告；复验结论不意味着配置已修复。

完整输出移到新路径、原输入删除后仍能复验。报告结论、来源字节和额外库存变化均拒绝。旧体检报告仍可独立复验。

`inspection_status`/`inspection_findings` 保留全项目首轮结构问题；路径 resolved 不会将未绑定 RTE 任务等其他问题清零。`unassessed_references` 逐项保留范围外字段/实例引用，`unsupported_containers` 列出未解释的通信模块容器（包括包装容器，不自动视为错误）。变体条件不自动求值，位于受支持链中的条件节点/引用/方向为 partial。

定义字段短名只在其模块定义上下文中解释，完整 DEFINITION-REF 保留。这是受限结构词汇匹配，不等于确认厂商定义语义或 XSD 合规。未检查 payload 布局、PDU 长度、CAN ID、调度、网关/TP、完整厂商扩展或生成结果；resolved 不代表 ECU 能收发，也不恢复商业工具验收。

## 公开回归

```bash
python scripts/run_ecuc_communication_scenarios.py --output output/ecuc-chain-scenarios
```

合成正常 Tx/Rx（含组信号）、缺引用、错误目标类型、外部未知引用、重复对象、方向冲突、厂商未知引用、条件配置及无支持路径共九例；移走报告并删除原输入后九份复验；结论、来源、库存三类篡改拒绝。单测另覆盖路由端点不匹配、多目标、CanIf 选择歧义、引用数量和 XML 定位。真实本地工程的报告仅存忽略目录，不进入公开测试或 CI。

## 字段依据

词汇参考固定为 AUTOSAR CP R24-11。此选择不把输入 schemaLocation 或厂商版本改写为 R24-11，也不实现该版本所有约束。

- [COM 规范](https://www.autosar.org/fileadmin/standards/R24-11/CP/AUTOSAR_CP_SWS_COM.pdf)：ComIPdu 的 PDU/信号引用；10.2.15 的 ComSignalGroup 包含 ComGroupSignal。
- [PDU Router 规范](https://www.autosar.org/fileadmin/standards/R24-11/CP/AUTOSAR_CP_SWS_PDURouter.pdf)：PduRSrcPduRef/PduRDestPduRef 关联全局 EcuC Pdu。本实现不宣称覆盖路由队列或全版本约束。
- [CAN Interface 规范](https://www.autosar.org/fileadmin/standards/R24-11/CP/AUTOSAR_CP_SWS_CANInterface.pdf)：7.11 的 Tx buffer/HTH 关系及 CanIfRxPduCfg 的 HRH/PDU 引用。
- [CAN Driver 规范](https://www.autosar.org/fileadmin/standards/R24-11/CP/AUTOSAR_CP_SWS_CANDriver.pdf)：CanHardwareObject 的 CanObjectType、CanControllerRef。
