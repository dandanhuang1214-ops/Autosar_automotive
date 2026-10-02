# P28 对象级配置变更验收

更新：2026-10-02。remote-accepted；按受限静态对象保护范围冻结，下一主阶段 P29 planned。

| 阶段门 | 实现及证据 |
|---|---|
| 精确版本契约 | 项目/报告 0.7，阶段 0.2；原 0.1–0.6 保持；策略独立哈希防止伪装同策略比较 |
| 对象与不可变条件 | 前后对象结构、参数/引用精确定义，实际值和两侧源指针；缺失/歧义/未知不通过 |
| 两个工程 | 完整 Tx/Rx/应用/任务/模式工程与精简单 Tx 工程，固定保护范围的允许/拒绝变更 |
| 审查与交付 | 对象/字段/依赖指针和标量审查断言；原输入删除、两次搬移、回归与策略漂移比较、四类篡改拒绝 |
| 本地自动检查 | 374 tests：372 passed、2 环境跳过；15 项对象策略专项；52 schema、65 bound/25 syntax-only、50-source mypy、Ruff、topology、compileall、pip check 通过 |
| 隔离安装 | 最终源码与隔离 wheel 各 16 场景、16 迁移复验/审查、4 篡改拒绝、通信/信号/任务回归与策略漂移比较、二次搬移通过；源码额外搬移后 38/38 比较引用有效 |
| Windows/Ubuntu | 实现 `2269714e6895f6e1d3c2b7276e034b61262ea33b` / [run `37025748404`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37025748404) 七 job 全部 success；两平台对象策略场景、隔离安装和证据上传均 success |

指南：[对象策略运行与边界](p28-object-policy-guide.md)。证据目录 `output/p28-validation/`。本次没有运行厂商工具、商业往返或物理 ECU；P25 人工演示及外部反馈继续等待实际证据。

最终证据：`output/p28-validation/scenarios-final/summary.json`、`installed-final/summary.json`、`tests-release.log`。开发中非法版本列表分流异常、场景退出码预期及大小写策略审查编号冲突均已修复，最终固定代码重跑通过。

远端原始记录 `output/p28-validation/remote-ci.json`；双平台归档为 `ecuc-policies-Windows` / `ecuc-policies-Linux`。本条验收回填属于随后纯文档 `[skip ci]` 提交，不计作新实现验收。下一项为[P29 显式配置与运行证据绑定](p29-configuration-runtime-plan.md)。
