# P22 公开 ARXML 离线桥接

本轮交付真实 Generate-Arxml 导出的受限结构语义导入、引用检查、比较和快照复验。实现 `6166b80` 已通过 [run `36235450078`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/36235450078) 七 job 与双平台场景/上传验收。P22 项目 0.4 已实现，正在进行本轮独立验收，见文末项目路径与验收表；离线通过不代表商业工具导入成功。

## 使用

仅需 Workbench 本体，无 XML/CAN 第三方运行依赖。输出目录须为空或不存在。

```bash
python -m automotive_workbench.cli import-arxml examples/generate_arxml/xml/model.arxml --provenance examples/generate_arxml/xml/provenance.json --output output/arxml-import
python -m automotive_workbench.cli compare-arxml examples/generate_arxml/xml/model.arxml examples/generate_arxml/xml/model.arxml --output output/arxml-comparison
python -m automotive_workbench.cli verify-arxml output/arxml-import/arxml-report.json
python scripts/run_arxml_scenarios.py --output output/arxml-scenarios
```

导入成功/稳定比较/完整性复验返回 0；引用错误、发现变化或不可比较返回 2；非法输入、版本不匹配或非空输出返回 1。`changed` 只表示配置结构发生变化，不等于配置错误。`verify-arxml` 返回 0 只表示忠实重现保存结论，即使被复验的原始报告是 failed。

省略 `--provenance` 时生产者为 unrecorded。指定后必须与 XML SHA-256 匹配；生产者版本是本地执行记录或调用者声明，不是身份认证。比较命令的 `--provenance` 绑定 baseline，candidate 默认 unrecorded；两个输入各自的原始字节始终在比较报告中保留。

## 实际导出审计

使用固定 Generate-Arxml 提交 `e912e404d52e671c7561d518d9989af3382fce51` 的 `scripts/docx_to_contract.py`，输入为 P16 已公开的车窗 `source.docx`，新增真实 `--arxml model.arxml` 参数。未使用生产者工作区未提交修改，也未引用其其他工程 ARXML。

- 声明 namespace 为 `http://autosar.org/schema/r4.0`，schemaLocation 为 `AUTOSAR_4-3-0.xsd`。这是文件声明和生产者行为，不是已通过 AUTOSAR XSD 验证的声明。
- 36 个 SHORT-NAME 对象（含 11 个 package），25 个 REF/TREF；包含一个 application SWC、P/R ports、两个 S/R interfaces、primitive/application/implementation types、mapping set、constraints、units、compu methods、runnable、timing event 和 variable accesses。
- 未包含 ECU Extract 或 COM/PduR/CanIf ECUC。不会从 `WindowControlSwc`、接口名称或 P/R port 推断总线 Tx/Rx 或 BSW 对象。
- 生产者退出 0；原始输出及脚本/source/archive SHA-256、参数、Python/依赖版本见 [provenance](../../examples/generate_arxml/xml/provenance.json)。基准 XML SHA-256 为 `d44c2ae60131ef6d0a75035fb35d54403f2ce2bc028370bf4822c1d497ddf6e6`。

独立生产者环境安装其依赖后，可重放：

```bash
python scripts/replay_arxml_export.py --repository /mnt/d/work/SOA/code --producer-python /tmp/p22-producer-env/bin/python --output output/arxml-export-replay
```

替换为自己的仓库与解释器路径。脚本固定源码提交，不联网、不修改生产者仓库；保留 stdout/stderr、实际 XML、workbook、contract、issues 和 provenance。UUID 每次重新生成，XLSX 也可能包含生成时刻；因此不要求重新导出字节哈希与冻结样例相同，应使用 `compare-arxml` 核对本子集语义稳定。未运行 DaVinci。

## 支持范围与比较含义

第一版是 **对象路径、结构字段值、属性、引用目标与 DEST 的受限语义**。完整词表 `NAMED/SUPPORTED/REFS` 固定在 `arxml_bridge.py`，来自上述真实导出；不做全量 AUTOSAR 元模型、XSD、单位换算、数值约束或 runnable 行为验证。生产者实际使用抽象 `APPLICATION-DATA-TYPE` DEST 指向 primitive application type，因此明确允许这一关系，其他引用按已审计的 DEST/目标类型检查。

每个对象按祖先 SHORT-NAME 建立绝对身份，保留命名空间固定的带同名 sibling 序号 XML locator；所属字段记录相对路径、值及属性。身份重复、非法/缺失 SHORT-NAME、悬空引用或 DEST 冲突使导入 failed。支持 UTF-8、4 MiB/20,000 节点/64 层上限；拒绝 DTD/entity、其他 namespace/release 和畸形 XML。

比较按稳定对象身份输出 added/removed/modified 及完整前后字段，保留原始 XML 快照和双方 hash。SHORT-NAME 重命名视为删除/新增。忽略 UUID、格式空白和命名对象排列；数字按文本保留，`0.01` 与 `0.010` 会报告变化。匿名重复结构按同名 sibling 序号定位，重新排序可能成为结构变化。结构差异不推断运行影响或验收项影响；后者仍由 P21 的明确配置依赖处理。

未知元素、外部 namespace、未知属性、混合文本逐定位列入 `unsupported`，覆盖为 partial，任何含 partial 或 failed 的输入均 not-comparable，不能给出虚假的 stable。每份报告固定记录 COM/IPdu/PduR/CanIf 映射 unknown。报告内嵌 Base64 原始 XML，移走或删除原始输入后可以重新解析核对整个结论；这证明内容自洽，不认证生产者。

## 场景与剩余门

`run_arxml_scenarios.py` 保留基准真实导出，仅用两个唯一文本锚点构造变体：TYPE-TREF 指向不存在的 `AbsentType`；TIMING-EVENT PERIOD 从 `0.01` 改为 `0.02`。它记录原始/变体 hash，并按 checked-in `golden.json` 核对正常、悬空、稳定、变化与拒绝比较五场景。变体是显式故障注入，不能称为生产者实际错误导出。脚本最后删除自己创建的输入并迁移五份报告，逐份调用真实 CLI 复验。

Windows/Ubuntu runtime-evidence 新增场景与 `arxml-bridge-{OS}` artifact，保留既有七 job。Python 3.14 与双平台 core 均运行新增单元回归；生产者重放为单独本地工具执行证据，CI 消费冻结 XML，不冒充 CI 重新运行生产者。

项目接入已实现，见下一节；完整公开路径需本轮实现提交自己的七 job 验收。商业工具安装/许可和往返单独验收：本轮检查 `/mnt/c/Program Files/Vector*` 与 `/mnt/c/Vector*` 均无匹配，未据此认定机器上绝无安装或许可；需确认实际安装位置、版本和合法许可后执行真实导入/回导。无商业条件时按路线保留 blocked，并在公开路径完成后推进 P23。

## 项目 0.4：静态门控、审查与迁移

`workbench-project-0.4` 在 0.3 声明通信项目上强制增加 `inputs.arxml` 和 `inputs.provenance`；原有 0.1–0.3 继续使用原契约。生产者 JSON 必须以 `arxml_sha256` 绑定实际 XML，其他工具版本字段原样保存；这是来源记录，不认证工具身份。`generation` 仍可独立声明 DOCX/contract/issues 门。

```bash
python -m automotive_workbench.cli run-project examples/window_control/project-arxml.json --output output/arxml-project
python -m automotive_workbench.cli run-project-review output/arxml-project/bundle/project-report.json --output output/arxml-project/review
python -m automotive_workbench.cli compare-projects output/arxml-project/bundle/project-report.json output/arxml-project/bundle/project-report.json --output output/arxml-project/comparison
python scripts/run_arxml_project_scenarios.py --output output/arxml-project-scenarios
```

项目运行需要 CAN 可选依赖，默认使用隔离 virtual 通道。项目 bundle 内保存 `inputs/arxml.arxml`、`inputs/provenance.json` 和 `arxml.json`；后者为 `arxml-project-gate-0.1`，内嵌原始 `arxml-import-0.1` 报告，保留对象 locator、工具信息、unsupported 和未知边界。

- 畸形 XML、版本不匹配或生产者 hash 不符：输出创建前拒绝，退出 1。
- 悬空引用、重复身份或 DEST 冲突：ARXML 阶段 failed，通信 skipped，项目退出 2。
- 不支持语义：原导入 coverage=partial 原样保留；项目增加 `ARXML-PROJECT-UNSUPPORTED` ERROR 并阻止通信，不把 partial 当成已验收。
- 正常受限输入：静态门通过后执行原有 DBC/intent/vectors 通信路径。XML 与通信模型分别验收；未证明 SWC 端口与 DBC/BSW 配置的跨源一致性。

审查重新解析保存的 XML 与生产者快照，核对阶段报告与语义摘要，再生成引用；同时引用覆盖范围、未知边界和错误严重度。迁移后的重审不访问原工程输入。即使库存 hash 随被篡改的阶段报告一起更新，只要报告不符合输入快照，重审仍拒绝。

项目比较沿用 `project-comparison-0.2`，0.4 的 comparison_basis 新增 ARXML 语义摘要。相同定义/相同受限语义才能比较验收结果；周期变化、悬空引用或覆盖改变会产生 not-comparable，避免两个通信 passed 掩盖配置变化。格式空白和 UUID 变化不改变摘要。查看具体对象差异，请对两个 bundle 的 `inputs/arxml.arxml` 使用 `compare-arxml`；公开场景还归档独立 `semantic-diff.json`，周期变更只定位到 `TMT_WindowControl_Step`。

P21 对象图入口继续要求项目 0.3；使用原 `project-declared.json` 分析 DBC/intent 的依赖影响。0.4 不把缺失的 COM/IPdu/PduR/CanIf ECUC 补造为对象图。

公开脚本运行正常、悬空引用、周期变化、未知元素四个真实 CLI 案例；变体标注 synthetic-mutation，保留基线 hash；随后删除脚本创建的输入并移动整个目录，验证 manifest、原审查引用、重新审查、比较引用和内嵌 XML。Windows/Ubuntu CI 上传 `arxml-project-{OS}`，完整门与实现提交见 [P22 验收表](p22-acceptance.md)。
