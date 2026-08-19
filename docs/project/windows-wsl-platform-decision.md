# 第3周运行平台决策

## 决策

采用混合环境，不进行整机Linux迁移：

- Windows：DOCX/Excel、Generate-Arxml、DaVinci、Simulink及职业文档；
- WSL2 Ubuntu 24.04：SocketCAN/vcan、can-utils、OpenBSW POSIX spike、CMake/Ninja及后续 Linux-first 开源组件；
- python-can virtual：WSL不可用时的强制fallback；
- Docker：可选，不作为第3周前置条件。

## 当前探测事实（2026-08-17 更新）

- WSL 2.7.11.0，默认发行版 Ubuntu-24.04，运行于 WSL2；
- 内核为 `6.18.33.2-microsoft-standard-WSL2`；
- CAN、CAN RAW、CAN ISO-TP、VCAN 配置为模块，匹配的模块文件已确认存在；
- Git、GCC、G++、Make、Python、ip、modprobe 已存在；
- can-utils、CMake、Ninja 尚待安装或复验；
- `vcan0` 尚待创建和实际收发验收；
- Docker 不是当前 R2 阶段前置条件。

## 已采用的进入方式

```text
Windows: D:\ＬＬＭ\automotive-workbench
WSL:    /mnt/d/ＬＬＭ/automotive-workbench
```

不再安装 Ubuntu 22.04。OpenBSW 官方原生基线差异通过限时 spike 处理，不通过重装系统提前规避。

## 为什么不是完全转Linux

商业AUTOSAR工具、Office输入和Simulink仍以Windows工作流为主；SocketCAN及多数开源汽车实验在Linux更自然。双平面能同时训练企业现实中的商业工具桥接和开源CI/虚拟验证。

## 文件布局建议

- Windows项目继续保留现有位置；
- OpenBSW等Linux大型构建仓库放在WSL的`~/work/`，不要直接在`/mnt/d`编译；
- 只把JSON、日志、测试报告和公开生成物同步到Windows控制仓；
- 不在Windows和WSL同时修改同一个工作树。

## 退出条件

- WSL安装或网络问题在一个学习时段内无法解决：立即使用python-can virtual，不阻塞第3周；
- OpenBSW构建连续两个时段仍未进入官方测试：暂停spike，回到Python虚拟ECU；
- Docker daemon问题不在本阶段修复，除非某个已选实验明确必须使用Docker。
# 当前落地状态（2026-08-13）

python-can `virtual` fallback 已在 `D:\ＬＬＭ\automotive-workbench` 落地，并通过双节点收发、错误 ID、超时和非法物理值实验。它保证后续学习不被 WSL/Docker 环境阻塞，但不改变主方案：具备可用 Linux 环境后仍应迁移同一实验语义到 SocketCAN/vcan，再评估 OpenBSW POSIX。
