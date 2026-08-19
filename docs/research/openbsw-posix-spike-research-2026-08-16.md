# OpenBSW POSIX Spike 前置调研

日期：2026-08-16  
结论：先做 readiness probe；vcan 与 Linux Python 闭环通过后，再限时 clone/build。

## 官方事实

- OpenBSW 官方 README 首推其 development Docker image，然后在容器内执行 `cmake --preset posix` 和 `cmake --build --preset posix`；同时也提供 Bazel 构建。来源：<https://github.com/eclipse-openbsw/openbsw>
- POSIX 平台无需汽车硬件，但 CAN/DoCAN 能力依赖主机 SocketCAN。来源：<https://eclipse-openbsw.github.io/openbsw/sphinx_docs/doc/dev/platforms/posix/index.html>
- 官方文档当前明确指向 Ubuntu 22.04 或 Windows 的环境指南；本机是 Ubuntu 24.04.1，因此原生构建兼容性尚未被官方基线直接覆盖，不能先宣称支持或不支持。
- reference application 的 POSIX 入口、CanSystem/DemoSystem 和 unitTest 入口已有官方导航，适合后续限时源码调用链分析。来源：<https://eclipse-openbsw.github.io/openbsw/sphinx_docs/doc/dev/index.html>
- GoogleTest 源码已包含在项目中；测试要求行为命名、明确描述并避免测试内条件逻辑。来源：<https://eclipse-openbsw.github.io/openbsw/sphinx_docs/doc/dev/guidelines/unittests.html>

## 路线判断

第一选择仍按官方推荐使用 development container，因为它可以隔离 Ubuntu 24.04 与官方 Ubuntu 22.04 基线差异。但当前 Windows Docker daemon 未运行，WSL 内 Docker 集成也尚未核实，所以不能立刻承诺容器构建。

备选是 WSL Ubuntu 24.04 原生 CMake 构建。当前 gcc/g++/make 已存在，cmake/ninja 缟失。只有当官方容器不可用且依赖清单可控时，才安装原生构建依赖。

## Spike 门槛

进入 clone/build 前必须满足：

1. vcan0 实际收发通过；
2. Workbench SocketCAN backend lab 通过；
3. 确认 Docker development container 可用，或明确批准 Ubuntu 24.04 原生构建实验；
4. 记录 OpenBSW commit SHA 和 Apache-2.0/NOTICE；
5. 设定构建时间预算和退出条件；
6. 不把 OpenBSW 描述为完整 AUTOSAR Classic 商业栈。

## 首次 Spike 产物

- readiness report；
- clone commit/license evidence；
- POSIX referenceApp 或 unit tests 的一次可复现构建；
- CAN SocketCAN 入口和 Rx/Tx 调用链索引；
- 一个最小测试或公开车窗 frame adapter 的可行性判断；
- 构建失败时的分类报告，而不是无限修环境。
