# P30 小模型适用性、XML 与多模态评估

2026-10-08。本轮是 P30 的事实选择、推理调用和模型适用性支持工作，不另起里程碑。实现和现场质量分别验收，最终结果见 [P30 验收表](p30-acceptance.md)。

## 当前判断

暂不启动微调。先排除上下文遗漏、推理服务不执行输出约束、生成预算不足三类工程问题，再对比模型。现有模型可继续作为受校验的实验解释器；在冻结问题、独立人工语义与资料适用性门通过前，不承担最终工程判定。

本机当前模型：`qwen3.5:2b`，服务报告 2.3B / Q8_0，文件 2,741,192,820 bytes；`qwen3-vl:2b`，2.1B / Q4_K_M，1,889,519,687 bytes；另有 `qwen3-embedding:0.6b` 用于检索。文件大小不是运行内存或显存需求。使用原有模型和镜像，没有下载权重、训练或重建知识库。两个生成模型都很小，彼此对照不能替代更强模型基线。

## 实测发现与改动

旧选择器优先排序所有 status/reason，可能将问题点名的检查排除出 24 条窗口。提示 0.5 的选择器优先精确检查身份、所问字段、受影响对象与必要状态；点名检查时不再用无关通过项填满窗口。中文原因/状态/影响/前后值有有限词映射，不宣称通用语义检索。事实仍来自完整项目复验，不从问题或模型回复制造新事实。上限保持 24 条 / 12000 字符，未选取事实继续显式记录。

生成 schema 将 fact_id 与原始 JSON 值成对限定；手册只能选来源内短原文候选；unassessed 的引用和建议列表必须为空。原严格引用校验继续独立运行，不能只相信服务执行了 schema。引用核对通过仍不认证自然语言因果关系、问题相关性或建议。

在本机 Ollama 0.31.1 / qwen3.5:2b 上，最小请求要求 schema 中 status 只能为 selected、提示故意要求 unassessed：强制 `think=false` 返回带 Markdown 的 unassessed，开启推理及省略 think 均返回 selected。上游有同类 [问题记录](https://github.com/ollama/ollama/issues/14850) 和 [修复讨论](https://github.com/ollama/ollama/pull/14660)，但其他版本的记录不能代替本机实测。提示 0.5 省略强制 think 开关，兼容不支持 thinking 的模型；0.1–0.4 的 payload 与历史事实排序保持不变。

开启推理后，开发问题在 1600 和 4096 token 预算下均出现截断，原始响应保留；这说明服务格式行为修正仍不等于真实任务可用。新版本生成上限 4096，超时和截断继续拒绝，不重试挑选成功回复。建议现场评测使用每请求 120 秒上限，耗时包含服务请求及项目复验，不能直接当作纯推理耗时。

现场开发与冻结评测保存在 `output/p30-context-validation/`；本地回归、冻结清单、模型清单与最小服务/XML 探针在 `output/p30-context-local/`。冻结 v2 有五个新问题和两个明确标注的已见控制题；代理编写 gold，不是独立人工标注。不得将控制题或已调试的问题称为未见样本。

## XML 不需要多模态

XML/ARXML 是文本。文件读取、命名空间、类型、跨文件 VALUE-REF、对象身份与完整依赖图由已有解析器和规则处理；模型接收按问题提取的、带来源的局部事实进行解释。当前平台不把完整私有 ECUC 工程直接塞入模型上下文。

文本模型可以尝试理解 XML 片段；能读标签不等于能校验 AUTOSAR。两份合成 XML 引用探针在开启推理、1200 token 的设置下均截断，因此这组观察没有证明直接 XML 分析可用，也不能据此推断模型不支持 XML 文本输入。测试数据不含用户工程。复杂工程应优先沿用确定性解析与对象图，不用模型替代解析器。

## 多模态的用途与边界

本机 `ollama show qwen3.5:2b` 列出 vision；[官方模型卡](https://huggingface.co/Qwen/Qwen3.5-2B)亦描述图像与文本输入。因此“小模型”不等于“没有视觉能力”。当前工作台解释接口只传文本，没有传图片，也没有通过图像工程分析验收。

多模态的候选用途是工程工具截图、框图、扫描 PDF、表格和诊断界面。先完成有人工 gold 的文字/OCR、端口方向、连线及图文冲突小样本，记录漏读、错连和拒答；输出仅作为待审核候选，并绑定原图、页码和坐标。需要严格引用关系时优先使用原始 XML/模型导出，而非截图。图像支持声明或一张演示图片成功，都不能证明复杂图纸分析能力。

## 何时考虑换模型或微调

| 观测到的问题 | 优先动作 | 微调决策 |
|---|---|---|
| 关键事实没进入上下文 | 修复解析、对象定位与事实选择 | 不用训练补偿缺输入 |
| 服务忽略 schema、请求截断 | 核实推理模式、服务版本、生成预算；保留失败 | 不先训练 |
| 上下文齐全仍选错对象、因果或领域概念 | 同一冻结集比较已安装模型，再安排更强基线与资源实测 | 先证明不是基础能力限制 |
| 模型已具备任务能力，但稳定违反特定风格/结构 | 收集审核过的成功与失败样本、错误分类 | 才评估小规模 SFT/LoRA |
| 资料缺失、版本不适用 | 补齐合法来源与检索/适用性证据 | 不把实时工程事实写进权重 |

微调启动前需要：明确且稳定的目标任务、可合法使用并人工审核的数据、按工程/对象族/模板隔离的训练验证测试集、未参与训练的拒答和篡改负例，以及可回滚的基础模型与适配器身份。成功标准必须同时包含引用/类型保真、拒答、语义正确性、延迟和资源开销；不能只比较训练 loss 或格式通过率。当前缺少独立人工语义 gold，尚不足以开展一项有意义的训练实验。

## 冻结 v2 的真实模型结果（2026-10-08）

实现 `c60d8af5c0cc72c632a679e06fc264747267fb95` 的远端 run `37646726266` 七个 job 全部 success。模型质量另行计量，不由 CI 通过代替。

- `qwen3.5:2b` / digest `324d162be6ca5629ae4517c8710434d0bd2d665bc94dbad46e9af8fbf8a2f0df` 完成 v2 共 12 次（6 题 × 项目/检索）：11 次因输出截断拒绝，1 次请求超时；没有一次通过结构化答案门。12/12 归档离线复验通过。历史替换在推理前拒绝。11 项 gold 全部进入事实上下文；上下文覆盖不等于答题正确。
- 检索配对没有增加通过数。原始检索来源不能替代模型结构化引用。运行时间超过多数交互期望，评测使用现有 120 秒单请求上限；没有重试或挑选回复。
- 同题 `qwen3-vl:2b` 对照未完成：模型为 2.1B / Q4_K_M，权重约 1.89 GB；`ollama ps` 实测运行时约 4.3 GB、40% CPU / 60% GPU。NVIDIA RTX 3050 Ti Laptop GPU 报告 4 GB 显存。续查 11 份归档通过离线复验：7 次 Ollama 请求超时、4 次 HTTP 400；第 12 份及 partial/summary 含空字节，不能复验。没有有效答复，不构成完整模型质量比较。客户端上限为 120 秒，提高到 300 秒会被拒绝。视觉声明不等于工作台图像路径验收。
- 小模型没有通过目标工程解释任务。可用于本地实验，但 P30 不能宣称模型解释可用。不能据这些失败单独归因于参数量。

完整本地证据位于 `output/p30-context-validation/`（qwen3.5）、`output/p30-context-vl/trial-v2-vl/`（qwen3-vl 部分结果）和 `output/p30-context-local/`（冻结、探针、历史重放）。它们没有提交到公共仓库。六份提示 0.1–0.4 真实调用归档以原项目报告重放，6/6 passed。

下一项仍属于 P30：补齐 qwen3-vl 在 120 秒适配器范围内的有效对照（若能满足预算），建立独立人工语义/资料适用性标注，并按证据缩小模型用途；只有存在可复现能力缺口且有合规标注数据时才考虑训练。P25 人工演示、商业生成与物理 ECU 门不由本轮替代。


## 提示 0.6 服务兼容性修正（2026-10-08）

提示 0.6 已实现：针对本机 grammar 重复次数限制，将生成草稿上限从 4000 收紧至 160 字符；0.1–0.5 重放保持。418 项回归（416 passed、2 环境跳过）、13 项模型测试、schema/类型/拓扑检查通过；11 份既有 0.5 真实归档修改后复验通过。隔离安装通过（12 类协议场景及归档复验）；两条提示 0.6 的已见问题开发调用均超时、2/2 归档复验通过，无有效模型答复。本次实现 `ff08e4d58bacea55d2e6ea36b1e2e9d042ef55e3` 的 [run `37713395967`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37713395967) 七 job 全部 success。

本机服务日志证明 grammar 的 `char{0,4000}` 超出重复次数限制；这是服务兼容性阻塞，不能据此归因于模型的汽车领域能力。生成限制变小，独立引用/类型校验和语义 unassessed 边界不变。

下一项仍为 P30：验收 0.6 的服务兼容性，恢复 120 秒内完整模型对照，随后按[人工验收表](p30-human-review-guide.md)完成独立语义/资料适用性审阅；质量门通过前不宣称模型解释可用。

0.6 的两条开发调用为 `diagnostic-affected-objects` 和 `missing-generated-provenance`，均为已见问题；总耗时约 130.610 / 131.339 秒（包含复验等开销，HTTP 请求上限仍为 120 秒）。两次服务超时不是模型正确拒答，不构成新冻结质量评测。较短 schema 未消除整体延迟，下一步先隔离提示处理/思考生成/排队与资源占用，再确定可行的交互预算；不直接扩大超时或宣称模型可用。

8K 诊断使用与 16K 试验相同的已见问题，修改 payload 后由既有 Ollama 返回约 30.717 秒；prompt_eval_count 为 3460、eval_count 为 292，两项目标事实均通过 schema 与事实引用校验。序列化 response 的摘要在 `output/p30-continuation-audit/context-8k-validation.json`。它是预算诊断，不是历史可重放 adapter 成功，不用于模型质量计分。


### P30：提示 0.7 上下文预算与 token 用量门（2026-10-08）

- 新冻结提示 0.7 绑定 `num_ctx=8192` / `num_predict=4096`；0.5/0.6 的提示、16K payload 与历史复验保持。结构化生成输出上限为 160 字符；完成响应缺少整型 token 计数或 `prompt_eval_count + eval_count` 超上下文时拒绝。
- 已见诊断问题在 standalone 修改 payload 探针中 8K 返回成功（30.717 秒、3460 prompt / 292 completion tokens，目标事实 2/2），但它没有完整 adapter 重放边界。正式 0.7 adapter 同问题调用 56.251 秒，输出到 4096 token 上限而被拒绝；归档 `verify-model-explanation` passed，保持实际模型 status=refused。两个过程证明 8K 请求能较快完成，也暴露生成长度受上下文/模型行为影响，不能宣称稳定质量。
- 新增 token 上下文超限负例和版本化 payload 回归。本地全量 419 tests（417 passed、2 环境跳过）；14 项模型定向、Ruff、54-source 类型检查、57 schemas/76 bound/25 syntax-only examples、拓扑、pip check、compileall、安装后 12 协议场景与归档复验均通过。
- 实现 `04e50034dc2e9b517d8fca80a244225f2847126a` / [run `37726246623`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37726246623) 七 job 全部 success：`runtime-currency` 113144964548；`core-contracts (windows-latest)` 113144964747；`core-contracts (ubuntu-22.04)` 113144964916；`controlled-rejections (windows-latest)` 113146832094；`runtime-evidence (windows-latest)` 113146832136；`controlled-rejections (ubuntu-22.04)` 113146832158；`runtime-evidence (ubuntu-22.04)` 113146832196。模型 v2 问题已见；结构化拒绝仍有发生，完整模型质量、语义及资料适用性人工审核未完成。见[模型适用性评估](p30-model-suitability.md)和[人工验收表](p30-human-review-guide.md)。
- 下一项仍为 P30：保留模型生成结束状态、输出 token 数及耗时诊断；确定 8K 下不同模型和问题类型能否在 120 秒内结构化完成，再建立新冻结集并完成独立人工语义/资料适用性审阅。质量门前不将解释结果用于工程判定。

8K 预算作为 0.7 版已接入正式适配器。对同一已见题，手工 request 试探返回 292 token，正式适配器再调用则生成达到 4096 上限、`done_reason=length`，56.251 秒拒绝。两次随机 ID 内容与校验链保持不同，属于同题诊断复验，不构成稳定重现的质量样本。受控拒绝归档可离线复验；继续保存原服务 raw response，后续应计量每题的 prompt/eval token 与终止原因。


### P30：提示 0.7 预算实现远端验收（2026-10-08）

- 实现 `04e50034dc2e9b517d8fca80a244225f2847126a` / [run `37726246623`](https://github.com/dandanhuang1214-ops/Autosar_automotive/actions/runs/37726246623) 七 job 全部 success：`runtime-currency` 113144964548；`core-contracts (windows-latest)` 113144964747；`core-contracts (ubuntu-22.04)` 113144964916；`controlled-rejections (windows-latest)` 113146832094；`runtime-evidence (windows-latest)` 113146832136；`controlled-rejections (ubuntu-22.04)` 113146832158；`runtime-evidence (ubuntu-22.04)` 113146832196。
- 419 项全量测试中 417 passed、2 环境跳过；14 项模型专项；隔离安装后的 12 项协议夹具和离线归档复验通过；Ruff、54-source mypy、57 schemas、76 schema-bound / 25 syntax-only、CI topology、pip check、compileall 通过。
- 本机正式 adapter 以 8K prompt 返回 4096-token length 截断并拒绝；该受控失败的归档离线复验通过。已见问题的直接修改 payload 探针有一次 30.717s 的 292-token 完成结果，不能代替正式 adapter 重放或新冻结问题对照。
- 本次记录属于 `[skip ci]` 文档状态回填，引用实现提交及其实际 run；新改运行代码时仍须该提交自己的 CI。
- 下一项为 P30：先确定 8K 下响应结束、耗时和 token 计数在模型/问题间的稳定范围，再冻结新评测集；完成独立人工语义及资料适用性审阅。现有代理编写的 gold 不是独立人工验收。P30 仍 implementing。


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
