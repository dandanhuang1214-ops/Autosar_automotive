# P10 契约一致性与运行时前沿实施记录

## 目标

P10 不增加汽车协议或 adapter。它把 P0-P9 已有能力升级为可执行契约，并验证最低支持版本之外的当前 Python feature release，解决全局审计发现的 schema/loader 漂移、单一 Python 版本、无静态质量门禁和依赖解析版本不可追溯问题。

## 实施结果

### JSON Schema 成为 CI 门禁

`scripts/check_json.py` 现在执行三层检查：

1. 解析全部 schema 和 example JSON；
2. 使用各 schema 声明的 draft 执行 meta-schema 检查；
3. 按顶层 `schema_version` 自动绑定 schema，执行 Draft 2020-12 实例和 `format` 校验。

当前结果是 25 份 schema 有效、45 份自描述 example 通过实例校验。另有 16 份外部输入、固定报告或无 `schema_version` fixture，只能证明 JSON 语法有效；工具会明确输出 `no declared schema`，不把它们计为 schema 合规。

manifest、delivery receipt 与 capsule report 的 boolean count 负例同时送入 JSON Schema 和对应 Python loader，双方都必须拒绝。这是首个显式 accept/reject parity 门禁。

### Python 运行时前沿

`requires-python >=3.11` 保持不变：3.11 仍是最低兼容契约。CI 新增独立的 Ubuntu 22.04/Python 3.14 job，安装完整 diagnostic 与开发依赖并运行全量测试。Python 官方文档将 3.14 列为当前稳定系列，并提供专门的 porting/change 说明。[^1]

没有加入 free-threaded build，也没有立即构造完整 OS×Python 笛卡尔矩阵；当前目标是尽早发现新解释器兼容问题，而不是扩大 CI 成本。

### 最小静态质量门禁

Ruff 在全仓启用 `E4/E7/E9/F`，覆盖 import/runtime error、语法、未定义名称和未使用符号等低争议错误，不进行全仓格式重写。当前使用的官方 PyPI release 是 0.16.6。[^2]

mypy 以 Python 3.11 语义检查 evidence bundle/capsule 安全路径和 P10 脚本。范围化门禁避免把一次里程碑变成 9,000 多行的强制类型迁移；后续新安全模块应进入该列表。当前 PyPI release 是 2.3.1，并声明支持 Python 3.14。[^3]

### 解析依赖证据

`resolved-dependency-inventory-0.1` 记录：

- Python implementation 与精确版本；
- 操作系统平台字符串；
- Workbench、cantools、python-can、can-isotp、udsoncan、jsonschema、mypy 与 Ruff 的解析版本；
- 未安装的可选依赖以 `not-installed` 显式表示。

Windows/Python 3.11、Ubuntu/Python 3.11 和 Ubuntu/Python 3.14 分别生成并上传 inventory。依赖仍由 `pyproject.toml` 的兼容范围管理，inventory 是“本次证据实际使用版本”的快照，不冒充 lock file。

jsonschema 4.26.0 是当前 PyPI release，并支持 Python 3.10 及以上。[^4]

## 本地验收

| 检查 | 结果 |
|---|---|
| 全量 unittest | 153 项运行，151 通过，2 项环境条件跳过 |
| 契约/evidence 定向测试 | 29/29 通过 |
| Schema | 25 份 meta-schema 通过 |
| Schema-bound example | 45/45 通过 |
| Syntax-only fixture | 16 份，明确未声明 schema |
| Ruff | 全仓通过 |
| mypy | 5 个安全敏感源文件通过 |
| compileall/Bash/pip check | 通过 |

首轮远端 run `34445964343` 已验证 Windows/Python 3.11、Ubuntu/Python 3.11 和 Ubuntu/Python 3.14 三个 job 全部通过。复核冻结条件后又补齐三个 evidence loader 的 RFC 3339 时间戳拒绝，以及 manifest/capsule portable path 对反斜杠的 schema 拒绝；最终 run `34446441635` 再次验证三个 job 全部通过，P10 契约冻结。

## 边界与后续

- schema 自动绑定只接受 schema 中显式声明的 `schema_version`；不能识别的版本不会被猜测绑定。
- syntax-only fixture 仍需在未来出现稳定 producer contract 时逐步补 schema，不应为追求数字给外部格式套错误 schema。
- mypy 是渐进式范围门禁，不代表全仓 strict typing。
- dependency inventory 不提供哈希锁定、签名或 provenance authentication。
- P10 已冻结；后续 schema/loader 新版本必须同步增加正例、负例和 parity 回归。OpenBSW drift revalidation 仍需明确 adapter 或上游化需求触发。

## Sources

[^1]: Python Software Foundation, “[What’s New in Python 3.14](https://docs.python.org/3.14/whatsnew/index.html),” accessed 2026-09-10.
[^2]: Astral, “[Ruff on PyPI](https://pypi.org/project/ruff/),” release 0.16.6, accessed 2026-09-10.
[^3]: mypy project, “[mypy on PyPI](https://pypi.org/project/mypy/),” release 2.3.1, accessed 2026-09-10.
[^4]: Python JSON Schema, “[jsonschema on PyPI](https://pypi.org/project/jsonschema/),” release 4.26.0, accessed 2026-09-10.
