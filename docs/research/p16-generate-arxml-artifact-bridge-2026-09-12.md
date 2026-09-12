# P16 实际 Generate-Arxml 导出桥接

## 平台目标

P15 已提供项目入口，但 canonical 来源仍为手写 fixture。P16 使用真实 Generate-Arxml 导出，并把上游校验结果纳入工作流：文档生成成功不等于 DBC 集成成功，上游拒绝交付也不能被后续映射通过掩盖。

## 实施依据与来源

本次依据本地 Generate-Arxml 固定提交的实际代码，而非推测第三方接口：

- 仓库：`/mnt/d/work/SOA/code`；提交 `e912e404d52e671c7561d518d9989af3382fce51`。
- `scripts/docx_to_contract.py`：定义 `--input/--contract/--excel/--report-json` 导出入口；未关闭 OpenIssue、模型验证错误或 CORE ERROR 导致退出 1。
- `src/arxml_codegen/contract/docx_loader.py`：定义 SignalName/Resolution/InitValue 等字段提取。
- `src/arxml_codegen/contract/gap_report.py`：定义 items、counts、validation_errors 和 core_summary。

源仓库存在多项未提交改动，故通过 git archive 在隔离目录运行固定提交，生产者依赖安装到独立临时虚拟环境；未修改原仓库。公开 DOCX 由本平台编写，两份导出 JSON 不经手工改写进入 consumer。工作台核心无需增加 DOCX/Excel 库。

## 变更

- `workbench-project-0.2` 新增 generation 声明：生产者、revision、退出码、DOCX/issue report 路径及三份来源哈希。0.1 继续兼容。
- `generation_gate.py` 验证三份原始字节、gap report 结构与计数，保留完整 findings，并结合上游退出码、open issues、模型错误和 CORE ERROR 决定 generation 状态。
- `project-acceptance-0.2` 增加 generation 阶段；HTML 提供各阶段报告链接。静态映射仍执行以收集信息，但任一阶段失败都阻止通信实验。
- DOCX、原始 gap report、contract、revision 声明与阶段报告全部进入本次输入快照与现有 evidence 依赖图。
- 新增公开源文档生成器、固定提交重放脚本和三组实际导出样例。CI 消费已固定的导出，不安装或启动外部生成器；本地重放负责生产者链验证。

## 实际观察

| 案例 | 上游 | Workbench | 价值 |
|---|---|---|---|
| 正常 | 退出 0，保留 2 条 WARNING | 6 项声明验收通过，通信 passed | 实际导出可接现有工作流 |
| Resolution=2 | 退出 0，3 条 WARNING | canonical failed，通信 skipped | 跨工具一致性是额外验收条件 |
| 初值缺失 | 退出 1，1 条 OpenIssue | generation failed；canonical passed；通信 skipped | 上游失败不能被下游局部通过掩盖 |

分辨率变化产生上游 `CORE-010-PHYS-RANGE-CONSISTENCY` WARNING，以及 Workbench `MAP-NUMERIC-MISMATCH` ERROR；二者保留各自严重度和来源，不互相覆盖。

结果为真实工具处理公开合成输入的集成证据，不是客户数据、生成器整体质量、DaVinci 导入或量产 ECU 正确性的证明。原始表中 RequestedDirection 使用数值范围 0..3，本次未增加枚举语义校验。

## 验收与边界

测试覆盖三例、producer 退出 0 无法掩盖未闭合问题、三类来源哈希变化、非法声明、损坏 findings/summary/counts、原始 DOCX 确定性重建、输入快照迁移和篡改检出，以及 CLI 退出码。固定数据的元信息仅为本地声明，报告明确 `producer_identity_verified=false`。

操作说明与完整重放命令见 `examples/generate_arxml/bridge/README.md`。实测结果和远端状态以 `docs/project/progress-log.md` 为准。回退可继续使用 project 0.1；外部生成器始终与 Workbench 核心独立。
