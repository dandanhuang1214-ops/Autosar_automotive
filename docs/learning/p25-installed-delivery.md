# P25：从源码运行到可安装交付

平台实现证据见[安装指南](../project/p25-installed-delivery-guide.md)和[能力证据表](../project/p25-capability-evidence.md)。本页记录需要自己理解的部分；自动测试通过不等于已经掌握。

本轮关键区别是：源码环境里能运行，不能证明 wheel 包含所需代码、入口正确、可选依赖齐全或运行时不依赖仓库路径。验证必须在新 venv、仓库外工作目录中，用安装后的绝对命令路径执行，并检查实际模块来源。wheelhouse 保存的是适配所记录平台/Python 的依赖，不保证任意机器可用。

独立练习：

1. 找出本次 `commands.json` 的离线安装和 installed-origin 结果，解释如何排除 checkout import；说明为什么只清除 PYTHONPATH 还不够。
2. 对照正常和故障项目，区分工程 failed、验证脚本 passed、证据复验 passed，指出三者检查的对象。
3. 把归档移到新目录，按照指南重跑；记录实际 OS、Python、开始/结束时间和结果。解释报告中的相对路径如何找到来源。
4. 用 `summary.json` 的 wheelhouse/input hash 找到一个具体文件；解释哈希一致为何仍不能证明生产者身份或物理 ECU 通过。

实际独立复跑：待记录。遇到的错误与自己的解释：待记录。尚不能独立解释的点：待记录。
