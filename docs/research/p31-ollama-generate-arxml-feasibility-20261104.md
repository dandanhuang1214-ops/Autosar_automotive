# P31 自然语言候选到 Generate-Arxml 回读可行性（2026-11-04）

本轮只测试公开车窗样例的隔离生成链。**Ollama 输出受限 JSON 变更草案，ARXML 由固定版本 Generate-Arxml Python 生产者生成。** 两条模型草案均标为 `unreviewed_test_candidate`，没有代替用户审阅，也没有接入 AI 平台网页或 MCP 生产工具。

## 输入和执行环境

- 输入为 `examples/generate_arxml/bridge/baseline/source.docx`；文档有项目字段、Signal 表与 Runnable Access 表，使用 `--mode signal --profile signal_atomic_davinci`。
- 从本机 Generate-Arxml 仓库只读 `git archive` 固定提交 `e912e404d52e671c7561d518d9989af3382fce51`，解压到 Workbench 忽略的 `output/deliverables/p31-generate-arxml-feasibility/producer-pinned/`。源仓库已有未提交改动，本轮未修改它，也未在其工作区运行生产者。
- 使用生产者自带 Windows `.venv/Scripts/python.exe`，依赖导入检查通过。Workbench 在本机导入和重放 ARXML。模型为实际 Ollama `0.31.1` / `qwen3.5:2b`，digest `324d162be6ca5629ae4517c8710434d0bd2d665bc94dbad46e9af8fbf8a2f0df`。
- 原始 DOCX、contract、Excel、issues、ARXML、生成日志、语义比较和模型传输记录保存在 `output/deliverables/` 下的本地忽略目录，不随仓库公开提交。

## 固定生产者和回读基线

| 场景 | 生产者 | Workbench | 结论 |
|---|---|---|---|
| baseline DOCX | 退出 0；0 open issue、0 模型验证错误、0 CORE ERROR；输出 contract、Excel、issues 与 SWC ARXML | ARXML 导入 `passed`、`supported-subset`，0 finding/unsupported；保存报告重放 `passed`；对冻结 SWC 样例语义 `stable` | 现有真实生成与受限回读链可复用。新 ARXML 字节哈希不同，语义仍稳定。 |
| 缺初值 DOCX | 退出 1；1 open issue；没有 ARXML | P16 generation gate `failed`，阻断 finding 1 | 上游阻断不会被误记为生成成功。 |
| 产物来源哈希错误 | 原始 ARXML 保留 | Workbench 拒绝错误 provenance：`Producer provenance ARXML hash mismatch` | 生成物与声明来源必须绑定。 |

## 两条真实 Ollama 候选

| 自然语言要求 | Ollama 受限草案 | 固定生成器和回读结果 | 评价 |
|---|---|---|---|
| `WindowPosition` 数值型初值 `0→5` | 准确给出 `signal_name=WindowPosition, field=init_value, old_value=0, new_value=5` | contract 已变为 `5`，生产者仍退出 0 且 ARXML 导入 `passed`；生成 XML 的端口 `<V>` 保持 `0`，与基线语义 `stable` | **需求没有落入生成物，必须拒绝作为完成。** 固定生产者的 `excel_builder._signal_init_value` 对非布尔、非枚举信号返回常量 `"0"`；当前工作树对应函数也仍是这一行为。 |
| `WindowControl_Step` 周期 `10→20 ms` | 准确给出 `runnable_name=WindowControl_Step, field=period_ms, old_value=10, new_value=20` | 生产者退出 0，Workbench 导入与保存报告重放 `passed`；语义比较 `changed`，唯一变化对象为该 Timing Event，`PERIOD` 从 `0.01` 变为 `0.02` | 该字段存在可核实的模型草案→生成→回读链。 |

这两条公开样例只能证明模型在窄字段提示下提取成功一次，不能证明任意自然语言需求均可转成正确 contract。尤其不能凭生产者退出 0 或导入 `passed` 判定用户所提字段已落实；必须把**候选期望变更**与**回读对象和值**逐项比对。当前契约字段的原 DOCX `source_trace` 在模型补丁后不再单独证明新值来源，正式工具还需保存模型原文、用户审阅动作、原 DOCX/contract 哈希与变更记录。

## 接入结论与边界

下一版 AI 平台可接“自然语言→结构化草案→用户审阅→固定 Generate-Arxml 执行→Workbench 回读”。首批可开放已证实传播且有精确回读定位的字段，例如上述 Runnable 周期；数值型 signal 初值在生产者修复及新回读测试通过前应阻断。服务必须限制可选字段、生产者版本、输入根目录和输出目录，并分别呈现生产者、结构导入、期望变化回读三种状态。

本轮没有修改 Workbench 或 Generate-Arxml 实现，没有新的实现 CI，也没有在 DaVinci 中导入，更没有生成 ECUC、编译 RTE 或运行物理 ECU。P31 主实现任务仍是把这一受控链路接到 AI 平台和 MCP 服务，遵循上述字段门与来源绑定。
