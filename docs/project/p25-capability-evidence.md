# P25 能力与证据对应

此表描述平台已实现的工程能力及可检查证据，不代表使用者已经能独立讲解、修改或调试。个人练习按“待独立复跑／能解释／能独立修改并复验”另行记录；未演示前不填掌握。

| 能力方向 | 可以展示的具体工作 | 证据入口 | 必须说明的边界 |
|---|---|---|---|
| 工具链：Python 发行与环境隔离 | wheel + CAN 依赖安装；在仓库外执行完整项目 | P25 `summary.json` runtime/wheelhouse；`commands.json` installed-origin/offline-install；`scripts/check_installed_projects.py` | 依赖包适配本次 OS/Python；不是通用离线安装器 |
| 配置自动化：声明驱动项目 | 车窗、ThermalControl 使用同一 CLI 和执行内核 | `portable/examples/*/project.json`；`portable/projects/*/bundle/index.html` | 公开受限模型；未支持的供应商配置不能自行推断 |
| 工具链：失败门控 | DBC 缩放与 canonical contract 不一致，静态失败阻止通信 | `portable/projects/scale-failure/bundle/project-report.json` stages；对应 review | failed 是预期工程结果，脚本通过表示正确检测到失败 |
| BSW：跨层对象与影响 | 定位 thermal-status 相关对象、传播路径及验收项 | `portable/impact/report.json` 的 affected、paths、vectors、requirements | 受限通信对象图，不等同真实 vendor ECUC 验证 |
| 工程审查：保留事实与引用 | 比较正常与故障结果，引用规则来源，迁移后复算 | `portable/comparison/project-comparison.json`；reviews；impact-review | 引用完整性不认证生产者身份，不补造故障唯一根因 |
| BSW 集成：独立 ECU 通信 | 固定 OpenBSW POSIX/vcan0 的构建、寻址、CF01 与进程清理 | [P23 验收](p23-acceptance.md)中的原始现场运行记录 | 此次 P25 默认演示不重跑 OpenBSW，不声称物理 ECU 量产验收 |
| 质量工程：跨平台交付 | Windows/Ubuntu 七 job 流程，Python 3.14 回归 | 当前实现对应 CI run 和 installed-projects 两平台 artifact | 本地成功不能替代远端结论；见进度账本当前状态 |

## 独立练习验收

1. 不看脚本，按[交付指南](p25-installed-delivery-guide.md)在新目录运行两个项目，解释正常结果。
2. 找到缩放变化的原始 DBC 行、对应 contract 字段和实际 Finding，说明为何通信没有运行。
3. 沿 `impact/report.json` 指出一个受影响对象到验收项的路径，并解释为何 pump-status 不在本次向量影响结果中。
4. 区分报告 failed、证据复验 passed 和脚本退出码，解释这三者为何不冲突。
5. 将证据复制到其他目录，独立复验，再故意删除一个来源文件观察拒绝。只修改副本，保留原始归档。

练习的实际命令、输出位置、耗时和不能解释的问题应单独记录。没有实际记录时，不能把自动脚本成功转写成个人熟练度。
