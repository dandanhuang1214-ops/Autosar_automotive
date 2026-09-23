# P20 通信声明：当前支持范围

P20a 提供只读预检，P20b 提供声明驱动的通用发送/接收；P20c 项目接入尚待实现。以下命令不打开总线，不写运行输出；成功时 stdout 为 `communication-plan-0.1`，拒绝时退出 1。需要既有 `[can]` 可选依赖。

```bash
workbench plan-communication examples/window_control/window_control.dbc examples/window_control/bsw_intent.json examples/window_control/communication_vectors.json
workbench plan-communication examples/thermal_control/thermal_control.dbc examples/thermal_control/bsw_intent.json examples/thermal_control/communication_vectors.json
```

声明使用 `communication-vectors-0.1`，只包含 `schema_version` 和 `vectors`。每个向量包含唯一的 `id`、DBC `message`、本地 `direction`（tx/rx）、完整的数值 `signals` 和 `timeout_seconds`（大于 0、最大 5 秒）；每份声明最多 256 个向量。本地 ECU 来自 BSW intent，不允许向量覆盖。项目 0.1/0.2 与原 CAN lab 保持原有入口；本阶段不能把新声明交给旧 runner 执行。

支持 classic CAN 标准/扩展 ID、1–8 字节、非 multiplexed 整数线编码信号，物理值可带符号、缩放和偏移；枚举使用数值，解码不返回 choice 字符串。Rx 要求每个声明信号在 DBC 中都以本地 ECU 为接收者。ThermalControl 是公开合成的三报文样例，含两个 Tx 与一个 Rx，长度分别为 4/2/3 字节。

预检拒绝未知/缺失/额外信号、未知消息、重复向量 ID 或 DBC 身份、方向冲突、frame ID/DLC 不一致、不可编码/超范围值、bool/非有限数值、非法超时、CAN FD、container、multiplex 和浮点线编码。JSON 重复成员也拒绝。schema 检查结构与数值边界；唯一向量 ID、消息引用、DBC/intent 关系和编码约束由语义预检负责。

计划包含三份输入的 SHA-256、声明值、payload、原始整数和量化后的物理值。量化完全沿用 cantools 的 encode/decode：82.34°C 在示例的 0.1°C 分辨率下编码为 1223，解码约为 82.3°C。运行按原始整数比较，不引入任意浮点容差。计划是审阅产物；不能把外部修改过的计划当成已经验证的执行授权。

回归入口：`python scripts/run_communication_preflight_scenarios.py --output output/p20-preflight`。脚本调用真实 CLI、验证两个计划的 schema，并归档未知信号被拒绝的结果；Windows/Ubuntu CI 上传 `communication-preflight`。这证明输入编译，不证明任何总线收发、SocketCAN 或物理 ECU 行为。

## 执行声明

```bash
workbench run-declared-communication examples/thermal_control/thermal_control.dbc examples/thermal_control/bsw_intent.json examples/thermal_control/communication_vectors.json --output output/thermal-runtime
workbench run-declared-communication examples/window_control/window_control.dbc examples/window_control/bsw_intent.json examples/window_control/communication_vectors.json --output output/window-runtime
```

默认使用唯一 virtual channel；显式 `--interface socketcan --channel vcan0` 可选择 SocketCAN。runner 在 probe/open/send 和创建运行输出前重新预检全部声明与 BusConfig，拒绝 FD/self reception，要求输出为空或不存在，并检查预检期间的输入哈希漂移。它不接受用户修改过的计划 JSON 作为执行入口。

每个向量创建 local/peer 两个端点，Tx 为 local→peer，Rx 为 peer→local。两端使用该向量的标准 11 位或扩展 29 位精确过滤器；向量之间重新开关端点，避免旧队列残留。同一向量的 send 与 recv 共用声明 timeout 预算；open/shutdown 的耗时取决于底层 backend，不声称该预算是整个进程的硬实时上限。收到帧后核对 ID、extended 标志、classic/data frame、DLC 和原始信号值；payload 与物理解码值完整保留。未用 padding bits 不参与信号相等判断。异常下分别尝试关闭所有已打开端点，关闭失败使向量失败。

输出 `declared-runtime-report.json`（`declared-communication-runtime-0.1`）和 Markdown。JSON 保存输入哈希、完整计划、backend probe、过滤/通道锁证据，以及按稳定 ID 索引的 `vectors`，例如 `/vectors/thermal-status/status`。每个结果记录 sender/receiver、实际帧或 null、错误与 cleanup。退出码：0 passed、1 输入/输出拒绝、2 failed、3 blocked；blocked 不制造帧观测。

此路径由当前进程创建两个本地端点：virtual 或 Linux vcan 收发不证明独立 ECU、目标 BSW、物理 CAN 或电气/时序行为。旧 `run-project`、`run-can-lab` 和 `run-communication-chain` 保持原契约；项目/review/compare 集成留给 P20c。

## 场景与 SocketCAN 复验

```bash
python scripts/run_declared_communication_scenarios.py --output output/declared-scenarios
bash scripts/linux/run_socketcan_declared_communication.sh --python .venv/bin/python --output output/socketcan-thermal
```

场景脚本运行两项目真实 CLI、缺失接口 blocked，并在真实 virtual endpoints 上显式拦截 send：错误 ID 实际发送后由过滤器丢弃，no-send 完全抑制发送，两者应产生 receive_timeout。`injection.json` 标明注入方式及发送记录，不把模拟故障描述为物理 ECU 故障。Windows/Ubuntu CI 上传 `declared-communication`。

SocketCAN 脚本复用现有 `socketcan-<channel>.lock` 锁命名与 `flock`，保存 host probe，默认运行 ThermalControl；可用 `--dbc/--intent/--declaration` 指定车窗。脚本不会自动创建接口；缺失时保存 blocked。需要恢复本机接口时显式执行既有 `bash scripts/linux/setup_vcan.sh --apply`。锁只协调使用同一约定的 Workbench 进程，不能排除外部发送者。
