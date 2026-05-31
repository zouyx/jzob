# jzob

## 自动生成热点 AI 文章

仓库新增了 GitHub Actions 工作流 `.github/workflows/hot-ai-topic.yml`，默认每天执行一次（UTC 02:00），也可手动触发以下流程：

1. 从 Google News 抓取 AI 相关热点话题；
2. 先做研究归纳，再写作与审校，生成一篇更偏深度分析的博客；
3. 将生成的 Markdown 文章写入 `_posts/` 并提交到 `master`；
4. 由现有 deploy workflow 自动构建并发布站点。

默认情况下，生成脚本会分阶段使用模型：

- research：`openai/gpt-5`
- writing：`openai/gpt-4.1`
- review：`openai/gpt-4.1`

手动触发工作流时，可分别填写 `research_model`、`writing_model`、`review_model`；如果填写旧的 `model` 输入，则会统一覆盖所有阶段。

需要在仓库 Secrets 中配置：

- `MODELS_TOKEN`：带 `models:read` 权限的 GitHub token
