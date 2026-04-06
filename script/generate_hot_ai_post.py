#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = REPO_ROOT / "_posts"
DEFAULT_QUERY = '(AI OR "artificial intelligence" OR OpenAI OR Anthropic OR Claude OR Gemini OR DeepSeek OR Copilot) lang:en -is:retweet'
X_API_BASE_URL = os.environ.get("X_API_BASE_URL", "https://api.x.com/2").rstrip("/")
MODELS_API_URL = os.environ.get("GITHUB_MODELS_API_URL", "https://models.github.ai/inference/chat/completions")
DEFAULT_MODEL = "openai/gpt-4.1-mini"
LIKE_WEIGHT = 1
RETWEET_WEIGHT = 2
QUOTE_WEIGHT = 2
REPLY_WEIGHT = 3
MAX_ANALYSIS_TOKENS = 2200


@dataclass
class HotPost:
    post_id: str
    text: str
    author_name: str
    author_username: str
    created_at: str
    url: str
    score: int
    metrics: dict[str, int]


def request_json(url: str, *, token: str, payload: dict | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "jzob-hot-ai-topic-generator",
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, headers=headers, data=data)
    try:
        with urllib.request.urlopen(request) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Request failed: {url}\nHTTP {exc.code}\n{body}") from exc


def clean_text(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def score_post(metrics: dict[str, int]) -> int:
    return (
        int(metrics.get("like_count", 0)) * LIKE_WEIGHT
        + int(metrics.get("retweet_count", 0)) * RETWEET_WEIGHT
        + int(metrics.get("quote_count", 0)) * QUOTE_WEIGHT
        + int(metrics.get("reply_count", 0)) * REPLY_WEIGHT
    )


def select_hot_post(payload: dict) -> HotPost:
    posts = payload.get("data") or []
    users = {user["id"]: user for user in payload.get("includes", {}).get("users", [])}
    if not posts:
        raise RuntimeError("X API returned no AI posts to analyze.")

    candidates: list[HotPost] = []
    for post in posts:
        user = users.get(post.get("author_id", ""), {})
        username = user.get("username", "unknown")
        metrics = post.get("public_metrics") or {}
        candidates.append(
            HotPost(
                post_id=post["id"],
                text=clean_text(post.get("text", "")),
                author_name=user.get("name", username),
                author_username=username,
                created_at=post.get("created_at", ""),
                url=f"https://x.com/{username}/status/{post['id']}",
                score=score_post(metrics),
                metrics=metrics,
            )
        )

    return max(candidates, key=lambda item: (item.score, item.created_at))


def fetch_hot_ai_post() -> HotPost:
    token = os.environ["X_BEARER_TOKEN"]
    params = {
        "query": os.environ.get("HOT_AI_TOPIC_QUERY") or DEFAULT_QUERY,
        "max_results": os.environ.get("HOT_AI_TOPIC_MAX_RESULTS") or "10",
        "sort_order": "relevancy",
        "tweet.fields": "created_at,lang,public_metrics",
        "expansions": "author_id",
        "user.fields": "name,username",
    }
    query = urllib.parse.urlencode(params)
    payload = request_json(f"{X_API_BASE_URL}/tweets/search/recent?{query}", token=token)
    return select_hot_post(payload)


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:60] or f"ai-topic-{datetime.now().strftime('%Y%m%d')}"


def strip_code_fences(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return content


def generate_analysis(post: HotPost) -> dict[str, str]:
    token = os.environ["GITHUB_MODELS_TOKEN"]
    model = os.environ.get("GITHUB_MODELS_MODEL") or DEFAULT_MODEL
    payload = {
        "model": model,
        "temperature": 0.7,
        "max_tokens": MAX_ANALYSIS_TOKENS,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are GitHub Copilot writing for a personal engineering blog built with Jekyll. "
                    "Return only valid JSON with keys: title, slug, excerpt, body. "
                    "The blog must be in Simplified Chinese, insightful, opinionated but honest, and based on the supplied X post."
                ),
            },
            {
                "role": "user",
                "content": (
                    "请基于下面这条在 x.com 上互动度最高的 AI 相关帖子，生成一篇适合技术博客发布的深度分析文章。\n"
                    "要求：\n"
                    "1. 返回 JSON 对象，字段必须是 title、slug、excerpt、body。\n"
                    "2. title 不超过 50 个字；slug 使用小写英文和连字符；excerpt 1-2 句话。\n"
                    "3. body 仅返回 Markdown 正文，不要包含 YAML front matter。\n"
                    "4. 正文至少包含这些二级标题：事件概览、为什么值得关注、技术与产业影响、工程团队可以怎么做、风险与争议、总结。\n"
                    "5. 明确区分“已知事实”和“推断/判断”，不要编造未提供的数据。\n"
                    "6. 在正文中保留且只保留一次原始帖子链接。\n\n"
                    f"作者：{post.author_name} (@{post.author_username})\n"
                    f"发布时间：{post.created_at}\n"
                    f"互动数据：{json.dumps(post.metrics, ensure_ascii=False)}\n"
                    f"帖子内容：{post.text}\n"
                    f"原始链接：{post.url}\n"
                ),
            },
        ],
    }
    response = request_json(MODELS_API_URL, token=token, payload=payload)
    content = response["choices"][0]["message"]["content"]
    analysis = json.loads(strip_code_fences(content))
    analysis["slug"] = slugify(analysis.get("slug") or analysis.get("title", ""))
    return analysis


def yaml_string(value: str) -> str:
    return json.dumps((value or "").strip(), ensure_ascii=False)


def render_post(post: HotPost, analysis: dict[str, str]) -> str:
    now = datetime.now()
    title = analysis["title"].strip()
    slug = slugify(analysis.get("slug") or title)
    excerpt = re.sub(r"\s+", " ", analysis.get("excerpt", "")).strip()
    body = analysis["body"].strip()
    permalink = f"/posts/{now:%Y/%m/%d}/{slug}.html"
    created_at = post.created_at.replace("T", " ").replace("Z", " UTC")
    return f"""---
layout: post
title: {yaml_string(title)}
permalink: {permalink}
category: AI
tags:
  - AI
  - x.com
  - GitHub Copilot
excerpt: {yaml_string(excerpt)}
---

> 本文由 GitHub Actions 自动抓取 x.com 热门 AI 话题，并调用 GitHub Copilot / GitHub Models 生成初稿。
>
> 热点来源：[@{post.author_username}]({post.url}) · 发布时间：{created_at}

{body}
"""


def already_generated(posts_dir: Path, post: HotPost) -> bool:
    marker = post.url
    for path in posts_dir.glob("*.md"):
        with path.open(encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if marker in line:
                    return True
    return False


def write_post(posts_dir: Path, analysis: dict[str, str], content: str) -> Path:
    filename = f"{datetime.now():%Y-%m-%d}-AI-{analysis['slug']}.md"
    path = posts_dir / filename
    suffix = 1
    while path.exists():
        path = posts_dir / f"{datetime.now():%Y-%m-%d}-AI-{analysis['slug']}-{suffix}.md"
        suffix += 1
    path.write_text(content, encoding="utf-8")
    return path


def write_outputs(post_path: Path, analysis: dict[str, str], hot_post: HotPost) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"post_file={post_path.relative_to(REPO_ROOT)}\n")
        handle.write(f"post_title={analysis['title']}\n")
        handle.write(f"source_url={hot_post.url}\n")


def main() -> int:
    POSTS_DIR.mkdir(exist_ok=True)
    hot_post = fetch_hot_ai_post()
    if already_generated(POSTS_DIR, hot_post):
        print(f"Hot topic already published for {hot_post.url}")
        return 0

    analysis = generate_analysis(hot_post)
    content = render_post(hot_post, analysis)
    post_path = write_post(POSTS_DIR, analysis, content)
    write_outputs(post_path, analysis, hot_post)
    print(f"Generated {post_path.relative_to(REPO_ROOT)} from {hot_post.url}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyError as exc:
        print(f"Missing required environment variable: {exc.args[0]}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
