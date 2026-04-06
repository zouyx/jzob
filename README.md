# jzob

[![Build Status](https://travis-ci.org/zouyx/jzob.svg?branch=master)](https://travis-ci.org/zouyx/jzob)

## 自动生成热点 AI 文章

仓库新增了 GitHub Actions 工作流 `.github/workflows/hot-ai-topic.yml`，默认每天执行一次（UTC 02:00），也可手动触发以下流程：

1. 从 Google News 抓取 AI 相关热点话题；
2. 调用 GitHub Copilot / GitHub Models 生成一篇深度分析博客；
3. 将生成的 Markdown 文章写入 `_posts/` 并提交到 `master`；
4. 由现有 deploy workflow 自动构建并发布站点。

默认情况下，生成脚本会自动从 GitHub Models 服务端目录中选择最新可用的 OpenAI GPT 模型；如需固定模型，可在手动触发工作流时填写 `model` 输入。

需要在仓库 Secrets 中配置：

- `MODELS_TOKEN`：带 `models:read` 权限的 GitHub token
