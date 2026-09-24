# P21 通信对象图与配置影响

输入为 P20 `workbench-project-0.3` 项目，安装 `.[can]`。构图与比较不打开总线；其结果用于安排复验，不代表那些验收项已经执行。

```bash
python -m automotive_workbench.cli build-communication-graph \
  examples/thermal_control/project.json --output output/thermal-graph
python -m automotive_workbench.cli compare-communication-config \
  baseline/project.json candidate/project.json --output output/config-impact
python -m automotive_workbench.cli verify-communication-graph \
  output/config-impact/report.json
python scripts/run_communication_graph_scenarios.py --output output/p21-demo
```

每个输出目录含 `report.json` 与 `report.md`；必须为空或不存在。退出码：0 为分析完成（包括有配置变化），2 为图规则失败或不可比较，1 为非法输入/输出。独立复验返回 0 或 2。图失败不阻止其失败证据被复算。

## 身份、关系和来源

`communication-graph-0.1` 为闭合的版本化报告。对象 ID 是分别 URL 编码的 `comparison_key/local_ecu/type/name`；支持 ComSignal、IPdu、PduRRoute、CanIfPdu。同名对象跨类型或跨项目不混同。名称改变被视为删除和新增，不猜测重命名。同一个报文多个信号引用同一条路由合法；跨报文重用路由身份或冲突端点报错。

图从 intent 0.2 的显式 message/signal 声明产生，依赖边为 `signal-in-pdu`、`pdu-route`、`route-canif`。边表示配置依赖，**不是函数调用、数据流方向或 AUTOSAR ECUC 容器证明**；Tx/Rx 另存于对象，并与 DBC 本地 ECU sender/receiver 事实核对。0.1 intent 缺少本地 ECU/方向，保留旧命令读取，新图入口明确拒绝。

每个对象/关系保存 intent JSON Pointer；已解析 DBC 对象保存 `message:<encoded-name>/signal:<encoded-name>` 或消息 locator。`source_artifacts` 保存 project/DBC/intent/contract/vectors 五份确切输入字节的 Base64 与 SHA-256，可脱离原目录重放。来源 ID 是逻辑角色，不是绝对文件路径。`verify-communication-graph` 从这些快照重建结论并逐字段比较，检测图、传播路径、验收集合、输入哈希被修改；这不是签名或生产者认证。

## 规则覆盖与依据

下面全部是本平台的受限通信 intent 约束，不宣称符合某一 AUTOSAR release 或厂商 ECUC。规范性依据为本页定义、仓库 [intent 契约](../../schemas/bsw-intent.schema.json)、[P20 向量契约](../../schemas/communication-vectors.schema.json) 和输入 DBC 解析事实。每类的正常/失败检查见 [测试](../../tests/test_communication_graph.py)；真实 CLI 正负场景见 [重放脚本](../../scripts/run_communication_graph_scenarios.py)。

| 类别 / 规则 | 依据与拒绝条件 | 正例 / 负例 |
|---|---|---|
| 断引用 `GRAPH-MISSING-REFERENCE` | signal 必须解析到 DBC message/signal 及声明的 IPdu/CanIfPdu；向量覆盖其映射路径 | 双项目 Tx/Rx / Absent IPdu、缺 DBC signal |
| 重复身份 `GRAPH-DUPLICATE-IDENTITY` | 同一 scope/type/name 唯一；共享 route 必须同报文、方向和端点 | ThermalStatus 两信号共享 route / 两 ComSignal 同名、重复 message、跨报文 route |
| 方向 `GRAPH-DIRECTION` | 显式 tx/rx 与本地 ECU DBC sender/receiver、父 message 一致 | 双向正常链 / signal 与 message 方向翻转 |
| 长度布局 `GRAPH-LENGTH-LAYOUT` | can_id/dlc 与 DBC 一致；声明信号属性与 DBC 一致；映射报文内全部信号不得重叠或越界，支持 Intel/Motorola 位序 | 正常 4/2/3 字节 / DLC、bit_length、实际 DBC overlap/out-of-bounds |
| 路由端点 `GRAPH-ROUTE-ENDPOINT` | signal 的 IPdu/CanIfPdu 必须属于其 message | 正常 shared route / 指向 PumpStatus 的 CanIfPdu |
| 配置变化影响 | 同 comparison_key/local_ecu 且两图通过规则后，按稳定 ID 比较属性；在新旧依赖图并集传播 | 原样/重排无语义变化 / scale、对象重命名、测试定义及 contract 变化 |

FD、multiplex 和 float 线编码生成 `GRAPH-UNSUPPORTED`，不能当作正常图继续比较。未知 vendor 容器、硬件映射、调度和实际运行行为保留在 unknowns；没有向量的映射报文显式标记未知覆盖。既有 project、runtime、review、compare 契约未修改。

## 如何读影响报告

`communication-impact-0.1` 保留两侧完整图与快照；`source_changes` 列出字节不同的来源，`locator_changes` 列出来源定位变化。`changes` 仅列语义新增/删除/修改，因此重排 intent 数组会改变源哈希和 locator，但不触发语义重跑。

`affected` 每项包含从某个变化对象到该对象的依赖路径，边可在两图中找到。传播是无向、保守的同通信链依赖闭包：PDU 变化可能影响其所有信号，信号变化可能要求重跑整个 PDU 的路径；不能解释成实际软件控制流。报文对象包含 DBC 报文属性和信号布局，因此一条信号变化可能同时改变该报文的 IPdu/CanIfPdu 事实。

`vectors` 列受影响报文的声明向量 ID；`requirements` 包括对应 `/vectors/<id>/...` 验收项以及整体 canonical/mapping/communication 验收。验收或向量定义变化触发全部声明项复核；contract 字节变化属于图外语义，显式 unknown 并要求全部验收项重跑。generation 字段变化同样触发复核，但本图不验证外部生成器及其文件，仍须执行既有 generation gate。

公开 `scale-impact` 将 ThermalStatus 的 CoolantTemperature DBC 比例从 0.1 改成 0.2；输出受影响四类对象、`thermal-status` 向量及相关验收 ID，排除未受影响的 `pump-status`、`cooling-request` 向量级验收。不同项目或无效图返回 not-comparable，不能用相似名称强行推断。完成分析后，使用现有 `run-project` 执行候选项目，继续 review/compare 验收闭环。
