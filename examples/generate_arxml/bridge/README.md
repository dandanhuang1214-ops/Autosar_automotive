# Generate-Arxml → Workbench 导出桥接

这里的 `contract.json` 和 `issues.json` 是实际运行 Generate-Arxml 导出的原始文件；输入 DOCX 是为本平台编写的公开合成车窗案例，不是 OEM/客户文档。它们用于验证真实工具之间的连接，不表示生产项目或 DaVinci 已验收。

生产者为本机 `/mnt/d/work/SOA/code` 仓库的固定提交 `e912e404d52e671c7561d518d9989af3382fce51`。通过 `git archive` 导出临时源码执行，未使用其未提交修改。生产者原仓库为 `https://github.com/dandanhuang1214-ops/Generate-Arxml`；版本字段是本地记录，不是远端身份认证。

## 直接消费已有导出

在 Workbench 根目录使用已安装 CAN 依赖的解释器运行：

```bash
python -m automotive_workbench.cli run-project examples/generate_arxml/bridge/baseline/project.json --output output/arxml-baseline
python -m automotive_workbench.cli run-project examples/generate_arxml/bridge/scale-change/project.json --output output/arxml-scale-change
python -m automotive_workbench.cli run-project examples/generate_arxml/bridge/missing-init/project.json --output output/arxml-missing-init
```

| 案例 | DOCX 变化 | 生产者退出码 | generation | canonical | communication | Workbench 退出码 |
|---|---|---:|---|---|---|---:|
| baseline | 完整的两信号公开输入 | 0 | passed | passed | passed | 0 |
| scale-change | WindowPosition Resolution 从 1 改为 2 | 0 | passed | failed | skipped | 2 |
| missing-init | 删除 WindowPosition InitValue | 1 | failed | passed | skipped | 2 |

每个输出的 `bundle/index.html` 展示验收项与各阶段链接。`generation.json` 保留全部上游 findings：正常和缺初值案例各有两条端口未连接 WARNING；scale-change 另有 `CORE-010-PHYS-RANGE-CONSISTENCY`。这些警告不会被隐藏，也不被擅自改成 ERROR。跨工具的 `MAP-NUMERIC-MISMATCH` 则由 Workbench 按自己的 DBC 校验规则生成。

未闭合问题、模型验证错误、CORE ERROR 或生产者退出码 1 都会使 generation 阶段失败。即使项目未声明 generation 验收项，阶段失败仍会阻止通信实验。

## 重新运行真实生产者

为 Generate-Arxml 准备独立 Python 环境，安装其 `pyproject.toml` 依赖；Workbench 消费已有导出时无需这些依赖。本次实测的生产者环境为 Python 3.12.3、openpyxl 3.1.5、lxml 6.1.3、pydantic 2.13.5、PyYAML 6.0.3、python-docx 1.2.0。

```bash
PYTHONPATH=src .venv/bin/python scripts/run_generate_arxml_bridge.py \
  --repository /mnt/d/work/SOA/code \
  --producer-python /tmp/p16-generator-env/bin/python \
  --output output/arxml-replay
```

`/tmp/p16-generator-env/bin/python` 是本次建立的临时环境，清理后需替换为自己准备的解释器路径。该命令不会下载代码或依赖，默认固定上述提交，忽略原仓库工作区修改。输出目录必须为空或不存在。

脚本用 `create_public_delivery_docx.py` 生成三份确定性 DOCX，然后在各案例目录执行生产者的：

```text
scripts/docx_to_contract.py --input source.docx --contract contract.json --excel model.xlsx --report-json issues.json --mode signal --profile signal_atomic_davinci
```

随后用当前 Workbench 验收。`bridge-replay.json` 记录实际生产者退出码、源码 archive/script 哈希、解析依赖版本、三组输入/输出哈希及验收状态。生产者源码仅在临时目录存放；脚本不申请或输出最终 ARXML。

本次重放归档：`output/p16-replay/bridge-replay.json`。生产者 script SHA-256 为 `aed933c9757923f0181ec320052ffc623dd470927132b99391604364826d244e`。此脚本执行固定提交，故当前上游工作区内新增能力或 bug fix 不属于本次结论。

## 接入自己的导出

复制一个案例目录，将 `contract.json`、`issues.json`、`source.docx` 替换为同次导出的文件，再填写 `project.json` 的 `generation`：tool、完整 revision、实际 exit_code、两份来源路径及三份文件 SHA-256。项目 0.2 不会自动相信内容变化后的旧哈希；不匹配会在创建验收输出之前拒绝。

当前 adapter 消费固定版本 gap report 中的 items/counts/validation_errors/core_summary，并校验它们与 contract 的数量一致性。生产者升级导致结构变化时应显式调整适配器并重放三例，不静默忽略字段错误。

first workflow 的通信场景仍是车窗 `WindowStatus`/`WindowCommand` 和 `0x100`/`0x200`，其他项目需要先提供相应运行场景。这里将 RequestedDirection 作为 0..3 数值输入；没有声称完成枚举语义的跨工具验证。
