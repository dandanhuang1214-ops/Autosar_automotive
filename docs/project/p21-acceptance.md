# P21 验收记录

日期：2026-09-24。当前为 **remote-accepted，完成并冻结**；依据本轮实现 `79d1f3b` 与 [run `36022099415`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36022099415)，不引用 P20 的 run 替代。

| 阶段门 | 本轮证据 | 状态 |
|---|---|---|
| 两项目、Tx/Rx、稳定对象身份 | 车窗 8 对象；ThermalControl 14 对象，共享 route 保留两个来源；源字节 SHA-256 和 locator | 本地通过 |
| 六类规则正负例与依据 | [规则覆盖表](p21-communication-graph-guide.md)、13 组测试、公开 CLI 正常及五类失败 | 本地通过 |
| 两版配置 → 对象 → 验收项 | ThermalStatus scale 变化传播至四类对象及 thermal-status；未影响 pump-status/cooling-request；保留路径与来源变化 | 本地通过 |
| 未知/不支持/不可比较 | 图失败或 scope 不同拒绝比较；不支持 DBC 语义拒绝；contract、generation、无向量覆盖明确 unknown | 本地通过 |
| 迁移及完整性 | 内嵌五来源快照，删除生成的原候选目录后独立 CLI replay；篡改对象、结论、哈希均拒绝 | 本地通过 |
| 历史兼容 | 原 project/review/compare/runtime 契约保持；全量回归含安装后 wheel/capsule consumer | 本地通过 |
| Windows/Ubuntu/Python 3.14 | 七 job；两平台独立 CLI 场景及 communication-graph artifact 已接入 | 远端通过 |

本地场景入口：`python scripts/run_communication_graph_scenarios.py --output output/p21-demo`。最终证据记录于 `output/p21-validation/tests-final/` 与 `output/p21-validation/scenarios-final/`。P21 为静态依赖分析，不新增总线执行；既有 P20 现场记录仍是 P20 的证据，不能称作本次新现场测试。

边界：vendor-neutral intent 0.2，不验证 AUTOSAR release、vendor ECUC、硬件或实际软件调用。传播采用新旧依赖图并集的保守闭包，不做重命名推断或运行结果预测。报告 snapshot replay 验证内部一致性，不提供身份认证。用户个人 BSW 学习掌握另行验收。

远端通过后推进 P22 受限 ARXML 元素与版本、来源和不支持语义契约；商业工具往返只有真实执行证据才能接受。

本地最终质量门：245 tests（243 passed、2 environment skips），38 schema、58 schema-bound examples、23 syntax-only examples，Ruff、22 文件 mypy、CI topology、pip check、whitespace 通过。10 个公开 CLI 场景及迁移独立 replay 全通过。

## 远端冻结

实现提交：`79d1f3bba43fa7f9dbf85e5965741d50e10e4bdd`。[run `36022099415`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36022099415) completed/success，七个 job 全部 success：Windows/Ubuntu core-contracts、runtime-evidence、controlled-rejections，以及 Python 3.14 runtime-currency。

两平台的 `Run communication graph scenarios` / `Upload communication graph evidence` 均 completed/success，产物为 `communication-graph-Windows` / `communication-graph-Linux`。实现验收绑定此固定提交；随后纯文档 `[skip ci]` 状态提交不算新实现验证。下一主阶段为 [P22 ARXML 桥接](p22-arxml-bridge-plan.md)。
