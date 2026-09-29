# P25 十分钟演示脚本（待人工实测）

目标是在十分钟内讲清“配置变化 → 影响范围 → 实际失败 → 引用与交付”。以下为演示分配，不是已经完成的人工演示记录。自动验证实测为首次本地 40.799 秒、归档依赖离线复跑 24.905 秒；两者均包括各自脚本的安装和运行，不包括人工讲解，也不保证其他机器耗时。

先按[交付指南](p25-installed-delivery-guide.md)生成归档，并准备浏览器打开项目 HTML。演示时保留终端实际输出；若任一检查失败，展示失败证据并说明原因，不能使用旧成功报告冒充当次运行。

| 时间预算 | 操作与讲解 | 可定位证据 |
|---|---|---|
| 0:00–1:00 | 说明输入、virtual CAN 范围与 wheel 安装隔离 | summary runtime、wheelhouse hash；commands installed-origin |
| 1:00–3:00 | 运行车窗和 ThermalControl，展示同一声明式入口 | 两个 project.json；projects/window 与 thermal 报告 |
| 3:00–5:00 | 展示 DBC 温度缩放 0.1 → 0.2，运行故障项目；解释退出 2 和通信 skipped | scale-failure 输入与 project-report stages/findings |
| 5:00–7:00 | 展示影响对象、thermal-status 验收项及 regressed 比较 | impact/report.json；comparison/index.html |
| 7:00–9:00 | 展示审查引用，迁移后复验；解释 failed 报告仍可验证完整性 | reviews、impact-review、replay 及 commands 的 replay 步骤 |
| 9:00–10:00 | 说明不支持的范围，以及下一次真实使用反馈要验证什么 | [能力证据表](p25-capability-evidence.md)、P25 剩余验收门 |

## 人工演示记录模板

- 日期、操作者、OS/Python、实现提交和 CI run：待实际填写。
- 归档位置及 summary hash：待实际填写。
- 实际开始/结束时刻与各步耗时：待实际填写。
- 是否在干净环境完成、出现的失败及恢复步骤：待实际填写。
- 无法独立解释或需要查文档的点：待实际填写。

## 外部反馈记录模板

真实使用或投递反馈尚未取得，不用代理自测代替。本文件不授权联系他人、发布包或向外部项目提交贡献。

取得用户授权的反馈后，记录使用场景、环境、输入版本、可复现步骤、实际错误、预期行为、相关证据和下一轮优先级；公开记录仅保留必要信息。缺少反馈时，P25 整阶段保持未完成。
