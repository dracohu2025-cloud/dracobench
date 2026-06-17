# DracoBench 设计说明

## 定位

DracoBench 服务两个目标：

1. 帮助我做模型选型：判断模型在知识、推理、代码、调试、中文表达、长上下文等任务中的实际能力。
2. 帮助我组织公众号内容：评测结果应能产出模型画像、典型成功案例、典型失败案例和可解释的对比结论。

因此它不追求单一总分，而是输出能力矩阵：

- 正确率
- 指令遵循率
- JSON / 格式有效率
- 代码测试通过率
- 平均延迟
- token 与成本
- 错误率 / retry 率
- 典型样例

## MVP 能力域

| suite | 目标 | 推荐 scorer |
| --- | --- | --- |
| `knowledge` | 事实、概念、跨领域常识 | `exact` / `contains_any` |
| `reasoning` | 多步逻辑、数学、约束推理 | `exact` / `regex` |
| `coding` | 小函数实现、算法、API 使用 | `code_python_tests` |
| `debugging` | 根据报错和代码定位 bug | `regex` / 后续 patch tests |
| `instruction_following` | JSON、Markdown、字数、禁止项 | `json_schema_lite` / `text_rules` |
| `chinese_writing` | 中文解释、总结、改写、公众号风格 | `text_rules` / 后续 LLM judge |
| `rag_long_context` | 基于给定资料回答、引用、拒答 | `text_rules` / 后续 faithfulness |

## 数据流

```text
cases/*.jsonl
  -> runner
  -> OpenRouter / model
  -> scorer
  -> runs/*.jsonl
  -> reports/*.md
  -> reports/*.html
```

## OpenRouter 策略

OpenRouter 适合用作统一模型入口，但评测时必须记录路由策略：

- `model`
- `provider.only`
- `provider.order`
- `provider.allow_fallbacks`
- `provider.sort`
- `temperature`
- `max_tokens`
- `seed`
- 调用时间
- latency
- usage
- error

正式榜单不应使用 `latest` alias。若要比较同一模型在不同 provider 上的表现，应把 provider 视为实验变量。

## 判分原则

优先级：

1. 程序可验证判分：exact、regex、JSON schema、单元测试。
2. 半自动判分：文本规则、引用覆盖率。
3. LLM-as-judge：只用于开放写作和主观质量，且需要记录 judge model、rubric、位置随机化策略。
4. 人工抽检：用于校准 LLM judge 和公众号文章中的关键案例。

## 版本策略

每个 case 都需要带 `version` 和 `id`。一旦发布正式结果，旧 case 不直接改题；需要新增版本，避免历史结果不可复现。
