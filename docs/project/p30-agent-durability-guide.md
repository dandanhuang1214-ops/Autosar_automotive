# P30 只读 Agent checkpoint、暂停与幂等恢复

状态：**local-accepted / remote CI pending**。本门只增加只读 Agent 的持久状态与恢复协议，不注册写入、执行或硬件工具，也不改变 v1 模型质量 3/5 failed 结论。

## 已实现能力

Agent 可由调用方指定在本次调用完成若干个成功只读工具后暂停。暂停只发生在完整 tool event 已写入内存、下一次模型调用尚未开始的安全边界：

```text
model action -> read tool passed -> checkpoint(paused)
                                  |
                                  +-> resume -> next model action -> trace 或下一 checkpoint
```

checkpoint 使用 `readonly-agent-checkpoint-0.1`，恢复结果使用 `readonly-agent-resume-0.1`。原有 `readonly-agent-trace-0.1` 保持兼容；不使用暂停参数的既有调用和 trace 验签不变。

checkpoint 固定并离线复验：

- goal、完整事件哈希链、observation、累计 token/调用/执行时间；
- 模型名称与 digest、Ollama 服务版本；
- 完整只读工具 manifest 和预算；
- 项目报告字节摘要；
- 可选知识服务 origin 与 digest-bound 策略 ID；
- resume 次数与父 checkpoint ID。

恢复前只要报告、策略、知识 origin、模型 identity、服务版本、工具或预算发生变化，就 fail closed。报告在 registry 创建后发生任何字节变化，也会在项目工具执行前拒绝。

## 幂等语义

`resume-readonly-agent` 将“同一 checkpoint + 同一不可变 output 路径”作为完成态幂等键：

1. output 不存在时，恢复执行并保存 checkpoint-bound resume envelope；
2. output 已存在时，先复验 checkpoint、当前 registry binding、恢复参数和保存结果；
3. 复验通过后直接返回原结果，不再访问模型、项目工具或知识服务；
4. output 属于其他 checkpoint、已篡改、是 symlink、绑定上下文不同或同一幂等键被换参数则拒绝。

这是**已完成恢复的重试幂等**，不是分布式 exactly-once。若进程在模型/只读工具返回后、resume envelope 落盘前崩溃，重试仍可能重新调用模型或只读工具；当前没有副作用，因此不会重复写配置或触发硬件。并发 claim、租约、事务型 outbox 和写工具 idempotency key 尚未实现，开放写入前必须另行完成。

暂停等待时间不计入执行墙钟预算；checkpoint 保存的是各段实际执行时间累计值。恢复继续消耗原总 token、model-call、tool-call、step 和执行时间预算，不能借暂停重置额度。

## CLI

先在一个成功 read tool 后暂停：

```bash
python -m automotive_workbench.cli run-readonly-agent \
  output/project/bundle/project-report.json \
  --goal "核对项目为什么被阻断" \
  --model qwen3.5:2b \
  --ollama-url http://127.0.0.1:11434 \
  --pause-after-tool-calls 1 \
  --output output/agent/checkpoint.json

python -m automotive_workbench.cli verify-readonly-agent-checkpoint \
  output/agent/checkpoint.json
```

恢复并保存不可变 resume envelope：

```bash
python -m automotive_workbench.cli resume-readonly-agent \
  output/project/bundle/project-report.json \
  output/agent/checkpoint.json \
  --ollama-url http://127.0.0.1:11434 \
  --output output/agent/resume.json

python -m automotive_workbench.cli verify-readonly-agent-resume \
  output/agent/checkpoint.json \
  output/agent/resume.json
```

如果起始调用绑定了知识服务，恢复时必须再次提供相同 `--knowledge-url` 和同一 `--knowledge-policy`。恢复也可再次指定 `--pause-after-tool-calls`，形成带父 checkpoint 的下一暂停点。

## 本地验证

- 全量 457 tests 通过，2 项环境条件跳过；15 项 Agent runtime 定向测试通过。
- 64 schemas / 77 schema-bound / 25 syntax-only examples 通过。
- Ruff、scoped mypy、compileall、pip check、diff check 通过。
- 源码合成 HTTP 场景完成 pause、离线 checkpoint 复验、resume、服务不可用下完成态重试及停服 resume 复验。
- 隔离 wheel 环境重复通过同一场景；wheel SHA-256 `4836288bd3d03447084c5dafc6b32a5413f02533f3922b814a5d86dd155d6d7c`。

远端 CI 尚未运行，因此本门当前不能写成 remote-accepted。下一门是在不开放写/硬件工具的前提下，定义可审计的 approval request/decision 状态、拒绝与过期语义；只有副作用工具具备独立授权、事务边界和幂等键后，才讨论执行型 Agent。
