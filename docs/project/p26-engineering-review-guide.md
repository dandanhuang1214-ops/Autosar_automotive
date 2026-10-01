# ECUC 工程审查与配置变更影响

P26 的完整操作路径是：选择真实配置 → 审查通信/应用/调度绑定/模式结构 → 保存快照 → 比较两版 → 定位受影响对象 → 搬移后复验。仅消费文件，不执行厂商工具，也不修改源工程。

## 运行与交付

```bash
workbench review-ecuc-project before/project.dpa \
  --application before/application.arxml --tool-log before/validation.log \
  --output output/ecuc-before
workbench review-ecuc-project after/project.dpa \
  --application after/application.arxml --tool-log after/validation.log \
  --output output/ecuc-after
workbench compare-ecuc-reviews \
  output/ecuc-before/ecuc-review.json output/ecuc-after/ecuc-review.json \
  --output output/ecuc-impact
workbench verify-ecuc-review output/ecuc-before/ecuc-review.json
workbench verify-ecuc-impact output/ecuc-impact/ecuc-impact.json
```

`--application` 和 `--tool-log` 可重复，也可省略。未提供应用文件时引用保持 unassessed，不从对象名推断组件或扫描整个磁盘。Windows 可将上述参数放在同一行运行；源码环境用 `PYTHONPATH=src python -m automotive_workbench.cli` 替换 `workbench`。

打开输出中的 `index.html` 查看当前结构检查、缺口、变更摘要和影响证据。HTML 显示摘要与有限列表，完整对象库存/参数/引用/证据边保存在 JSON；大工程完整 JSON 可能较大，不将全部原始对象重复嵌入网页。HTML 和 JSON 都参加复验。

审查目录包含 `ecuc-review.json`、`index.html`、`snapshot/`。比较目录内的 `before/after` 分别复制完整审查及来源，因此删除原工程、原审查目录后，整个比较目录仍可独立复验。输入快照属于原工程数据，按其原始使用范围保管；公开 CI 只使用合成输入。

## 可以确认什么

| 范围 | 实际判定 | 保留边界 |
|---|---|---|
| 通信 | 复用已验收的 Com/EcuC/PduR/CanIf/Can 引用链与方向 | 不证明 CAN ID、布局、总线或运行行为 |
| 应用与组合 | RteSwComponentInstance → 显式 SW-COMPONENT-PROTOTYPE → TYPE-TREF；检查其所在组合 | 仅显式提供的平面实例关联；不自动完成多层 ECU Extract、连接器、实例引用解释 |
| ASW/BSW 调度绑定 | 事件引用 → runnable/schedulable entity → OsTask；保留可选 OsEvent/Alarm/ExpiryPoint 引用；检查应用事件归属 | 绑定存在不等于周期、激活次数、优先级、WCET 或可调度性正确；未记录绑定是证据缺口，不擅自称厂商非法配置 |
| 模式管理 | BswM rule → expression/condition 与 action list/item；缺引用、错误类型、条件及依赖环 | 不执行表达式、不仿真模式状态、不验证厂商动作副作用；环标记为待检查，不自动断言运行死循环 |
| 工具观察 | 原日志字节、逐行等级/代码/消息及精确对象路径关联 | 全部 historical-unbound；不作为当前配置失败或根因证明 |
| 两版影响 | 完整对象身份下参数/引用/类型/增删变化，经两侧显式依赖反向传播，并定位通信路径/任务映射/模式规则 | 未知字段、未解析依赖、选择范围改变明确保留，不能据“未找到路径”证明无影响 |

这些能力使用独立 `ecuc-engineering-review-0.1` 和 `ecuc-configuration-impact-0.1` 契约。旧 ECUC 体检/通信报告以及 P22 SWC ARXML 契约保持原边界。

## 工具日志的有限格式

本入口支持 UTF-8 文本观察行：

```text
ERROR CODE [/Absolute/Object/Path] historical message
WARNING CODE [/Absolute/Object/Path] historical message
INFO CODE [/Absolute/Object/Path] historical message
```

其余非空行作为 UNPARSED 原样保留。路径仅做精确关联，零匹配为 unassessed，多匹配为 ambiguous。不据短名、文本相似性或 ERROR 字样猜测对象和当前状态。这是有限文本适配，不是完整 DaVinci 日志解析器；没有原工具版本、输入绑定和实际执行证据时，不声称恢复了商业工具校验。公开 fixture 的日志明确是测试数据。

## 比较如何解释

`changes` 保存每个稳定对象 ID 的 before/after 参数、引用和源定位。ID 使用 `ecuc:` / `application:` 加完整 AUTOSAR 路径；重复身份时返回 not-comparable，不按数组位置凑配。

`affected_objects` 为每个受影响对象保存一个确定性的最短依赖见证：变化起点、before/after 快照和 `dependency_edges`。这些边在对应审查报告的 `integration.dependencies` 中可逐项核对。通信路径的成员关联则指向对应 `communication.paths` 索引；它表示需要重新检查该路径，不声称已发生运行故障。

格式化空白不构成配置变化。未知 XML 内容/属性/混合文本变化、未知类型及读取范围变化保留为 `unassessed_changes`。日志变化单列 `historical_logs_changed`，不会混进配置变更或“回归失败”。未解析依赖数量在两侧分别记录；范围内无变化不等于全工程等价。

## 状态与退出码

| 入口 | 退出 0 | 退出 2 | 退出 1 |
|---|---|---|---|
| review-ecuc-project | no-issues-in-scope | attention-required（含范围缺口） | 输入/环境错误 |
| compare-ecuc-reviews | unchanged-in-scope / changed-in-scope | partial / not-comparable | 来源复验失败、输入错误 |
| 两个 verify | passed：可信复现，包括原结论有缺口 | 不使用 | 来源/结论/库存/HTML 改变或不合法 |

输入沿用 UTF-8、r4.0 namespace、64 MiB 单文件/256 MiB 总输入上限；最多 100000 个对象，单条模式规则最多遍历 10000 个对象。输出必须为空或不存在，审查输出在源工程目录外，比较输出与输入审查不重叠。禁止快照符号链接；所有展示文本转义。

## 验证与独立练习

```bash
python scripts/run_ecuc_engineering_scenarios.py --output output/ecuc-engineering
python scripts/check_installed_ecuc.py --output output/installed-ecuc
```

十组完整 CLI 流程覆盖正常、信号/PDU/任务/周期/模式改变、缺失任务、重复身份、未知 XML 和历史日志改变；十份迁移复验、结论/来源/HTML/库存四类篡改拒绝。安装检查在仓库外创建无项目依赖的 venv，以 `--no-deps --no-index` 安装本地 wheel，排除 checkout import，再运行相同流程并复验迁移副本。

独立练习见[学习材料](../learning/p26-engineering-review.md)。平台自动回归不等于操作者掌握，也不替代 P25 人工演示或真实外部反馈。

## 固定词汇来源

实现参考 AUTOSAR CP R24-11 的有限字段，不把厂商输入自动声明为该版本合规：

- [RTE 规范](https://www.autosar.org/fileadmin/standards/R24-11/CP/AUTOSAR_CP_SWS_RTE.pdf)：8.5 的组件实例/类型关系、RteEventRef、RteMappedToTaskRef 及 BSW 对应引用。当前仅检查记录的结构关系，不执行全部生成约束。
- [BswM 规范](https://www.autosar.org/fileadmin/standards/R24-11/CP/AUTOSAR_CP_SWS_BSWModeManager.pdf)：BswMRule 的表达式及 True/False action list 引用。
- [模式管理指南](https://www.autosar.org/fileadmin/standards/R24-11/CP/AUTOSAR_CP_EXP_ModeManagementGuide.pdf)：规则、条件和动作列表的配置关系示例。
- 通信字段来源沿用[通信链指南](p26-ecuc-communication-guide.md)。
