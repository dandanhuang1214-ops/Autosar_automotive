# P22 公开路径验收

更新：2026-09-27。当前项目接入 local-accepted；实现提交与远端 run 待回填。离线底座 `6166b80` / run `36235450078` remote-accepted 保持；本轮尚不继承其远端结论。

| 阶段门 | 本轮证据 | 状态 |
|---|---|---|
| 实际公开导出、固定 AUTOSAR 子集、来源与未知边界 | 固定 producer `e912e404`，XML/provenance/golden；既有导入与重放 | remote-accepted（前轮） |
| 版本化项目快照与静态门控 | project/report 0.4；ARXML 失败/partial 均阻止通信；旧 0.1–0.3 兼容 | 本地通过 |
| 正常/悬空/周期变化及额外未知语义 | 四个 CLI 案例；周期只改变 timing event，合成输入明确标注 | 本地通过 |
| 审查、比较、来源篡改与迁移 | 删除原输入后 4/4 manifest、citations、重审、comparison、XML 重放；篡改测试拒绝 | 本地通过 |
| Windows/Ubuntu + Python 3.14 七 job | 已接入 ARXML project 场景/上传及 topology guard | 待远端 |
| 商业导入/回导 | 有限安装探测未找到入口，未执行许可查询和导入 | blocked |

本地证据目录：`output/p22-project-validation/`，公开场景 `release-scenarios/`，测试摘要 `tests-final/ci-test-summary.json`，有限商业探测 `commercial-probe.json`。最终全量 262 tests：260 passed、2 environment skips；41 schema、59 schema-bound examples、25 syntax-only examples、Ruff、27 文件 mypy、CI topology、pip check 与 whitespace gate 通过。这些生成物不提交，双平台执行产物通过 CI 独立上传。

2026-09-27 商业探测仅检查 PATH 中 `dvcfg-b` / `DaVinciConfigurator` / `DaVinciConfigurator.exe`，以及 `/mnt/c/Program Files`、`/mnt/c/Program Files (x86)` 下含 Vector/DaVinci 的一级目录和 `/mnt/c/Vector`。均无匹配；不据此认定整台机器不存在安装或许可。恢复需提供实际安装位置、版本、合法许可和可公开导入工程，执行真实导入/回导并保留命令、日志、输出及 hash。

边界：受限结构/引用检查，不验证完整 XSD、ECU Extract、ECUC 或商业工具往返；XML 与 DBC/intent 独立验收，未知跨源映射保留。项目 virtual 通信不构成独立 ECU 或物理总线证据。按路线，在本轮公开路径远端验收后保留商业 blocked，推进 P23 独立 ECU 项目执行；个人学习掌握单独验收。
