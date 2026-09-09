# P4a 跨层通信方向契约调研

## 问题

原 `bsw-intent-0.1` 已能保存 DBC Signal、SWC、COM、I-PDU、PduR 和 CanIf 引用，也能发现 message/signal 层的 PDU 引用不一致，但没有声明“从哪个 ECU 看方向”。仅凭 `PduRRoute_*_Tx` 或 `CanIf*TxPdu` 名称推断方向不可靠：这些名称是样例设计名，不是可移植语义。

## P4a 决策

`bsw-intent-0.2` 增加根级 `local_ecu`，并要求每个 message 和 signal 显式声明 `direction=tx|rx`。DBC adapter 使用 DBC 的 message sender 和 signal receiver 推导本地 ECU 方向，再与 intent 比较：

- 本地 ECU 是 message sender：`tx`；
- 本地 ECU 不是 sender、但出现在 signal receiver：`rx`；
- 两者都不满足：`unresolved`，作为方向不匹配报告。

message 与 signal 的显式方向也必须相同。sender、receiver、方向和既有 I-PDU/CanIf 引用分别校验，避免一个字段的正确掩盖另一层错误。

## 证据输出

`validate-map` 在既有 Finding 外新增 `communication_paths`。每条路径同时保留 DBC sender/receiver 事实、本地 ECU 方向以及 `SWC DataElement → Port → COM Signal → I-PDU → PduR route → CanIf PDU` 标识。公开车窗样例形成两条路径：

- `WindowPosition`：BODY_ECU `tx` 到 TESTER；
- `RequestedDirection`：TESTER 发送、BODY_ECU `rx`。

## 边界

本契约验证公开 DBC 与 vendor-neutral intent 的内部一致性，不生成 ECUC，不验证供应商 BSWMD、PDU mode、handle ID、controller/hardware object、RTE API 或总线上的实际收发。对象名后缀不会成为判定依据。

## P4b 静态—运行时绑定

P4b 将 CAN lab 升级到 `can-lab-0.2`，保留原 `WindowStatus` Tx round trip，同时新增 `WindowCommand` Rx 场景。两个场景都在 evidence 内显式保存 message name、相对 BODY_ECU 的 direction、frame ID、payload 和 decoded signal，因而不需要根据场景名称或数组位置猜测身份。

`run-communication-chain` 在同次编排中完成静态校验和 runtime lab，然后以 `DBC message + signal` 为稳定 identity 绑定两层证据。接受一条路径必须同时满足：

- 静态 `validate-map` 整体通过；
- runtime lab 整体及对应 scenario 通过；
- decoded evidence 存在完全一致的 message/signal identity；
- 静态与运行时 direction、frame ID 完全一致。

缺失 identity、frame ID 漂移、direction 漂移或静态校验失败都会生成独立 Finding，并使组合报告 `status=failed`。组合报告记录 DBC、BSW intent 和实际 runtime JSON 的 SHA-256，避免报告引用未绑定的输入。

P4 至此形成公开样例的静态—运行时完整通信证据链。virtual backend 仍只证明进程内确定性编解码与收发；SocketCAN、OpenBSW、目标 ECU、RTE/COM API、控制器配置和电气行为不在本阶段证明范围内。
