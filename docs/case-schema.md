# Case Schema

DracoBench 的用例使用 JSONL，每行一个 case。

## 最小字段

```json
{
  "id": "reasoning-001",
  "suite": "reasoning",
  "version": "0.1.0",
  "language": "zh",
  "prompt": "只回答最终数字：3 + 4 = ?",
  "scorer": "exact",
  "expected": { "answer": "7" },
  "tags": ["math", "easy"],
  "temperature": 0,
  "max_tokens": 256
}
```

## 字段说明

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | 全局唯一 ID |
| `suite` | 是 | 能力域，例如 `reasoning` |
| `version` | 是 | 用例版本 |
| `language` | 否 | `zh` / `en` / `mixed` |
| `system` | 否 | 覆盖默认 system prompt |
| `prompt` | 是 | 用户提示词 |
| `scorer` | 是 | 判分器名称 |
| `expected` | 是 | 判分器所需配置 |
| `tags` | 否 | 过滤和报告用标签 |
| `temperature` | 否 | 覆盖运行参数 |
| `max_tokens` | 否 | 覆盖运行参数 |
| `contamination_risk` | 否 | `public` / `private` / `synthetic` |

## 内置 scorer

### `exact`

```json
{ "answer": "42", "normalize": true }
```

### `contains_any`

```json
{ "answers": ["俄罗斯", "Russia"] }
```

### `regex`

```json
{ "pattern": "FIX:.*range\\(len\\(items\\)\\)", "flags": "is" }
```

### `json_schema_lite`

支持 `type`、`required`、`properties`、`additionalProperties`、`const`、`enum`、`pattern`、`minItems`、`maxItems`。

### `text_rules`

```json
{
  "required": ["模型评测", "可复现"],
  "forbidden": ["遥遥领先"],
  "max_chars": 120
}
```

### `code_python_tests`

```json
{
  "tests": [
    "assert solution.solve([2, 2, 1]) == 1",
    "assert solution.solve([4, 1, 2, 1, 2]) == 4"
  ],
  "timeout_seconds": 3
}
```

注意：该 scorer 会执行模型输出的 Python 代码。扩大使用前应加入更严格沙箱。

