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
