# jzob — Agent 使用说明

Joe Zou 的个人技术博客。Jekyll 站点，托管于 GitHub Pages，文章以中文为主。

## 命令

```sh
# 本地开发
jekyll serve                          # 启动于 http://localhost:4000

# 生产构建
JEKYLL_ENV=production jekyll build --destination=_deploy

# 运行 AI 文章生成器测试
python -m unittest discover tests -v
```

## CI/CD

- **部署**（`.github/workflows/deploy.yml`）：推送至 `master` 或 `pages-*` 分支时触发。使用 Jekyll 4.4.1、Ruby 3.3 构建，通过 SSH 部署至 `zouyx/zouyx.github.io`。
- **AI 文章生成**（`.github/workflows/hot-ai-topic.yml`）：每日 UTC 02:00 定时执行。抓取 Google News RSS，经 3 阶段流水线（研究 → 写作 → 审校）调用 GitHub Models API，提交至 `_posts/` 后触发部署。
- **并发控制**：`hot-ai-topic` 组，`cancel-in-progress: false` — 不允许重叠执行。
- **所需密钥**：`MODELS_TOKEN`（需 `models:read` 权限的 GitHub token）。部署需要 `DEPLOY_KEY`（SSH 密钥）。

## AI 文章生成（Python）

入口：`script/generate_hot_ai_post.py`。依赖 `MODELS_TOKEN` 环境变量。数据源通过 `HOT_AI_SOURCE` 配置（默认 `arxiv`，支持 `hackernews`、`arxiv`、`google`，可逗号组合如 `hackernews,arxiv`）。每次运行取 `HOT_AI_TOPIC_COUNT` 条（默认 3）最高分话题各生成一篇。三阶段默认模型：

| 阶段     | 默认模型            | 温度  |
|----------|-------------------|-------|
| 研究     | `openai/gpt-5`    | 无    |
| 写作     | `openai/gpt-4.1`  | 0.8   |
| 审校     | `openai/gpt-4.1`  | 0.2   |

可通过 `MODELS_RESEARCH_MODEL`、`MODELS_WRITING_MODEL`、`MODELS_REVIEW_MODEL` 单独覆盖，或用旧版 `MODELS_MODEL` 统一覆盖。

`validate_analysis()` 强制执行的质量门禁：
- 不少于 3 条事实、1 个不确定点、2 个关联报道来源
- 正文不少于 1400 字，13 个必需标题齐全
- 原始新闻链接恰好出现一次
- 空泛短语不超过一次

生成的文章文件名格式为 `YYYY-MM-DD-ai-{slug}.md`，分类为 `AI`。

## 博客规范

- 文章存放于 `_posts/`。文件名格式：`YYYY-MM-DD-分类-标题.md`。
- AI 自动文章使用前缀 `ai`，分类为 `AI`。
- Front matter 必须包含 `layout`、`title`、`permalink`、`category`、`tags`、`excerpt`。示例见 `_posts/2026-04-25-ai-deepseek-v4-vs-chatgpt-claude-gemini.md`。
- 站点时区：`Asia/Shanghai`。
- 使用 `jekyll-paginate-v2` 分页（每页 5 篇文章）。

## 测试

- 测试文件在 `tests/`，使用标准 `unittest`。
- 执行单个文件：`python -m unittest tests.test_generate_hot_ai_post`
- 测试已 mock API 调用 — 无需真实 token。
- `hot-ai-topic.yml` 中的工作流默认值必须与 Python 默认值保持一致（`test_workflow_default_models_match_script_defaults` 测试会验证这一点）。

## 目录结构

```
_posts/          → 博客文章（新文章放这里）
script/          → AI 文章生成器 + 背景知识 JSON
tests/           → 生成器的单元测试
_includes/       → Jekyll 局部模板
_layouts/        → 页面模板
_plugins/        → 自定义 sitemap 生成器
_config.yml      → Jekyll 配置（时区、分页、插件）
llm.txt          → 站点概览的 LLM 发现文件
```
