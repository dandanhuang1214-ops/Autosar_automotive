# DaVinci 显式信号映射只读接入

`audit-signal-mappings` 消费 AUTOSAR 4 ARXML 中显式的 `SENDER-RECEIVER-TO-SIGNAL-MAPPING`。输入可以是 Developer 导出的 ECUProject ARXML，再加上定义数据元素的 PortInterface ARXML。每份输入记录路径、字节数和 SHA-256；每条映射输出端口、数据元素、SystemSignal 的完整引用、由端口类型确定的 Rx/Tx 和未解析引用。零映射及悬空引用返回 `attention-required`（退出码 2）。

```sh
workbench audit-signal-mappings --source exported-ecu-project.arxml \
  --source port-interfaces.arxml --output mapping-audit.json
```

这项检查证明输入文件内的三类对象引用可解析，并不证明 COM/PduR/CanIf 配置、DBC 导入、任务映射、CFG 生成或 CAN 总线运行。供应商 CFG 的原生校验结果应单独保存，与本报告并列审查。运行时只读，不调用商业工具或修改工程；工具导出应先在隔离副本上完成。公开回归使用合成 ARXML，不包含本地商业工程和 SIP。

七周实操计划与平台的接点：先用 Developer 导出验证现有 Rx/Tx data mapping；随后在 CFG 配置 COM/PduR/CanIf 时使用既有 ECUC 审查和通信 trace；Week 6 的候选建议只能引用本审计的已解析映射，Week 7 的写回仍需在隔离工程执行并由 CFG 重新校验。当前基础设施不把学习练习完成情况当成配置链已验收。计划标称每周 18 小时，若连续两周执行则为 36 小时，超过路线图原每两周总计 20–30 小时预算；应在实际排期中明确新预算或减少并行平台工作。计划中的测试 DBC 是经典 CAN 8 字节帧，CAN FD 仍需另备样本与配置证据。
