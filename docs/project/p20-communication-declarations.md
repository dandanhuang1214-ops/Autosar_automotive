# P20 通信声明：当前支持范围

P20a 提供只读预检，P20b 的通用发送/接收与 P20c 项目接入尚待实现。以下命令不打开总线，不写运行输出；成功时 stdout 为 `communication-plan-0.1`，拒绝时退出 1。需要既有 `[can]` 可选依赖。

```bash
workbench plan-communication examples/window_control/window_control.dbc examples/window_control/bsw_intent.json examples/window_control/communication_vectors.json
workbench plan-communication examples/thermal_control/thermal_control.dbc examples/thermal_control/bsw_intent.json examples/thermal_control/communication_vectors.json
```

声明使用 `communication-vectors-0.1`，只包含 `schema_version` 和 `vectors`。每个向量包含唯一的 `id`、DBC `message`、本地 `direction`（tx/rx）、完整的数值 `signals` 和 `timeout_seconds`（大于 0、最大 5 秒）；每份声明最多 256 个向量。本地 ECU 来自 BSW intent，不允许向量覆盖。项目 0.1/0.2 与原 CAN lab 保持原有入口；本阶段不能把新声明交给旧 runner 执行。

支持 classic CAN 标准/扩展 ID、1–8 字节、非 multiplexed 整数线编码信号，物理值可带符号、缩放和偏移；枚举使用数值，解码不返回 choice 字符串。Rx 要求每个声明信号在 DBC 中都以本地 ECU 为接收者。ThermalControl 是公开合成的三报文样例，含两个 Tx 与一个 Rx，长度分别为 4/2/3 字节。

预检拒绝未知/缺失/额外信号、未知消息、重复向量 ID 或 DBC 身份、方向冲突、frame ID/DLC 不一致、不可编码/超范围值、bool/非有限数值、非法超时、CAN FD、container、multiplex 和浮点线编码。JSON 重复成员也拒绝。schema 检查结构与数值边界；唯一向量 ID、消息引用、DBC/intent 关系和编码约束由语义预检负责。

计划包含三份输入的 SHA-256、声明值、payload、原始整数和量化后的物理值。量化完全沿用 cantools 的 encode/decode：82.34°C 在示例的 0.1°C 分辨率下编码为 1223，解码约为 82.3°C。后续运行应按原始整数比较，不引入任意浮点容差。计划是审阅产物；不能把外部修改过的计划当成已经验证的执行授权。

回归入口：`python scripts/run_communication_preflight_scenarios.py --output output/p20-preflight`。脚本调用真实 CLI、验证两个计划的 schema，并归档未知信号被拒绝的结果；Windows/Ubuntu CI 上传 `communication-preflight`。这证明输入编译，不证明任何总线收发、SocketCAN 或物理 ECU 行为。
