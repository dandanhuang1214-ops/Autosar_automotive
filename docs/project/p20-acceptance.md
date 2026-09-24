# P20 整阶段验收记录

日期：2026-09-24。范围：声明驱动的多项目通信验证，包含 P20a–d。当前整阶段状态为 **remote-accepted，完成并冻结**。此前 P20a/P20b 的 run 不代替本次项目集成实现的 CI。

| 阶段门 | 实际证据 | 当前结论 |
|---|---|---|
| 两个结构不同项目共用引擎 | 车窗两报文/两条映射路径；ThermalControl 三报文、4/2/3 字节、缩放/偏移、五条映射路径；project 0.3 只改声明输入 | 本地通过 |
| 开总线前拒绝 | P20a/b 预检及新增项目无副作用负例；非法向量/缺失路径/重复映射身份在运行输出前拒绝 | 本地通过 |
| 静态门控与实际运行失败 | canonical resolution 改为 2 后 communication skipped；合法输入下真实 virtual 发送抑制引发超时、失败路径及审查引用 | 本地通过 |
| 项目/review/compare | 六案例、稳定/两类回归/两类不可比较；0.3 快照来源校验、严格定义比较 | 本地通过 |
| 整包迁移 | 原目录移动后已不存在；六项目 manifest/citations/重新审查和五份 comparison 独立复验 | 本地通过 |
| 兼容性 | 旧 project 0.1/0.2、comparison 0.1、P15–P19、隔离 wheel 与 capsule consumer；另测 0.3 可选 generation | 本地通过 |
| Linux SocketCAN 现场 | 两项目在 vcan0 通道锁下完整 run-project/review/compare/verify；2/2 与 3/3 向量通过 | 本地通过 |
| Windows/Ubuntu/Python 3.14 | 实现提交 `31ca4ef` 的七 job 与两平台 multi-project-release artifact | 远端通过 |

公开重放入口：`python scripts/run_multi_project_scenarios.py --output output/p20-release`，页面 `output/p20-release/portable/index.html`。输入全部为公开合成数据；现场及运行故障都不代表商业工具或物理 ECU 验证。

SocketCAN 现场入口：`bash scripts/linux/run_socketcan_projects.sh vcan0 output/p20-final-validation/socketcan .venv/bin/python`。实际使用 python-can 4.6.1、cantools 44.0.0，接口 vcan0 已存在；两项目 runtime 均记录 `held_by_entrypoint`。两份项目报告 SHA-256：

- 车窗：`29774f3d1b9522644f943547d1ca5f50ac226a08f2dcdabac9bbb96e1d6377cc`
- ThermalControl：`60cf42a94003ac197bbea058df621c58eda8fffda161c2f20e55c4e1aab5b438`

该现场证据只证明 Linux SocketCAN/vcan、同进程两端点及项目编排。远端 CI 单独运行 virtual，不能替代这份现场结果。固定 hash 用于定位本次本地 artifact，不保证别人重跑产生相同含时间字段的报告字节。

契约边界：project/report 0.3 显式版本化；涉及新报告的 comparison 0.2 核对 comparison_key、local_ecu、完整向量和验收定义。旧版报告仍使用旧比较语义。新绑定报告只绑定 intent 明确声明的路径，不声称生成或验证真实 COM/PduR/CanIf ECUC。

通过整阶段后主线转入 P21：先建立具有独立身份的通信对象图，再实现有来源、正负例和未知边界的变更影响分析。不能把本阶段的结果比较称为已经完成配置影响追踪。

本地质量门：232 tests（230 passed、2 environment skips）；36 schema、58 schema-bound example、23 syntax-only example；Ruff、20 文件 mypy、CI topology、pip check、shell syntax、文档链接和 whitespace 通过。测试摘要：`output/p20-final-validation/tests-final/ci-test-summary.json`。

## 远端冻结

实现提交：`31ca4ef80ee9ff9c7147d964d805d73a5026798c`。

[GitHub Actions run `35979820300`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/35979820300) completed/success。Windows/Ubuntu 的 core-contracts、runtime-evidence、controlled-rejections，以及 Python 3.14 runtime-currency，七个 job 全部 success。两平台 `Run multi-project release scenarios` 和 `Upload multi-project release evidence` 均 completed/success，产物名 `multi-project-release-Windows` / `multi-project-release-Linux`。

随后只提交文档状态回填，使用 `[skip ci]`，不把该文档提交算作新的实现验证。P20 已收口；当前下一主阶段为 [P21 对象图与变更影响](p21-object-graph-plan.md)，状态 planned。
