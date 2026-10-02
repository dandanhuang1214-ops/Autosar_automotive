# P28 对象级配置保护策略

项目 0.7 在 P27 静态检查上增加精确对象保护。旧 0.1–0.6 项目继续使用原契约。

```bash
python -m automotive_workbench.cli run-project examples/ecuc_acceptance/integration.protected.project.json --output output/protected-integration
python -m automotive_workbench.cli run-project examples/ecuc_acceptance/transmitter.protected.project.json --output output/protected-transmitter
python -m automotive_workbench.cli verify-ecuc-project output/protected-integration/bundle/project-report.json
python -m automotive_workbench.cli run-project-review output/protected-integration/bundle/project-report.json --output output/protected-review
```

打开 `bundle/index.html` 查看每项接受状态；`bundle/ecuc-stage.json` 的 `checks.policy.*` 保存实际值、对象/字段/依赖见证指针。指针相对于 observation 中的 `path`，可继续定位到快照源文件及 XML XPath。项目来源清单绑定前后报告、原输入、策略及阶段报告的 SHA-256；复验从快照重算，不接受仅修改结论并重新计算哈希的结果。

## 声明方法

从原 0.6 项目复制，设 `schema_version` 为 `workbench-project-0.7`，增加 `policies`，并为每条策略增加必须通过的 requirement：

```json
{
  "policies": [
    {
      "id": "SIGNAL_SIZE",
      "object_id": "ecuc:/Demo/Com/ValueA",
      "condition": "unchanged",
      "field_group": "parameters",
      "definition": "/Synthetic/ComSignal/ComBitSize"
    }
  ],
  "requirements": [
    {
      "id": "SIGNAL_SIZE",
      "text": "信号位宽不得变化",
      "stage": "ecuc",
      "pointer": "/checks/policy.SIGNAL_SIZE/status",
      "expected": "passed"
    }
  ]
}
```

以上为字段片段；完整可运行声明见两个 `*.protected.project.json`。所有策略必须被 requirement 引用，不能写入保护要求却不参与接受判定。全局 communication/impact 等检查仍可同时声明。

| 条件 | 范围与含义 |
|---|---|
| `exists_complete` | 前后两侧都必须存在唯一对象并具备受支持的结构见证。支持 ComSignal/ComGroupSignal/ComIPdu 的通信路径、ASW/BSW 任务映射、BswMRule 结构；不会用孤立对象存在代替完整链路 |
| `unchanged` + `parameters` | 精确完整 definition 必须唯一存在；受 P26 已建模字段词汇限制，比较解析后字符串值，不做单位换算或数值等价归一化 |
| `unchanged` + `references` | 精确完整 definition 的目标必须唯一存在且前后相同；保留引用依赖见证。切换到另一个有效任务也会被保护策略拒绝 |

允许变化由预先选定的保护范围表达：只保护信号结构时，可接受其已建模位宽变化；再声明位宽不可变则拒绝。未声明字段不等于获得全工程安全结论。未知源结构/读取范围变化、不完整依赖仍使本轮策略无法通过，即使未知发生在保护对象外；当前采用保守范围，不推断未知部分无影响。

策略数组的规范化哈希进入 `comparison_basis`。改变目标、条件、字段或策略顺序后，两次项目结果为 `not-comparable`；不能通过移除保护把回归包装成同策略通过。基线来源改变同样不可比较。使用相同保护声明与相同基线，可正常比较候选变更。

## 状态和边界

- 缺对象/字段、悬空目标、结构缺口、受保护值变化：failed。
- 对象、字段或引用目标不唯一：blocked。
- 未支持结构/字段、变体条件、缺应用覆盖、不透明或范围变化：unassessed。
- 声明格式错误、模糊身份、重复策略 ID、未参与接受的策略：执行前拒绝。

四状态均有来源；只有 passed 接受。项目聚合沿用 P27 的 failed → blocked → unassessed 优先级，逐项状态不丢失。结构完整仅指 P26 受限静态引用链，不证明布局有效、实时可调度、厂商生成或物理 ECU 行为。全部公开输入为合成示例。

## 可重放场景和安装验收

```bash
python scripts/run_ecuc_acceptance_scenarios.py --object-policies --output output/p28-scenarios
python scripts/check_installed_ecuc.py --object-policies --output output/p28-installed
```

16 场景覆盖两个工程、信号/任务拒绝、两工程允许变化、缺口、未知、缺对象、歧义和策略漂移；删除原输入后迁移复验与审查，比较信号/任务回归及策略改变，四类篡改拒绝，并再次搬移整树复验。安装脚本离线构建 wheel，在仓库外无依赖 venv 中执行同一流程并排除 checkout import。输出目录必须不存在。
