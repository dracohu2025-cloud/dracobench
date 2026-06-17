# DracoBench 难度升级路线

当前 `v0.1-hard` 已经能区分部分模型问题，但对强代码模型仍然偏温和。下一阶段建议新增 `v0.2-challenge`，目标不是扩大题量，而是提高区分度和诊断价值。

## 目标

- 让强模型不再轻易接近满分。
- 更准确地区分“会写代码”和“会调试真实问题”。
- 增加对过度思考、空输出、格式漂移、资料外幻觉的检测。
- 让每次结果都能直接产出 HTML，作为公众号文章素材。

## 建议新增题型

| 方向 | 难度升级方式 | 判分 |
| --- | --- | --- |
| Debugging | 多文件上下文、失败测试、隐性状态 bug、并发/缓存/边界问题 | patch tests / regex 兜底 |
| Coding | 非模板业务函数、组合边界条件、输入脏数据、性能约束 | 单元测试 + hidden-style cases |
| Reasoning | 多约束表格推理、条件反转、不可满足约束识别 | exact / contains_any |
| RAG | 多段资料互相冲突、要求引用、资料外拒答 | text rules + 后续 citation scorer |
| 指令遵循 | 嵌套 JSON、CSV/Markdown 混合格式、禁止翻译、禁止解释 | schema / regex / text rules |
| 中文表达 | 观点密度、反营销表达、公众号标题与导语质量 | rubric + 人工抽检 |
| 稳定性 | 同题多次运行，观察格式漂移和空输出 | repeated runs |

## 优先级

1. 先补 20 道 `debugging` 和 `coding` challenge 题，重点拉开代码模型差距。
2. 再补 10 道 RAG/长上下文题，测试“只根据资料回答”和拒答。
3. 最后补中文写作 rubric，把主观题从简单关键词检查升级为可解释评分。

## 输出要求

从现在开始，每次正式 run 都应输出：

- `runs/*.jsonl`
- `reports/*.md`
- `reports/*.html`

最终和用户讨论结果时优先给 HTML 链接，再补简短文字摘要。

