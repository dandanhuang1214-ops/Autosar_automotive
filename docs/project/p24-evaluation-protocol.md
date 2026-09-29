# P24 分项评测与冻结制度

更新：2026-09-29。开发实现冻结于 `249a7307ef7b0db96c09c65a5187d5bd40f6e3f9`；随后负例登记提交 `6117b09e7ab80e7fdebca5a4654cdc4159f29a46`。首轮本地负例和从头生成来源后的完整重放通过；实现 `6117b09e7ab80e7fdebca5a4654cdc4159f29a46` / [run `36451604309`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36451604309) 七 job 全部 success；Windows/Ubuntu 开发场景、分项评测及证据上传均 success。

## 分项口径

- 目录检索：`search-engineering-questions` 使用英文词、中文双字词片段和 IDF 重叠评分，报告 top-1、hit@3 和无匹配。它只导航已有问题，不检索工程事实，不将相似文本当成断言支持，也不宣称模型语义理解。
- 确定性：既有六类 30 题保持原目录 hash 与 `engineering-review-0.1`。新增开发 gold 将“非空”增强为对象、路径、规则位置、未满足验收项及 XML 周期前后值等精确断言。
- 引用：重新加载来源、执行领域验证并重算答案；与检索排名单独计量。
- 严重度：对真实静态失败保留原始 Finding、`ERROR` 和引用；XML 源未给等级时保留缺失。对摘要降级、删除、伪造分别计量拒绝。当前实际等级覆盖为 ERROR 与未标级，不据此声称覆盖所有厂商等级系统。
- 条件差异：独立执行均为缺失合成构建的 blocked；单改构建提交或诊断 timeout，实际 CLI 项目比较必须为 not-comparable 并复验引用。它不证明一次新的 OpenBSW 现场运行。
- 模型：未运行，不计作零错误率。当前固定事实可由既有规则解释；故障唯一根因、未声明内部映射、生产认证等缺口仍缺执行证据，语言模型不能补造，因此本阶段不接模型。

## 冻结与后形成负例

1. 先完成开发代码、开发题和评分器的定向/全量检查，提交冻结实现。原 30 题目录仍为 `428427a19e16d60bf613ae51a3b1718cce553401ab4cfeee47d3fd90a2351fde`。
2. 在该提交之后才形成负例数据：记录父提交、UTC 形成时刻、全部运行源码及评测/生成脚本和开发 gold 的 SHA-256。首次执行前将具体 recipes、预期退出状态和检查项提交入 Git。
3. 评分器执行前要求冻结库存和哈希匹配；运行代码、检索、规则或评分器发生改变即拒绝继续沿用该冻结声明。负例不被用于修正排序、断言、预期值或通过阈值。
4. 若发现失败，保留首轮失败，明确转入开发修正，再在新冻结之后形成新的负例集；不能反复修改同一批 gold 直到全绿后仍称独立测试。
5. 明确区分输入完整性拒绝（退出 1，无新答案）与已验证来源上的越界结论拒答（退出 2，有范围引用）。对 verifier 负例和迁移后的原拒绝也分别保存证据。

“独立”仅表示数据在冻结后形成且未参与策略调优；本轮仍由同一维护过程编写，复用公开项目来源家族，**不是第三方盲测，也不是来自独立客户或物理 ECU 的样本**。实际结果只能支持列出的受限功能。

## 复跑入口

```bash
python -m automotive_workbench.cli search-engineering-questions "哪些验收项需要重跑" --limit 3
python -m automotive_workbench.cli search-engineering-questions "XML 引用错误" --input-version arxml-import-0.1
python scripts/run_engineering_review_scenarios.py --output output/engineering-review
python scripts/run_p24_assessment.py --development output/engineering-review --output output/p24-assessment
```

最后一条命令增加 `--held-out tests/fixtures/p24-held-out-0.1.json` 即运行冻结负例。总报告分别保存各分项分子、分母和明细；模型不参与判定。来源报告与答案不是单文件胶囊，迁移应保留相对目录关系。

## 首轮后形成负例记录

清单 SHA-256：`5c880470f931e0f103c9648b1cd34e0242f50574a4e386b6f893e1947f53df24`。154 个被测运行源码、脚本、开发 gold 和公开输入文件绑定于清单；具体形成 UTC 时间见清单。首次评测在登记提交之后进行，未根据结果修改清单、消费者、检索或评分器。

| 类型 | 新扰动 | 首轮本地结果 |
|---|---|---|
| 9 个完整性负例 | 删除依赖边、错误影响路径、掩盖原始 XML 周期、遗漏引用、重算库存后保留过期 timeout 摘要、遗漏构建角色、删除嵌套命令日志、遗漏筛选 Finding、错误筛选周期分类 | 9/9 拒绝；预期错误原因逐项匹配 |
| 3 个范围负例 | 生产者自称 ECUC 认证、工具标签自称物理量产认证、保存命令中的身份认证指令 | 3/3 拒答；元数据和命令始终作为数据，未执行 |
| 5 个目录查询 | 三个新短语、两个无匹配领域查询 | top-1/hit@3 3/3，无匹配 2/2 |
| 迁移 | 原目录改名后重验三类案例 | 12/12 保持拒绝/拒答结论 |

原始首次证据为 `output/p24-assessment-validation/held-out-first/` 与同级 `held-out-first-summary.json`。它们与既有开发样例分别计量，不能合并宣称语言模型准确率或外部用户效果。
