# DracoBench Report

## Summary

- Cases: 50
- Passed: 47
- Pass rate: 94.0%
- Errors: 0
- Avg latency: 7768 ms
- Total cost: $0.046539
- Prompt tokens: 4040
- Completion tokens: 11125
- Reasoning tokens: 9900

## By Suite

| Suite | Cases | Passed | Pass rate | Avg latency | Cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| `chinese_writing` | 4 | 4 | 100.0% | 10775 ms | $0.004167 |
| `coding` | 10 | 10 | 100.0% | 9620 ms | $0.012721 |
| `debugging` | 8 | 7 | 87.5% | 9411 ms | $0.011835 |
| `instruction_following` | 7 | 6 | 85.7% | 5735 ms | $0.006185 |
| `knowledge` | 8 | 8 | 100.0% | 5658 ms | $0.002774 |
| `rag_long_context` | 3 | 3 | 100.0% | 10007 ms | $0.001843 |
| `reasoning` | 10 | 9 | 90.0% | 5838 ms | $0.007014 |

## Failure Examples

### hard-reasoning-005

- Suite: `reasoning`
- Score details: `{'matched': []}`

Output:

```text
甲、丙
```

### hard-debugging-001

- Suite: `debugging`
- Score details: `{'pattern': 'FIX:\\s*`?\\s*def\\s+add_item\\(x,\\s*items=None\\)\\s*:'}`

Output:

```text

```

### hard-if-004

- Suite: `instruction_following`
- Score details: `{'expected': '模型-评测-需要-可复现', 'actual': 'model-evaluation-needs-reproducible'}`

Output:

```text
model-evaluation-needs-reproducible
```

