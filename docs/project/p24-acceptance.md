# P24 工程问题审查验收

更新：2026-09-29。P24 固定问题与目录导航范围 **remote-accepted**。实现 `6117b09e7ab80e7fdebca5a4654cdc4159f29a46` / [run `36451604309`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36451604309) 七 job 全部 success；Windows/Ubuntu 开发场景、分项评测及证据上传均 success。

| 门 | 实际证据 | 状态 |
|---|---|---|
| 至少 30 个不同工程问题 | 六类各五题；对象、路径、规则位置及周期前后值精确 gold 30/30 | 通过 |
| P21/P22/P23 消费与来源复验 | 图/影响、XML、项目 0.5、独立执行；引用重算 30/30，原契约兼容 | 通过 |
| 目录检索单独计量 | 开发 top-1 与 hit@3 各 17/17、无匹配 1/1；冻结后各 3/3、无匹配 2/2 | 通过 |
| 严重度保真 | 原始 ERROR 与未标级 2/2；摘要降级、删除、伪造拒绝 3/3 | 通过 |
| 条件差异解释 | 改变构建提交或诊断 timeout 后比较均 not-comparable，引用有效，2/2 | 通过 |
| 未参与调优的冻结后负例 | 完整性拒绝 9/9、越界拒答 3/3、迁移重放 12/12 | 通过 |
| 本轮七 job CI | 6117b09 / 36451604309，双平台评测和上传成功 | remote-accepted |

开发策略冻结提交 `249a7307ef7b0db96c09c65a5187d5bd40f6e3f9` 在先，负例登记提交 `6117b09` 在后，首次执行前已入 Git；冻结库存绑定 154 个文件。负例首次执行后未修改消费者、排序、评分器、gold 或阈值。负例与开发共享公开来源家族、由同一维护者形成，独立性限定为未用于调优，**不是第三方盲测或独立客户样本**。方法与 hash 见[评测制度](p24-evaluation-protocol.md)。

本地全量 303 tests：301 passed、2 environment skips；47 schema、61 schema-bound examples、25 syntax-only examples、Ruff、36 文件 mypy、Windows-target 新入口检查、topology、pip check 和 whitespace 通过。从头生成来源后的完整重放 `output/p24-assessment-release/assessment/summary.json` 为 passed；实际远端记录保存在 `output/p24-assessment-validation/remote-ci.json`。

目录检索仅导航固定问题，不代表语义证据检索；模型未运行。条件比较使用合成缺失构建的 blocked 项目，没有新增现场 ECU 运行。完整性验证不认证生产者身份；严重度未覆盖所有厂商等级。原首批基线 `92bf90a` / run `36415173355` 保留为历史，不替代本轮验收。

下一主阶段为 [P25 可复现交付](p25-reproducible-delivery-plan.md)：先验证隔离安装后的 CLI 能在仓库外完成两个项目与配置故障流程。后续状态文档提交使用 `[skip ci]`，不作为实现验收提交。
