# DracoBench Report

## Summary

- Cases: 7
- Passed: 4
- Pass rate: 57.1%
- Errors: 0
- Avg latency: 6311 ms

## By Suite

| Suite | Cases | Passed | Pass rate | Avg latency |
| --- | ---: | ---: | ---: | ---: |
| `chinese_writing` | 1 | 0 | 0.0% | 8829 ms |
| `coding` | 1 | 1 | 100.0% | 3750 ms |
| `debugging` | 1 | 0 | 0.0% | 4091 ms |
| `instruction_following` | 1 | 1 | 100.0% | 4067 ms |
| `knowledge` | 1 | 0 | 0.0% | 13035 ms |
| `rag_long_context` | 1 | 1 | 100.0% | 3228 ms |
| `reasoning` | 1 | 1 | 100.0% | 7180 ms |

## Failure Examples

### knowledge-common-001

- Suite: `knowledge`
- Score details: `{'matched': []}`

Output:

```text

```

### debugging-python-001

- Suite: `debugging`
- Score details: `{'pattern': 'FIX:\\s*for\\s+i\\s+in\\s+range\\(len\\(items\\)\\)\\s*:'}`

Output:

```text
bug：`range(len(items) + 1)` 会多产生一个等于 `len(items)` 的索引，导致访问越界。

最小修复：把 `+ 1` 去掉。

FIX: `for i in range(len(items)):`
```

### zh-writing-001

- Suite: `chinese_writing`
- Score details: `{'missing': ['模型评测', '可复现'], 'present_forbidden': [], 'char_count': 0, 'length_ok': True}`

Output:

```text

```

