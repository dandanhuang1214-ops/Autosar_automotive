# P30 六类冻结问题评测

当前模型适配已通过双平台工程验收，但模型解释质量仍待验收。本轮在提示 0.4 之后冻结新问题，复用已经保存、可以离线复验的项目证据，不重新执行 ECU 或 CAN 实验。

## 问题与计量

问题清单位于 [p30-evaluation-cohort-v1.json](../research/p30-evaluation-cohort-v1.json)：配置保护拒绝、配置影响对象、CAN 超时、诊断负响应、物理 ECU 缺证据、历史运行替换。前四类 gold 是明确的 artifact/pointer/类型化值；缺证据要求模型返回结构化 unassessed；历史替换必须在推理前被工程复验拒绝。

这组问题由代理根据既有证据编写，与早先六次提示开发调用分开，在查看本组模型输出前冻结。它不是独立人工 gold，也没有用 P24 冻结题库调参。看到结果后不能继续宣称本组是未见测试；改提示或选事实策略应另建开发试验和后续验收组。

- 确定性事实：完整项目复验且 gold 唯一匹配，保存请求摘要。
- 上下文覆盖：gold 有多少实际进入 24 条事实窗口；漏选单独记录。
- 模型引用：通过原严格引用门后计算 gold recall，引用通过不代表答全。
- 缺证据：只有有效的模型 unassessed 才记为结构化拒答；校验器拒绝、服务不可用不计模型正确拒答。
- 检索：与无检索模式使用同题、同模型、同提示；记录来源数量、逐字摘录通过数及资料缺口。没有人工相关性 gold，不能将“有命中”称为检索准确。
- 历史替换：记录调用前拒绝，不放入模型准确率分母。
- 自然语言、因果解释、资料适用性和人工可用性保持 unassessed。

## 可重复入口

先具备清单引用的本地 P29 归档；它们不随公共仓库分发。路径变化时复制清单并显式更新路径，重新冻结，不能覆盖旧 manifest。完整模型评测需要工作台 CAN 可选依赖才能复验 CAN 项目。

```bash
PYTHONPATH=src .venv/bin/python scripts/assess_model_explanation.py --root . freeze \
  --spec docs/research/p30-evaluation-cohort-v1.json \
  --output output/p30-evaluation/frozen-v1.json \
  --model qwen3.5:2b \
  --model-digest 324d162be6ca5629ae4517c8710434d0bd2d665bc94dbad46e9af8fbf8a2f0df
```

冻结会复验每份项目，核对预先编写的 gold，保存完整 bundle 文件集合摘要、事实请求摘要、模型摘要、提示版本和适配/评分脚本摘要。将输出的 manifest_sha256 单独记录，再运行：

```bash
PYTHONPATH=src .venv/bin/python scripts/assess_model_explanation.py --root . run \
  --manifest output/p30-evaluation/frozen-v1.json \
  --manifest-sha256 <冻结时记录的摘要> \
  --output output/p30-evaluation/new-trial \
  --ollama-url <可达的Ollama源地址> \
  --knowledge-url <可达的知识助手源地址>
```

输出目录必须不存在。代码或证据变化先拒绝；每次推理归档均离线重放后才评分，中途失败保留原文件及已完成 partial，不伪造完整结果。省略 knowledge-url 只运行项目事实模式。最终 summary 保留逐题结果，不把工程保护、上下文覆盖和语义质量合并成一个“准确率”。

当前原 Docker backend 内部地址为 `http://ollama:11434` / `http://api:8000`，不向宿主机默认开放。现场复用原 API 镜像的 Python 3.12，同时只读挂载工作台现有 `.venv/lib/python3.12/site-packages`；首次未挂载依赖的启动因缺 cantools 失败且没有模型调用。依赖导入和 bitstruct 编解码实测后再运行，不安装新依赖或下载模型。不同机器必须重新验证解释器/本地扩展兼容性，不能假定任意虚拟环境均可复用。

本轮冻结摘要：`71d4396eb2913a6b0c1ec832d2eacba68e65a01376e4777b672793e8121ac6a4`。完整证据保存于 `output/p30-evaluation/`，资料原文留在本地忽略目录。实测结果和后续 CI 结论见 P30 验收表及完整报告。

## 本轮执行结论

五题分别执行无检索/检索两种模式，共十次真实推理，均 refused；历史替换在推理前拒绝。所有十份调用归档离线复验通过。前三类问题的 gold 上下文覆盖为 0/2，诊断为 2/2；缺证据题没有有效模型拒答。此结果定位了上下文漏选与输出契约两个问题，不支持复杂工程解释已可用的结论。实现 `8735bc3b672bd4d95902fb5abcb431d88248efc1` / [run `37419810449`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37419810449) 七 job 全部 success 验收的是评测实现，具体质量结果见完整报告。


## 提示 0.5 后的新冻结集

[p30-evaluation-cohort-v2.json](../research/p30-evaluation-cohort-v2.json)包含五个新问题与两个明确标注的已见控制题：前后类型化值、诊断受影响对象、CAN ID 不匹配、诊断超时、生成来源缺失，加上负响应/历史替换控制。首次 gold 把 XML 数字文本写为 JSON 数字，冻结入口严格拒绝；核对原值为字符串后改正，模型尚未调用。此 gold 修正不用于修改解析器或放宽类型校验。

七题共 11 项目标事实，全部进入 0.5 上下文。模型和提示固定后分别冻结两个已安装模型，分开保存 manifest 摘要，不下载新权重。先运行 qwen3.5 的项目/检索配对，再运行 qwen3-vl 的同题对照，避免同时加载干扰延迟。原样保留所有失败；自然语言和资料相关性仍需人工评价。

## 冻结 v2 结果（2026-10-08）

`qwen3.5:2b`：12 次配对生成（6 有效问题 × 项目/检索），11 次输出截断拒绝、1 次服务超时，0 次通过；12/12 归档离线复验通过，gold 覆盖 11/11。历史替换控制在推理前拒绝。

`qwen3-vl:2b` 同一冻结清单有 11 份通过离线复验的归档：7 次请求超时、4 次 HTTP 400；第 12 份及 partial/summary 含空字节，原文件保留。没有有效完整 summary 或模型答复，不能与 qwen3.5 比通过率。模型适用性和资源限制见[适用性评估](p30-model-suitability.md)。P30 质量门未通过，阶段保持 implementing。

人工验收的执行顺序和逐题记录见[人工语义与资料适用性验收](p30-human-review-guide.md)；当前均待独立审阅，不由代理填报通过。

提示 0.7 绑定 8K / 4096-token 预算，已见问题正式 adapter 仍出现 `done_reason=length`，被拒绝且可离线复验。直接修改 payload 的一个请求虽完成，但不能视作该 adapter 门通过。下一轮保持每项记录响应终止原因、prompt/eval token 和时间；不将已见问题用于未见质量分。


### P30：提示 0.8 的 qwen3-vl 思考模式适配（2026-10-08）

- qwen3-vl 本机 identity families=[qwen3vl] 经运行时核对后，在提示 0.8 使用 think=false；qwen3.5 和提示 0.1–0.7 不变，失败/成功均保存实际 model-input、身份与服务输出。不是所有 thinking 模型共用一个强制开关。
- 同一已见 qwen3-vl 问题的提示 0.7 默认调用用尽 4096 token、message.content 为空；提示 0.8 适配器调用约 25.7 秒结束，1129 prompt / 348 output tokens，结束原因为 stop。输出通过模型 schema、严格 fact_id/typed-value 校验，两个 gold 事实均被引用，正式归档离线复验通过。自然语言解释未经人工审核，prose 仍 unassessed；单个已见开发样本不是质量评估。
- 新增模型家族策略和归档复验回归。当前本地全量 420 tests（418 passed、2 环境跳过），15 项 P30 模型定向通过；隔离安装 12 协议场景/归档复验通过；Ruff、54-source mypy、57 schemas/76 bound/25 syntax-only、topology、pip check、compileall 均通过。
- 提示 0.8 的实现 `cb6294b8a9161647733c636ed07411b0975b1389` / [run `37733947430`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37733947430) 七 job 全部 success。下一项用新冻结问题配对 qwen3.5 与 qwen3-vl，再完成独立人工语义和资料适用性审阅；P30 继续 implementing。


### P30：提示 0.8 远端验收与六题已见回归（2026-10-08）

- 实现 cb6294b8a9161647733c636ed07411b0975b1389 / [run 37733947430](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37733947430) 七个 job 全部 success：runtime-currency 113169146393；core-contracts Windows 113169146725 / Ubuntu 113169146661；controlled-rejections Windows 113170820518 / Ubuntu 113170820559；runtime-evidence Windows 113170820597 / Ubuntu 113170820534。
- 全量 420 tests（418 passed、2 环境跳过）；15 项模型专项；隔离安装后 12 项协议场景及归档复验、Ruff、54-source mypy、57 schemas/76 bound/25 syntax-only examples、CI topology、pip check、compileall 通过。
- 新冻结 v2 全部题目明确为已见回归，共六个项目模式问题、一个历史 preflight 控制。qwen3-vl 六题中三题 structured pass、三题因 4096-token length 截断拒绝；gold recall 通过项为 1.0。7/7 行（含历史控制）归档复验 passed。初次从宿主 Ollama 地址运行一题因 DNS blocked，该失败另存，没有计为模型拒绝；正式运行在原 backend 容器网络完成。
- 一条 `diagnostic-affected-objects` 正式调用 25.7 秒、1129 prompt / 348 output tokens；schema 及两个 gold 引用通过。其中文解释没有经人工语义核对，仍为 unassessed。旧测试不是新未见评测，也不能替代人工 review。
- 下一项：冻结一批未参与提示调试的具体工程问题，做 qwen3.5 与 qwen3-vl 完整配对并记录结束原因/token/耗时；完成独立人工语义和资料适用性记录。P30 仍 implementing。
