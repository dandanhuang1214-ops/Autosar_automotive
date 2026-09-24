# P22：受限 ARXML 与工具桥接

状态：planned，2026-09-24。按路线在 P21 完成远端冻结后开始；此文件是下一阶段入口，不是已实现能力。

## 用户结果

从真实、可公开的工具导出中导入一个明确受限的 ARXML 语义子集，保留对象身份、源 XML 定位、输入/工具版本和不支持语义；正常、悬空引用、语义变化三组输入能够离线比较，并在语义确实可映射时连接 P21 对象图。

## 从这里继续

1. 审计固定 Generate-Arxml producer 的实际 ARXML 输出、AUTOSAR namespace/version、导出参数与现有 P16 重放证据。当前仓库 `examples/generate_arxml/bridge/` 保存 DOCX、contract、issues、intent、DBC 和 project；并未因目录名称含 arxml 就证明已消费 ARXML XML 文件。
2. 根据实际产物固定第一版受支持元素、引用类别与版本；区分 SWC/interface、ECU Extract 和 ECUC。只有源文件真实包含的语义才能映射到 P21，缺失的 COM/PduR/CanIf 配置应输出 unknown，不能从 SWC 名称补造 BSW 对象。
3. 定义离线输入快照、XML locator、生产者提交/工具版本、未支持元素清单和版本化结果；拒绝悬空引用和版本不匹配，明确未支持但可保留的语义。
4. 使用真实导出建立正常 golden，再从该源显式构造悬空引用及语义变化负例；保存变更脚本、输入 hash 和预期差异。消费和比较不要求运行商业软件。
5. 接入项目工作流与公开重放，运行既有 P20/P21 兼容回归、Windows/Ubuntu 和 Python 3.14 七 job；以新实现提交/实际 run 冻结公开路径。
6. 另行探测合法可用的 DaVinci 安装、版本、许可及导入/回导能力。缺少环境时记录实际阻塞与恢复步骤；商业往返不以离线样例或在线说明替代。按路线完成公开路径后可带着明确的商业环境 blocked 推进 P23。

本阶段不实现通用 ECUC 编辑器，不增加硬件平台，不改变 P21 的 vendor-neutral 规则来源。远端实现证据与个人 AUTOSAR/工具学习掌握仍分别验收。
