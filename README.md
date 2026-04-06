# jzob

[![Build Status](https://travis-ci.org/zouyx/jzob.svg?branch=master)](https://travis-ci.org/zouyx/jzob)

## 自动生成热点 AI 文章

仓库新增了 GitHub Actions 工作流 `.github/workflows/hot-ai-topic.yml`，可定时或手动执行以下流程：

1. 从 x.com 搜索 AI 相关热点帖子并挑选互动度最高的话题；
2. 调用 GitHub Copilot / GitHub Models 生成一篇深度分析博客；
3. 将生成的 Markdown 文章写入 `_posts/` 并提交到 `master`；
4. 由现有 deploy workflow 自动构建并发布站点。

需要在仓库 Secrets 中配置：

- `X_BEARER_TOKEN`：x.com API Bearer Token
- `GITHUB_MODELS_TOKEN`：带 `models:read` 权限的 GitHub token
