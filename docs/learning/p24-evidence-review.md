# P24 个人复跑练习

平台实现和自动评测通过不代表已掌握以下能力，完成后另记个人记录。

1. 按 [P24 指南](../project/p24-engineering-review-guide.md)生成两份相同配置的影响报告，运行 `impact-acceptance`。说明为何重跑集合为空不能证明真实 ECU 无缺陷。
2. 在开发场景的 `graph/scale-impact/report.json` 中定位 `thermal-status`，沿 `affected` 的路径回到变化对象，再定位源 DBC。区分源字节变化、对象语义变化和实际运行结果。
3. 用 `arxml-version` 查看版本和 coverage。解释为何官方 R25-11 发布不表示本平台已验证 R25-11 XML，也不表示 SWC XML 含 ECUC 配置。
4. 比较 `project-gates` 与 `ecu-diagnostic`：一个是静态失败跳过运行，另一个可能是缺失构建导致 blocked。区分 skipped、blocked、timeout 和 negative_response。
5. 对副本修改一项回答值后运行 `verify-engineering-review`，记录拒绝。恢复答案、只改变源文件格式后再验证，解释为何字节 hash 仍会变化。
6. 解释 30 题开发集、独立未参与调优负例、固定 JSON Pointer 查询与自然语言检索的差别。当前模型指标为未运行，不是零错误率。

每次记录命令、来源版本/hash、实际输出和自己的解释；不要把平台生成的结论直接作为个人学习验收。
