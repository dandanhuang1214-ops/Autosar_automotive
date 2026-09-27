# P23：独立 ECU 证据阅读练习

本页是练习入口，不代表使用者已经掌握 OpenBSW 或 BSW 集成。先按 [执行指南](../project/p23-external-ecu-guide.md)运行，再从自己的报告回答以下问题。

1. 在 `inputs/build.json` 找出 commit、ELF hash 和三份关键源码 hash，解释为什么只知道源码 HEAD 不能证明当前 ELF 由它构建。
2. 对照 `inputs/can_source.txt`、`docan_source.txt` 与 `uds_source.txt`，定位通道、请求/响应 ID 和 CF01 数据，说明哪些是构建声明，哪些由实际帧观测支持。
3. 在 `diagnostic/uds-did-report.json` 找到 `22CF01` 请求及 SF/FF/FC/CF，说明为何客户端启动成功和 ECU 进程存活都不足以证明一次诊断通过。
4. 对比 no-response、wrong-response-id 与 wrong-did 的实际结果：前两者都可能超时，不能只凭超时把故障定位到某个 BSW 模块；NRC 则是另一种实际响应证据。
5. 查看 ECU/client 的 PID、退出码及清理记录。解释通道锁只能约束遵守同一锁约定的程序，以及为何只应清理本次创建的进程。
6. 移动输出目录后复验，说明保存的字节一致性与重新执行 ECU 的差别。再修改一个快照，确认复验拒绝。

个人验收应包含自己执行的命令、定位到的源码行、原始报告及口头解释；平台自动化测试与本机现场成功不能替代这些学习证据。
