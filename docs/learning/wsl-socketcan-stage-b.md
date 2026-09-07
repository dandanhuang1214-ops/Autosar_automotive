# Linux 学习与 WSL SocketCAN 方案 B

## 学习目标

这不是“为了运行一个 vcan 命令而装 Linux”，而是掌握后续嵌入式岗位可迁移的基础：

- Windows、WSL2 VM、Linux distribution 和 kernel 的关系；
- shell、路径、权限、包管理和进程；
- 内核配置 `CONFIG_*`、built-in 与 module 的区别；
- `modprobe`、`lsmod`、`dmesg` 的基本用途；
- Linux network interface 与 `ip link`；
- CMake/Ninja/GCC 构建工具链；
- SocketCAN/vcan 与普通 Python 进程内 virtual bus 的区别。

## Stage B0：只读核实

请在你自己的普通 PowerShell 中运行，不要使用管理员 PowerShell：

```powershell
wsl --version
wsl --status
wsl -l -v
```

先不要安装、更新、注销或删除任何 distribution。把完整输出保存到本文件的“执行记录”部分。

如果发行版存在，再使用实际名称运行；下面的 `Ubuntu-22.04` 只是示例：

```powershell
wsl -d Ubuntu-24.04 -- uname -a
wsl -d Ubuntu-24.04 -- sh -lc "cat /etc/os-release"
wsl -d Ubuntu-24.04 -- sh -lc "command -v python3; command -v git; command -v cmake; command -v ninja; command -v ip; command -v modprobe"
```

## Stage B1：检查现有 CAN 能力

只有 B0 成功后才运行：

```powershell
wsl -d Ubuntu-24.04 -- sh -lc "zgrep -E 'CONFIG_CAN(=|_)|CONFIG_VCAN' /proc/config.gz 2>/dev/null || grep -E 'CONFIG_CAN(=|_)|CONFIG_VCAN' /boot/config-$(uname -r) 2>/dev/null || true"
wsl -d Ubuntu-24.04 -- sh -lc "lsmod | grep -E '(^can|vcan)' || true"
wsl -d Ubuntu-24.04 -- sh -lc "ip -details link show type vcan 2>/dev/null || true"
```

结果解释：

- `CONFIG_CAN=y`：CAN 编入内核，不需要加载主模块；
- `CONFIG_CAN=m`：CAN 是模块，需要匹配的 modules；
- `CONFIG_VCAN=m`：vcan 是模块，可尝试 `modprobe vcan`；
- `# CONFIG_CAN is not set` 或完全没有相关配置：才进入自定义内核评估；
- 配置为 `m` 但模块文件不存在：仍可能需要重建并安装 modules。

不要在此阶段执行 `sudo modprobe` 或 `ip link add`，先把输出交给平台计划复核。

## 后续阶段（当前不要执行）

B2～B4 会涉及包安装、内核源码下载、数 GB 构建空间、较长编译、`.wslconfig` 修改和 WSL 重启。每一阶段会单独给出：

- 预计时间和磁盘；
- 具体命令及其含义；
- 验收输出；
- 回退方法；
- 学习问题；
- 是否需要管理员权限。

## 执行记录

### B0 输出

已完成（2026-08-14）：

```text
WSL version: 2.7.11.0
Kernel version: 6.18.33.2-2
Windows: 10.0.19045.6466
Default distribution: Ubuntu-24.04
Default WSL version: 2
Ubuntu-24.04: Running / WSL2
docker-desktop: Stopped / WSL2
```

B0 结论：WSL2 和 Ubuntu 24.04 已安装并运行，无需执行 `wsl --install`，也无需新建 Ubuntu 22.04。对 `Ubuntu-22.04` 的命令返回 `WSL_E_DISTRO_NOT_FOUND`，原因只是发行版名称不匹配，不是 WSL 或 Linux 故障。后续所有命令改用 `Ubuntu-24.04`。

### B1 输出

进行中（2026-08-14）：

- `uname -a` 成功：`6.18.33.2-microsoft-standard-WSL2`，x86_64；
- `/etc/os-release` 成功：Ubuntu 24.04.1 LTS (Noble)；
- 每次启动出现 `chdir(/mnt/c/Users/20261/Desktop) failed 5`，但 Linux 命令仍执行成功。原因是 WSL 尝试继承当前 Windows Desktop 工作目录失败，后续使用 `wsl -d Ubuntu-24.04 --cd ~` 从 Linux home 启动；
- 工具循环和 CAN 检查尚未得到有效结果。失败来自 PowerShell → wsl.exe → `sh -lc` 多层引号/变量展开，不代表工具缺失或内核不支持 CAN；
- 后续改为进入交互式 Linux shell 后运行原生命令，避免 `$cmd`、`$(uname -r)` 和正则在 PowerShell 层被改写。

B1 已完成复核：

```text
python3/git/gcc/g++/make/ip/modprobe/modinfo: present
cmake/ninja: missing（R2 不需要，OpenBSW 构建前再补）
CONFIG_CAN=m
CONFIG_CAN_RAW=m
CONFIG_CAN_BCM=m
CONFIG_CAN_ISOTP=m
CONFIG_CAN_VCAN=m
MODULE_DIR_PRESENT
vcan.ko / can.ko / can-raw.ko / can-bcm.ko / can-isotp.ko: present
NO_CAN_MODULES_LOADED
vcan0: not observed
```

`find` 访问 modules 目录中的 `lost+found` 出现 Permission denied，不影响结论；目标 CAN modules 已成功列出。

B1 结论：当前 Microsoft WSL2 内核已经提供完整 R2 所需 CAN/RAW/BCM/VCAN 模块。无需下载内核源码、编译自定义内核或修改 `.wslconfig`。下一步只需加载模块并创建运行期 vcan0；这些状态在 WSL VM 关闭后可消失，属于可逆环境操作。

### 当前结论

B0、B1 通过。自定义内核阶段 B2 明确跳过；进入模块加载和 vcan0 创建验证。OpenBSW 所需 CMake/Ninja 暂未安装，不阻塞 R2。

### 2026-08-17：DrvFS 恢复与平台探测

- `/mnt/d` 一度对整个 D 盘返回 `Input/output error`，不是全角目录 `ＬＬＭ` 的单点问题；
- Windows PowerShell 执行 `wsl --shutdown` 后重新进入 Ubuntu，`/mnt/d` 恢复；
- 已成功进入 `/mnt/d/ＬＬＭ/automotive-workbench` 并列出完整仓库；
- `probe_socketcan.sh` 确认 CAN 配置、modules 目录和 `vcan.ko` 均存在；
- `vcan0_present=false`、`can_utils_present=false`；
- `probe_openbsw.sh` 确认 Git/GCC/G++/Make/Python 已存在，CMake/Ninja 尚缺；
- Ubuntu 24.04 不是当前记录的 OpenBSW 官方原生基线，后续采用限时兼容性 spike；
- WSL 内 `code .` 尚不可用，应使用 Windows VS Code 的 Microsoft WSL 扩展连接，不安装 Snap 版 VS Code。

下一关：安装基础工具、创建 `vcan0`，用 `candump/cansend` 验证内核总线，再运行 Workbench SocketCAN backend lab。
