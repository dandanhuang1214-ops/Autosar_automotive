# ECUC 项目结构体检

该入口读取 DPA 的 `EcucSplitter/Configuration`、`Splitter File` 和唯一 ECUC value collection。它按绝对 AUTOSAR 对象路径选择模块，忽略未选择模块的容器检查。不会递归扫描整个工程目录，也不会自动加入 initial/workflow 副本；若 DPA 显式声明这些文件，则按声明加载并检查，不自行改写项目选择。

```bash
workbench inspect-ecuc-project /path/to/project.dpa --output output/ecuc-inspection
workbench verify-ecuc-inspection output/ecuc-inspection/ecuc-inspection.json
```

源码环境可用 `PYTHONPATH=src python -m automotive_workbench.cli` 替换 `workbench`。Windows DPA 内的相对反斜杠路径会按项目根解析。源工程不被修改；输出必须为空或不存在，并位于 DPA 所在目录之外。

报告和快照可能包含原工程内容，应按输入数据的使用范围保管；CI 仅使用公开合成工程。

## 输出与退出码

- `ecuc-inspection.json`：选定模块、未选模块路径、容器类型计数、引用分项、发现及 file/xpath/object_path 定位。
- `snapshot/`：DPA、collection 和显式 splitter 文件的原字节；报告绑定大小和 SHA-256。
- 体检退出 0：`no-issues-in-scope`；退出 2：`attention-required`；输入错误退出 1。
- 复验退出 0：从快照重新计算整个报告一致，结果 `passed`；来源缺失、内容或结论篡改、非法库存退出 1。原体检有 WARNING 时，复验仍可以 passed，表示报告可信重现，不表示问题已修复。

将整个输出目录移动到其他位置后可以复验，原项目无需在场。复验检查所有快照文件、来源 hash 和全部结论；不能只携带单个报告 JSON。完整性复验不认证来源身份。

## 首轮检查

| 代码 | 含义 |
|---|---|
| ECUC-MODULE-SELECTION | value collection 选定路径有零个或多个模块定义 |
| ECUC-DUPLICATE-SELECTION | collection 重复选择同一路径 |
| ECUC-AMBIGUOUS-PATH | 已选模块中同一完整对象路径多次定义 |
| ECUC-MISSING-REFERENCE | 指向选定模块范围的普通 VALUE-REF 找不到对象 |
| ECUC-TASK-UNBOUND | RTE/BSW event mapping 未记录非空 mapped-to-task 引用 |

不同命名空间路径下相同 SHORT-NAME 不会被直接视为重复。普通引用可分为 resolved、ambiguous、missing_selected_object、empty、unassessed；外部定义/系统行为和实例引用不因当前未读取而误报为已确认缺失。

XML 定位采用命名空间局部标签与同标签兄弟序号，例如 `/AUTOSAR[1]/AR-PACKAGES[1]/AR-PACKAGE[1]/...`；结合报告记录的 r4.0 输入 namespace 定位，不是省略命名空间即可直接交给任意 XPath 引擎执行。

本入口不验证 schemaLocation 对应的厂商 XSD，不验证生成参数范围，不生成 ECUC、不修复原工程、不执行工具。任务引用存在也不证明调度周期与任务类型正确；这些属于后续集成检查。

公开场景：

```bash
python scripts/run_ecuc_project_scenarios.py --output output/ecuc-scenarios
```

四组场景覆盖正常、未绑定、断引用和歧义；移走原目录并删除输入副本后复验四组报告，再验证篡改拒绝。本轮路线见[P26 计划](p26-ecuc-inspection-plan.md)。
