# DracoBench

DracoBench 是一套个人向的大模型评测工具，目标不是再造一个公开排行榜，而是帮助我判断不同模型适合做什么，并把评测过程沉淀成可用于公众号文章的证据材料。

第一版重点覆盖：

- 知识与常识
- 逻辑推理
- Coding
- Debugging
- 指令遵循
- 中文表达与内容创作
- 长上下文 / RAG
- 成本、速度、失败率

后续难度升级路线见 [docs/difficulty-roadmap.md](docs/difficulty-roadmap.md)。

## 快速开始

`.env` 中需要包含：

```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

验证样例用例：

```bash
PYTHONPATH=src python3 -m dracobench validate --cases cases/v0.1/smoke.jsonl
```

列出用例：

```bash
PYTHONPATH=src python3 -m dracobench list --cases cases/v0.1/smoke.jsonl
```

查看 hard 用例集：

```bash
PYTHONPATH=src python3 -m dracobench validate --cases cases/v0.1/hard.jsonl
PYTHONPATH=src python3 -m dracobench review-html \
  --cases cases/v0.1/hard.jsonl \
  --out docs/review/v0.1-hard.html \
  --title "DracoBench v0.1-hard Case Review"
```

通过 OpenRouter 跑一次 smoke benchmark：

```bash
PYTHONPATH=src python3 -m dracobench run \
  --model <openrouter-model-slug> \
  --cases cases/v0.1/smoke.jsonl
```

为了提升正式评测的可复现性，可以固定 provider：

```bash
PYTHONPATH=src python3 -m dracobench run \
  --model <openrouter-model-slug> \
  --provider-only <provider-slug> \
  --no-fallbacks \
  --cases cases/v0.1/smoke.jsonl
```

建议区分两种运行口径：

```bash
# efficiency mode: 观察低输出预算下的成本、延迟、截断和稳定性
PYTHONPATH=src python3 -m dracobench run \
  --model <openrouter-model-slug> \
  --cases cases/v0.2/challenge.jsonl \
  --max-tokens 1024

# ability mode: 给 reasoning-heavy 模型更公平的输出预算
PYTHONPATH=src python3 -m dracobench run \
  --model <openrouter-model-slug> \
  --cases cases/v0.2/challenge.jsonl \
  --max-tokens 4096
```

默认输出：

- `runs/*.jsonl`：逐题明细，包含 prompt hash、原始输出、token usage、latency、score、error。
- `reports/*.md`：适合继续整理成文章的 Markdown 摘要。
- `reports/*.html`：默认生成的可视化评测结果页，用于 review 分数、成本、token、失败样例和逐题明细。

也可以给已有 run 文件补生成 HTML：

```bash
PYTHONPATH=src python3 -m dracobench report-html \
  --run runs/<run-file>.jsonl \
  --out reports/<report-file>.html
```

## 部署报告到 Vercel

仓库已包含 Vercel 静态部署配置：

- `vercel.json`：构建 `public/` 静态站点，并把 `/`、`/reports` 指向 `reports/index.html`。
- `.vercelignore`：部署时排除 `.env`、缓存、测试目录等本地文件。
- `scripts/prepare_vercel_static.py`：从当前 `reports/` 和 `runs/` 中复制 v0.3 challenge100 ability16384 的最终结果到 `public/`。

部署前先生成静态站点：

```bash
PYTHONPATH=src python3 scripts/prepare_vercel_static.py
```

本地预览可以直接打开：

```bash
python3 -m http.server 8765 --directory public
```

然后访问：

```text
http://127.0.0.1:8765/reports/index.html
```

使用 Vercel CLI 部署预览版本：

```bash
vercel deploy . -y
```

如果需要生产发布，再显式使用：

```bash
vercel deploy . --prod -y
```

## 当前边界

- 代码题 scorer 会执行模型生成的 Python 代码。当前只做了临时目录和 timeout，正式扩大 coding/debugging 评测前应加入更强沙箱。
- LLM-as-judge 尚未默认启用。第一版优先使用 exact、regex、JSON schema lite、文本规则、单元测试等可复现判分。
- OpenRouter 默认会自动做 provider routing。正式评测需要记录并尽量固定 provider 策略。

## 远端仓库

后续代码可以同步到：

https://github.com/dracohu2025-cloud/dracobench

不会自动 commit 或 push；需要明确要求后再执行 git 操作。
