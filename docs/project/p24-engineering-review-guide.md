# P24 固定工程问题审查

P24 固定问题与目录导航范围已 remote-accepted，见[验收记录](p24-acceptance.md)。30 题覆盖配置影响、通信图规则、ARXML、项目门控、外部 ECU 和来源范围，每类五题。开发题与冻结后负例分开计量；不是自然语言模型正确率。

## 使用

2026-09-29 新增 `search-engineering-questions` 目录检索与对象级/严重度分项评测，见[冻结与评测制度](p24-evaluation-protocol.md)。检索仅帮助选择固定问题，命中不代表工程结论成立；原 30 题目录与已有答案验证保持兼容。

在已安装开发依赖的环境运行；源码执行时设置 `PYTHONPATH=src`。

```bash
python -m automotive_workbench.cli list-engineering-questions
python -m automotive_workbench.cli compare-communication-config examples/thermal_control/project.json examples/thermal_control/project.json --output output/p24-stable
python -m automotive_workbench.cli review-engineering output/p24-stable/report.json --question impact-acceptance --output output/p24-stable-review
python -m automotive_workbench.cli verify-engineering-review output/p24-stable-review/engineering-review.json
python scripts/run_engineering_review_scenarios.py --output output/p24-development
```

输出目录须为空或不存在，且在来源报告目录之外，以免破坏原报告完整库存。固定问题 ID 明确选择工程任务；不接受自由文本指令改变断言或来源。旧 `run-project-review` 等入口和契约继续有效。

`engineering-review.json` 使用独立 `engineering-review-0.1` 契约，保存问题目录 hash、源版本/相对路径/SHA-256、每个结构化引用的 JSON Pointer、原始值及值 hash。Markdown 同时展示选中答案和完整引用。`answered` 表示准确读出已记录证据，不表示源项目通过。空诊断 `null` 保留为空，不填造响应；空 findings 仅表示未记录匹配规则，不表示工程没有缺陷。

`selected` 为规则码筛选、未通过验收项或 timing-event 变更；`facts` 保留原始被引用集合，避免筛选时丢掉上下文。比较不可用时保留原始 status/reason；不同源版本在输出前拒绝。超时唯一根因、内部 DBC 映射、量产 ECUC、物理 ECU 和身份认证等越界题返回 `refused`（CLI 退出 2），同时引用其范围证据。损坏、缺失或不适用来源为输入错误（退出 1），不生成看似有效的答案。

## 验证与范围

- 对象图/影响与 ARXML 从内嵌来源重算；项目 0.5 使用既有快照和静态/外部阶段复验；独立执行使用既有文件完整性及诊断绑定复验。全部离线，不执行 ECU 或保存的命令。
- 引用允许数组和对象，保留空集合、类型和原字段。布尔/数字严格区分，来源没有 severity 时不推造等级。结构化引用需要本入口的 verifier；旧 scalar review 引用接口未改变。
- 保存后 verifier 重新加载源、执行领域复验、重做固定问题与筛选，并严格比较整个答案。移动答案与其相对来源树后可复验；只有答案文件并不构成自包含胶囊。验证完整性不认证来源生产者身份。
- 开发评测由固定 JSON gold 独立指定预期状态和值，覆盖 30 个不同问题以及五个拒答。来源包括真实公开 XML 的合成故障变体、车窗/ThermalControl 图、合成缺失构建的项目 blocked 证据；不冒充新的现场 ECU 运行。
- 分项评测已增加对象级 gold、严重度保真、词法目录检索、条件比较及冻结后负例；具体计数和独立性范围见[评测制度](p24-evaluation-protocol.md)。语义检索与模型未运行。

## 技术跟进（2026-09-28）

[AUTOSAR 官方 Classic 页面](https://www.autosar.org/standards/classic-platform/) 当前列出 R25-11。本项目受限 XML 消费仍是已验证的 4.3.0，问题会引用实际输入版本；发布更新不自动扩大支持范围。Python 3.14 runtime-currency CI 继续保留。

[NIST AI 600-1](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf) 将生成式 AI 的 confabulation 列为风险。本轮据此采用可复算基线并单列未测试能力，是项目工程选择，不是声称符合 NIST 认证。下一步先冻结开发基线，再形成未参与规则调优的负例；仅在真实解释缺口明确时接可选模型，并单独计量增益与无证据断言。
