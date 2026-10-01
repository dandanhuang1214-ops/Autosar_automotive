# P27 声明式 ECUC 配置变更验收

`workbench-project-0.6` 将 P26 工程审查和两版配置影响接入 `run-project`。这是静态配置项目，不启动 CAN、生成器或 ECU；旧 0.1–0.5 项目保持原行为。当前远端状态见 [验收表](p27-acceptance.md)。

## 一次声明，完整运行

```bash
workbench run-project examples/ecuc_acceptance/integration.project.json --output output/ecuc-integration
workbench verify-ecuc-project output/ecuc-integration/bundle/project-report.json
workbench run-project-review output/ecuc-integration/bundle/project-report.json --output output/ecuc-review
workbench run-project examples/ecuc_acceptance/transmitter.project.json --output output/ecuc-transmitter
```

源码环境使用 `PYTHONPATH=src python -m automotive_workbench.cli` 替代 `workbench`；Windows 安装后直接使用同一 console script。输入使用 UTF-8，输出须为空或不存在。静态 0.6 不使用 `--interface`/`--channel`；这些参数仅影响旧通信项目。

两个公开合成工程分别包含：Tx/Rx、应用和 BSW 任务映射及 BswM；单 Tx、五个模块、无应用/任务/模式声明。第二个项目不改内核即可运行。输入不包含厂商/客户工程，不声称 AUTOSAR XSD 或商业生成验证。

项目文件示例：

```json
{
  "schema_version": "workbench-project-0.6",
  "name": "Telemetry static acceptance",
  "comparison_key": "telemetry-policy-v1",
  "inputs": {
    "baseline": {"project": "baseline/demo.dpa", "applications": [], "tool_logs": []},
    "candidate": {"project": "candidate/demo.dpa", "applications": [], "tool_logs": []}
  },
  "requirements": [
    {"id": "COMM", "text": "通信结构可定位", "stage": "ecuc", "pointer": "/checks/communication/status", "expected": "passed"},
    {"id": "IMPACT", "text": "变更在支持范围内可追踪", "stage": "ecuc", "pointer": "/checks/impact/status", "expected": "passed"}
  ]
}
```

路径相对项目文件；应用 ARXML 和历史日志须显式列出。未知字段、重复检查、重复 ID、不支持指针和将期望改为 `unassessed` 均在创建输出前拒绝。先读取并冻结两侧原字节，后续执行只消费快照；搬移复验不依赖原路径。

## 判定语义

| 检查 | 通过条件 | 未通过的含义 |
|---|---|---|
| `communication` | 有通信路径且 P26 链在支持范围内解析完成 | 无路径为 unassessed；结构引用缺口为 failed |
| `application` | 提供应用输入、存在实例关联且全部关联完整 | 没有覆盖为 unassessed；已检查关联存在缺口为 failed |
| `task_bindings` | 有显式应用输入和任务映射，事件/实体/任务关联完整 | 没有应用输入或映射覆盖为 unassessed；绑定缺口为 failed |
| `mode_rules` | 有模式规则且支持的引用/环检查完整 | 没有规则为 unassessed；结构缺口为 failed |
| `impact` | 两侧可比较、没有未知变化和未解析依赖 | 不可比较为 blocked；未知字段/范围或未解析依赖为 unassessed |

只聚合声明的检查，优先级 failed → blocked → unassessed → passed。未声明的检查仍显示结果，但不计入接受条件；精简通信项目通过不代表应用、调度或模式通过。通过 `impact` 只表示已追踪支持的变化，不表示“没有变化”或“变化安全”。历史工具日志只作独立观察，不改变当前验收。具体语义范围沿用 [P26 指南](p26-engineering-review-guide.md)。

CLI 退出码：passed 为 0；failed/unassessed 为 2；blocked 为 3；输入非法或完整性复验拒绝为 1。复验返回 passed 表示证据一致，另列 `project_status`；不能把它当工程接受。

## 证据与比较

输出包含 `bundle/project-report.json`、HTML、`ecuc-stage.json`、原项目声明，以及 `ecuc/` 中完整 before/after 快照、审查、影响 JSON/HTML；同时生成通用 `manifest.json` 和完整性验证。阶段报告给出每个检查的来源指针及受影响对象；更细的依赖见证在影响报告中。

```bash
workbench compare-projects output/accepted/bundle/project-report.json output/candidate/bundle/project-report.json --output output/ecuc-comparison
workbench verify-project-comparison output/ecuc-comparison/project-comparison.json
```

比较两个项目运行结果要求相同 `comparison_key`、引擎版本、基线审查 hash 和完整要求定义；改变策略/基线会得到 not-comparable。新比较输出版本 0.3 容纳 unassessed，旧比较版本保持原状态契约。

`run-project-review` 先重算原始快照、策略、阶段和项目，再引用状态、原因、证据路径/指针和每项前 100 个受影响对象；完整列表始终在 JSON。审查 answered 说明所述状态有证据，failed/unassessed 项目也可以被准确解释，不等同接受。审查/比较以相对路径引用项目，搬移时保留整个目录树。

复验会拒绝结论、策略、来源、HTML、库存或引擎结果不一致。它验证自包含证据的内部一致性，不提供数字签名或输入来源身份认证；完整重写所有输入和派生文件不属于可证明的篡改检测范围。

## 可重复验收

```bash
python scripts/run_ecuc_acceptance_scenarios.py --output output/ecuc-project-scenarios
python scripts/check_installed_ecuc.py --project-acceptance --output output/installed-ecuc-projects
```

覆盖两项目、任务/通信失败、未知范围、应用缺失、重复身份和历史日志；删除原输入、搬移、项目复验、审查、比较复验及四类拒绝。安装验证用仓库外隔离 venv、offline `--no-deps --no-index` wheel、导入位置核对和 pip check，再重复完整流程。安装包准备和全部命令/退出码归档，不能用源码执行代替安装后验证。
