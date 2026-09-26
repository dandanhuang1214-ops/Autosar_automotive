# 真实公开 SWC ARXML

`model.arxml` 是固定 Generate-Arxml 提交实际消费公开车窗 DOCX 后的原始输出，未修改 UUID 或 XML 格式。`provenance.json` 保存本地工具执行与输入/输出绑定；`golden.json` 固定五种离线场景的预期结果。

导入、比较、变体生成和生产者重放见 [P22 指南](../../../docs/project/p22-arxml-guide.md)。当前只验证有来源的结构语义与引用完整性，不证明完整 AUTOSAR XSD、ECUC 或 DaVinci 导入通过。
