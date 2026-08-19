# R2 SocketCAN/vcan 后端调研与方案

日期：2026-08-14  
状态：已选择方案 B（2026-08-14）；进入分级环境核实，尚未修改 WSL 内核

## 目标

让 R1 已完成的 capture、decode、replay 和 supervision 实验在 Linux SocketCAN/vcan 上运行，同时保持 Windows `python-can virtual` 主线继续可用。

R2 不负责：自动安装 WSL、替换内核、启用管理员功能、构建 OpenBSW、接入真实 CAN 硬件。

## 本机当前可观察事实

在当前 Codex 会话中：

- `wsl --status` 和 `wsl -l -v` 返回 `Wsl/EnumerateDistros/Service/E_ACCESSDENIED`；
- Docker CLI 29.5.2 存在，但 Docker daemon 没有运行；
- Windows PATH 中没有 `cmake` 和 `ninja`；
- Git for Windows 可用。

以上只代表当前受限会话不能访问 WSL 服务，不能据此判断用户正常 PowerShell 中是否已安装 WSL。需要用户在普通 PowerShell 中复核。

## 官方事实

### SocketCAN 是 Linux 内核能力

SocketCAN 使用 Linux 网络栈和 PF_CAN socket；CAN 设备被表示为网络接口。vcan 是不需要 CAN 控制器硬件的虚拟网络设备。

来源：<https://docs.kernel.org/networking/can.html>

### python-can 已提供 SocketCAN backend

python-can 的 `Bus(interface="socketcan", channel="vcan0")` 可以直接打开 vcan0/can0。SocketCAN 后端还可利用 Linux BCM 做周期发送、内核级过滤和内核 timestamp。当前 Workbench 的 `BusConfig` 已经为这个切换保留了结构。

来源：

- <https://python-can.readthedocs.io/en/stable/index.html>
- <https://python-can.readthedocs.io/en/stable/_modules/can/interfaces/socketcan/socketcan.html>

### 默认 WSL2 不应假定包含 CAN/vcan

OpenBSW 官方 WSL 指南明确说明默认 WSL 内核可能不支持 CAN，并给出了克隆 WSL2-Linux-Kernel、配置 CAN、编译内核、安装模块、通过 `.wslconfig` 切换内核的完整流程。Microsoft 官方也支持在 `.wslconfig` 中指定自定义 kernel 和 kernelModules。

来源：

- <https://eclipse-openbsw.github.io/openbsw/sphinx_docs/doc/dev/learning/setup/setup_wsl_socketcan.html>
- <https://learn.microsoft.com/windows/wsl/wsl-config>

这意味着“启用 WSL vcan”可能从 5 分钟命令变成内核维护任务，不能由平台安装脚本静默执行。

### Docker 不是可靠绕过路径

SocketCAN/vcan 属于宿主 Linux 内核网络能力。Windows Docker Desktop 容器仍依赖其 Linux VM 内核及容器权限；仅启动一个普通容器不能保证存在或允许创建 vcan。因此 Docker 可作为实验候选，但不能作为 R2 默认方案。

### OpenBSW 依赖同一 Linux 执行面

OpenBSW POSIX 能在无汽车硬件时运行，并在主机支持 SocketCAN 时使用 CAN。后续 UdsTool 的 POSIX 示例也以 `vcan0` 和 `socketcan` 为默认组合。因此先把 R2 环境边界处理好，会直接降低 OpenBSW/UDS 阶段风险。

来源：

- <https://eclipse-openbsw.github.io/openbsw/sphinx_docs/doc/dev/platforms/posix/index.html>
- <https://eclipse-openbsw.github.io/openbsw/sphinx_docs/tools/UdsTool/doc/index.html>

## 三种路线

### 方案 A：探测优先、环境解耦（推荐）

先实现平台能力，不修改系统：

1. `probe-can-backend` 输出 OS、interface、channel、python-can backend、打开结果和失败原因；
2. 定义 capability：`available/open/send/receive/capture/replay`；
3. SocketCAN integration test 默认标为 `skipped`，只有 `vcan0` 探测成功才运行；
4. virtual 和 socketcan 使用同一 R1 测试向量，对比 ID、payload、顺序、decode Finding；
5. 输出 environment evidence JSON/Markdown；
6. 提供只读检查命令和人工 setup 文档，不执行 `sudo`、`modprobe`、`ip link add`、`.wslconfig` 修改。

优点：平台持续前进，不冒险修改用户系统；环境具备后立即验证。  
缺点：如果本机没有 vcan，R2 的 SocketCAN 实际运行仍会显示 blocked/skipped。

### 方案 B：立即为 WSL 编译自定义内核

按 OpenBSW 官方步骤启用 CAN/vcan。

优点：最终可得到 WSL2 + vcan + OpenBSW 的统一环境。  
缺点：需要 WSL2、Ubuntu、编译依赖、较多磁盘/时间、管理员操作、重启 WSL；Windows/WSL 更新后还要维护兼容性。当前甚至尚未在普通 PowerShell 确认 WSL 状态，不应直接选择。

### 方案 C：另建标准 Ubuntu VM

使用 Hyper-V/VMware/VirtualBox 的标准 Ubuntu 22.04/24.04 内核创建 vcan。

优点：更接近标准 Linux，避免 WSL 自定义内核维护；OpenBSW POSIX 也更自然。  
缺点：多一套 VM、磁盘和文件同步；与 Windows 工程目录协作不如 WSL 方便。

当 WSL 确认缺少 CAN 且用户不愿维护自定义内核时，方案 C 比在 Docker 中碰运气更可靠。

## 推荐实施方案

采用 A，分成 R2a 和 R2b：

### R2a：现在实施，不修改系统

- backend probe 与环境证据；
- SocketCAN conditional integration test；
- virtual/socketcan 等价测试契约；
- `blocked` 与 `skipped` 语义；
- WSL/Linux 只读检查脚本；
- CI 继续强制 virtual，SocketCAN 只有 runner 真正具备 vcan 时才执行。

验收：在 Windows 上 probe 必须明确返回 `unsupported_platform`，不是 traceback；在 Linux 无 vcan 时返回 `interface_missing`；在 vcan0 可用时运行完整 R1 capture/decode/replay。

### R2b：环境确认后选择执行面

用户在普通 PowerShell 中运行：

```powershell
wsl --status
wsl -l -v
wsl -d Ubuntu-22.04 -- uname -r
wsl -d Ubuntu-22.04 -- sh -lc "grep -E 'CONFIG_CAN|CONFIG_VCAN' /proc/config.gz 2>/dev/null || true"
wsl -d Ubuntu-22.04 -- sh -lc "ip -details link show type vcan 2>/dev/null || true"
```

根据结果：

1. vcan 已可用：直接验证 SocketCAN；
2. CAN 模块可用但 vcan0 未创建：用户在确认后人工创建；
3. 内核缺少 CAN：暂不自动编译，先比较 WSL 自定义内核与 Ubuntu VM 成本；
4. WSL 不可用：R2a 完成，R2b blocked，平台继续日志和故障分析能力，不停止其他研发。

## 为什么不立即进入 OpenBSW

OpenBSW POSIX 构建本身和 CAN 执行面是两个变量。如果现在同时引入，会无法区分失败来自构建工具、第三方依赖、WSL 内核还是 SocketCAN。先用轻量 python-can 验证 vcan，可以把 OpenBSW spike 的风险限制在 C++ SDK/调用链本身。

## 需要确认

建议确认以下决策：

- 先实施 R2a，不修改 WSL/Docker/内核；
- SocketCAN 不可用时必须明确 `blocked/skipped`，不能让 virtual 冒充；
- 用户稍后在普通 PowerShell 运行五条只读命令；
- 只有确认内核缺少 CAN 后，再单独决定 WSL 自定义内核或 Ubuntu VM；
- OpenBSW 延后到 R2b 的 vcan 实际收发通过之后。

## 用户决策与执行约束

用户选择方案 B，原因是希望把本阶段同时作为 Linux/嵌入式基础能力训练。执行顺序调整为：

1. B0：只读核实 Windows、WSL2、发行版和内核版本；
2. B1：核实当前内核的 CAN/CAN_RAW/VCAN 配置，先尝试现有能力；
3. B2：仅当配置缺失时，按与当前 WSL 内核匹配的 Microsoft 分支编译自定义内核；
4. B3：经用户确认后修改 `%UserProfile%\.wslconfig`，保留原配置和默认内核回退方法；
5. B4：创建 vcan0，运行 `cansend/candump` 和 Workbench R1 等价实验；
6. B5：形成 Linux 环境、内核配置、构建和实验报告，再进入 OpenBSW POSIX。

系统边界：平台代码不得自动执行管理员命令、安装 Windows 功能、覆盖 `.wslconfig`、切换内核或删除构建目录。所有系统变更必须在只读检查通过后单独确认。

### 环境核实结果更新

用户的 WSL 2.7.11 / Microsoft kernel 6.18.33.2 已提供 `CONFIG_CAN=m`、`CONFIG_CAN_RAW=m`、`CONFIG_CAN_BCM=m`、`CONFIG_CAN_ISOTP=m`、`CONFIG_CAN_VCAN=m`，并存在匹配的 `can.ko`、`can-raw.ko`、`can-bcm.ko`、`can-isotp.ko` 和 `vcan.ko`。因此方案 B 不再需要自定义内核：B2/B3 跳过，直接进入可逆的模块加载和 vcan0 创建。这个结果优于调研时依据 OpenBSW 文档作出的保守假设。
