# CAN 运行时、日志与回放阶段调研

日期：2026-08-14  
状态：待用户确认方案，尚未开始本阶段编码  
范围：Automotive Workbench 下一阶段；不包含 UDS、AI 前端和量产 ECUC。

## 1. 当前平台位置

平台已经具备：

- DBC → BSW intent → canonical contract 静态一致性校验；
- python-can virtual 双节点收发与 cantools 编解码；
- 错误 CAN ID、非法物理值、超时、周期和恢复实验；
- JSON/Markdown 证据报告及 CI。

当前缺口是：报文只存在于单次运行内，不能录制、离线分析、按原始时间回放，也没有可替换的 virtual/SocketCAN backend 配置契约。

## 2. 上游事实

### python-can 已经提供后端抽象，不应自行重写 Bus

python-can 的 `BusABC` 本身就是物理或虚拟 CAN 总线的统一包装；`Bus` 可以按 `interface/channel` 实例化 virtual、SocketCAN、PCAN、Vector 等后端。过滤可以由内核/硬件实现，不支持时再回退到软件过滤。因此平台只需要自己的 `BusConfig/BusFactory` 薄层，不需要开发新的 CAN 栈或重写 `BusABC`。

来源：

- <https://python-can.readthedocs.io/en/stable/index.html>
- <https://python-can.readthedocs.io/en/stable/internal-api.html>
- <https://python-can.readthedocs.io/en/stable/api.html>

### virtual backend 适合 CI，但不是跨进程真实总线

python-can virtual 的同 channel 实例只能在同一 Python 进程中互通；它保证可靠交付和顺序，但不实现带宽限制、ID 仲裁或高负载优先级。它适合确定性测试和 Windows CI，不应被当作真实 CAN 网络。

来源：<https://python-can.readthedocs.io/en/stable/interfaces/virtual.html>

### SocketCAN/vcan 是 Linux 执行面的正确目标

Linux 内核把 CAN 设备作为网络接口，并提供 PF_CAN socket；vcan 可以在无硬件时收发 CAN frame。python-can 的 SocketCAN 后端继续使用相同的 `Bus/Message` API，因此实验逻辑可以复用，只切换配置。

来源：

- <https://docs.kernel.org/networking/can.html>
- <https://python-can.readthedocs.io/en/stable/_modules/can/interfaces/socketcan/socketcan.html>

### WSL2 SocketCAN 不能假设开箱即用

Eclipse OpenBSW 官方文档明确给出了 WSL 自定义内核启用 CAN/vcan 的流程，说明默认 WSL 内核可能缺少所需 CAN 模块。该过程包括编译内核、加载模块和创建 vcan，成本明显高于普通 Python 依赖安装。因此 SocketCAN 必须有环境探测和跳过机制，不能让 Windows 主线 CI 被它阻塞。

来源：<https://eclipse-openbsw.github.io/openbsw/sphinx_docs/doc/dev/learning/setup/setup_wsl_socketcan.html>

### 日志和回放不需要自造底层实现

python-can `Logger/LogReader` 已支持 ASC、BLF、CSV、SQLite、can-utils `.log`、MF4 和 TRC；`MessageSync` 可以按原始 timestamp 回放，也可以使用固定 gap，并可跳过超长静默。cantools 可以直接解码 candump/can-utils 日志并绘图。

来源：

- <https://python-can.readthedocs.io/en/stable/file_io.html>
- <https://cantools.readthedocs.io/en/stable/>

### OpenBSW 是后续运行时消费者，不是日志内核

OpenBSW POSIX 版可以在无汽车硬件的环境运行；主机支持 SocketCAN 时可直接使用。官方 Demo 覆盖 CAN 和 UDS。但 OpenBSW 是 C++ 汽车 BSW SDK，并非完整 AUTOSAR Classic 商业栈，也不应该成为平台日志格式的拥有者。

来源：

- <https://eclipse-openbsw.github.io/openbsw/sphinx_docs/doc/dev/platforms/posix/index.html>
- <https://eclipse-openbsw.github.io/openbsw/sphinx_docs/doc/dev/index.html>

## 3. 日志格式方案比较

| 方案 | 优点 | 缺点 | 当前判断 |
|---|---|---|---|
| can-utils `.log` | 文本可审计；SocketCAN/candump 生态直接兼容；cantools 可直接解码；python-can 可读写和回放 | 不适合大量信号级查询；元数据有限 | 首阶段原始帧证据首选 |
| SQLite `.db` | python-can 原生支持；可按时间、ID 查询；适合较大实验 | 二进制文件不便代码审查；writer 始终追加；仍需单独 manifest | 第二层可选索引，不作为唯一真相源 |
| ASC | 与部分商用工具交换较友好；python-can 原生支持 | 文本更复杂；首阶段对 SocketCAN 学习收益不如 `.log` | 后续导入/导出 adapter |
| BLF | 紧凑、常见于 Vector 环境；python-can 支持 | 二进制不可直接审计；个人公开 Demo 不需要优先 | 商业桥接阶段再做 |
| MF4 | 适合测量数据和长时记录 | 需要 asammdf 可选依赖；python-can 文档提示其 MF4Reader 只支持自身 MF4Writer 产生的文件 | 当前不引入 |
| 自定义 JSONL 原始帧 | 易扩展元数据 | 重复发明日志标准；与 candump/cantools/商用工具互操作差 | 不采用为原始日志 |

## 4. 三个实施方案

### 方案 A：轻量互操作优先（推荐）

```text
python-can BusConfig
→ capture 为 can-utils .log
→ LogReader + MessageSync replay
→ cantools 离线 decode
→ experiment manifest + Findings + report
```

交付：

1. `BusConfig`：`interface/channel/receive_own_messages/fd/filters`；
2. `capture`：录制指定数量或时长，输出 `.log`；
3. `decode-log`：DBC 解码、未知 ID、DLC/DecodeError、周期与超时 Finding；
4. `replay`：保留 timestamp 或固定 gap，目标可以是 virtual 或 SocketCAN；
5. manifest 记录 DBC hash、backend、参数、开始时间和产物 hash；
6. virtual 进入 Windows/Linux CI；SocketCAN 测试只有环境探测成功才运行。

优点：依赖少、可审计、与 Linux/cantools 直接互通，并为硬件 backend 保留接口。  
不足：大量日志查询能力一般，后续可能需要 SQLite 索引。

### 方案 B：查询平台优先

在方案 A 基础上同时写入 SQLite，把每帧和解码信号索引化。

优点：后续 Web/API、统计、故障检索更方便。  
不足：现在会提前引入数据迁移、schema 版本、并发写入和双份真相问题，超出当前 Demo 所需。

### 方案 C：测量标准优先

从现在开始以 MF4/ASAM MDF 为中心，加入 asammdf 和信号级测量数据。

优点：更靠近成熟测量分析生态。  
不足：依赖和格式复杂度高；当前只有两个 CAN message，收益不足；python-can 的 MF4 互操作边界也需要额外验证。

## 5. 推荐决策

推荐选择方案 A，并规定“双层证据”而非“双份原始真相”：

```text
原始事实层：can-utils .log（frame + timestamp）
工程证据层：manifest.json + findings.json + report.md
```

DBC 只用于解码，不修改原始帧；同一 `.log` 可以更换 DBC 重新分析。报告必须记录所用 DBC 的 hash，避免日志不变但数据库版本变化造成结果无法复现。

不建议现在使用 SQLite 作为主存储，也不建议引入 MF4。等出现以下任一条件再升级：

- 单次日志超过约十万帧且离线过滤明显变慢；
- 需要跨多次实验做 SQL 查询；
- 需要接入真实 MF4/BLF/ASC 企业样例；
- 平台开始提供 Web/API 查询而不只是 CLI/report。

## 6. 建议实施顺序

### 阶段 R1：日志内核

- BusConfig/BusFactory；
- `.log` capture/replay；
- DBC 离线 decode；
- 未知 ID、DLC 不符、decode error Finding；
- manifest 与 SHA-256；
- virtual 自动化测试。

验收：同一录制文件回放后，frame ID、payload、顺序和相对时间语义可重复；更换错误 DBC 能产生确定性 Finding。

### 阶段 R2：SocketCAN adapter

- 只做 backend 配置和环境探测；
- 使用 `vcan0` 复用 R1 测试；
- 提供 setup 文档但不自动修改 WSL 内核；
- 没有 vcan 时明确 skip，不伪造通过。

验收：相同实验在 virtual 和 vcan 后端产生等价的 frame/decode Finding；backend 特有字段只出现在环境证据中。

### 阶段 R3：OpenBSW POSIX spike

- 限时构建官方 Demo；
- 定位 SocketCAN 入口、CAN Rx/Tx 调用链和测试入口；
- 只增加一个公开车窗报文适配或一个测试；
- 构建/许可/模块/测试任一长期不满足则退出，不耦合平台核心。

验收：OpenBSW 产生或消费的 CAN frame 能进入同一 `.log` 和 Finding 流程。

## 7. 需要共同确认的问题

1. 是否接受方案 A：`.log` 原始事实 + JSON/Markdown 工程证据？
2. R1 是否先只支持 Classical CAN，CAN FD 放到 SocketCAN/真实硬件阶段？推荐：是。
3. replay 默认是否保留原始相对时间，同时提供 `--gap-ms` 固定间隔覆盖？推荐：是。
4. SocketCAN 环境不可用时，是否允许 R1 完成并把 R2 标记为环境阻塞，而不是停止整个平台？推荐：是。
5. 是否暂缓 SQLite/MF4/BLF，直到出现真实查询或企业格式需求？推荐：是。
