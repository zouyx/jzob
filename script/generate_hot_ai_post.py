#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.error import URLError
from xml.etree import ElementTree


REPO_ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = REPO_ROOT / "_posts"
DEFAULT_QUERY = 'AI OR "artificial intelligence" OR OpenAI OR Anthropic OR Claude OR Gemini OR DeepSeek OR Copilot when:1d'
GOOGLE_NEWS_RSS_URL = os.environ.get("GOOGLE_NEWS_RSS_URL", "https://news.google.com/rss/search")
MODELS_API_URL = os.environ.get("MODELS_API_URL", "https://models.github.ai/inference/chat/completions")
DEFAULT_MODEL = "openai/gpt-5-mini"
MAX_ANALYSIS_TOKENS = 2200
MAX_SLUG_LENGTH = 60
POST_FILENAME_PREFIX = "ai"
REQUEST_TIMEOUT_SECONDS = 120


@dataclass
class HotTopic:
    topic_id: str
    title: str
    summary: str
    source_name: str
    published_at: str
    url: str


class HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def get_text(self) -> str:
        return "".join(self.parts)


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
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.load(response)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Request failed: {url}\nHTTP {exc.code}\n{body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Request failed: {url}\n{exc.reason}") from exc


def request_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "jzob-hot-ai-topic-generator"})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Request failed: {url}\nHTTP {exc.code}\n{body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Request failed: {url}\n{exc.reason}") from exc


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_html(html: str) -> str:
    parser = HTMLTextExtractor()
    parser.feed(unescape(html or ""))
    return clean_text(parser.get_text())


def normalize_published_at(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return clean_text(value)
    return parsed.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def select_hot_topic(feed_xml: str, max_results: int) -> HotTopic:
    root = ElementTree.fromstring(feed_xml)
    items = root.findall("./channel/item")
    if not items:
        raise RuntimeError("Google News RSS returned no AI topics to analyze.")

    candidates: list[HotTopic] = []
    for item in items[:max_results]:
        title = clean_text(item.findtext("title", ""))
        source_name = clean_text(item.findtext("source", "Google News")) or "Google News"
        summary = strip_html(item.findtext("description", ""))
        published_at = normalize_published_at(item.findtext("pubDate", ""))
        link = clean_text(item.findtext("link", ""))
        guid = clean_text(item.findtext("guid", link))
        if not title or not link:
            continue
        candidates.append(
            HotTopic(
                topic_id=guid or link,
                title=title,
                summary=summary,
                source_name=source_name,
                published_at=published_at,
                url=link,
            )
        )

    if not candidates:
        raise RuntimeError("Google News RSS returned no usable AI topics to analyze.")

    return candidates[0]


def fetch_hot_ai_topic() -> HotTopic:
    max_results = int(os.environ.get("HOT_AI_TOPIC_MAX_RESULTS") or "10")
    params = {
        "q": os.environ.get("HOT_AI_TOPIC_QUERY") or DEFAULT_QUERY,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }
    query = urllib.parse.urlencode(params)
    feed_xml = request_text(f"{GOOGLE_NEWS_RSS_URL}?{query}")
    return select_hot_topic(feed_xml, max_results)


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:MAX_SLUG_LENGTH] or f"ai-topic-{datetime.now(UTC).strftime('%Y%m%d')}"


def strip_code_fences(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return content


def resolve_model() -> str:
    configured_model = clean_text(os.environ.get("MODELS_MODEL", ""))
    if configured_model:
        return configured_model
    return DEFAULT_MODEL


def generate_analysis(topic: HotTopic) -> dict[str, str]:
    token = os.environ["MODELS_TOKEN"]
    model = resolve_model()
    payload = {
        "model": model,
        "temperature": 1,
        "max_completion_tokens": MAX_ANALYSIS_TOKENS,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are GitHub Copilot writing for a personal engineering blog built with Jekyll. "
                    "Return only valid JSON with keys: title, slug, excerpt, body. "
                    "The blog must be in Simplified Chinese, insightful, opinionated but honest, and based on the supplied Google News topic."
                ),
            },
            {
                "role": "user",
                "content": (
                    "请基于下面这条 Google News 中排序靠前的 AI 热门话题，生成一篇适合技术博客发布的深度分析文章。\n"
                    "要求：\n"
                    "1. 返回 JSON 对象，字段必须是 title、slug、excerpt、body。\n"
                    "2. title 不超过 50 个字；slug 提供一个简短主题短语即可，程序会统一转成 URL slug；excerpt 1-2 句话。\n"
                    "3. body 仅返回 Markdown 正文，不要包含 YAML front matter。\n"
                    "4. 正文至少包含这些二级标题：事件概览、为什么值得关注、技术与产业影响、工程团队可以怎么做、风险与争议、总结。\n"
                    "5. 明确区分“已知事实”和“推断/判断”，不要编造未提供的数据。\n"
                    "6. 在正文中保留且只保留一次原始新闻链接。\n\n"
                    f"来源：{topic.source_name}\n"
                    f"发布时间：{topic.published_at}\n"
                    f"话题标题：{topic.title}\n"
                    f"话题摘要：{topic.summary}\n"
                    f"原始链接：{topic.url}\n"
                ),
            },
        ],
    }
    response = request_json(MODELS_API_URL, token=token, payload=payload)
    content = response["choices"][0]["message"]["content"]
    analysis = json.loads(strip_code_fences(content))
    analysis["slug"] = slugify(analysis.get("slug") or analysis.get("title", ""))
    analysis["model"] = model
    return analysis


def yaml_string(value: str) -> str:
    return json.dumps((value or "").strip(), ensure_ascii=False)


def render_post(topic: HotTopic, analysis: dict[str, str]) -> str:
    now = datetime.now(UTC)
    title = analysis["title"].strip()
    slug = slugify(analysis.get("slug") or title)
    excerpt = re.sub(r"\s+", " ", analysis.get("excerpt", "")).strip()
    body = analysis["body"].strip()
    permalink = f"/posts/{now:%Y/%m/%d}/{slug}.html"
    published_at = topic.published_at or "Unknown"
    return f"""---
layout: post
title: {yaml_string(title)}
permalink: {permalink}
category: AI
tags:
  - AI
  - Google News
  - GitHub Copilot
excerpt: {yaml_string(excerpt)}
---

> 本文由 GitHub Actions 自动抓取 Google News 热门 AI 话题，并调用 GitHub Copilot / GitHub Models 生成初稿。
>
> 热点来源：[Google News / {topic.source_name}]({topic.url}) · 发布时间：{published_at}

{body}
"""


def already_generated(posts_dir: Path, topic: HotTopic) -> bool:
    marker = topic.url
    for path in posts_dir.glob("*.md"):
        with path.open(encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if marker in line:
                    return True
    return False


def already_generated_today(posts_dir: Path, now: datetime | None = None) -> bool:
    current_time = now or datetime.now(UTC)
    filename_prefix = f"{current_time:%Y-%m-%d}-{POST_FILENAME_PREFIX}-"
    return any(posts_dir.glob(f"{filename_prefix}*.md"))


def build_post_path(posts_dir: Path, slug: str, suffix: int | None = None) -> Path:
    suffix_text = f"-{suffix}" if suffix is not None else ""
    filename = f"{datetime.now(UTC):%Y-%m-%d}-{POST_FILENAME_PREFIX}-{slug}{suffix_text}.md"
    return posts_dir / filename


def write_post(posts_dir: Path, analysis: dict[str, str], content: str) -> Path:
    path = build_post_path(posts_dir, analysis["slug"])
    suffix = 1
    while path.exists():
        path = build_post_path(posts_dir, analysis["slug"], suffix)
        suffix += 1
    path.write_text(content, encoding="utf-8")
    return path


def write_github_action_output(handle, name: str, value: str) -> None:
    delimiter = "GITHUB_OUTPUT_EOF"
    while delimiter in value:
        delimiter += "_"
    handle.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")


def write_outputs(post_path: Path, analysis: dict[str, str], hot_topic: HotTopic) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        write_github_action_output(handle, "post_file", str(post_path.relative_to(REPO_ROOT)))
        write_github_action_output(handle, "post_title", analysis["title"])
        write_github_action_output(handle, "source_url", hot_topic.url)


def main() -> int:
    POSTS_DIR.mkdir(exist_ok=True)
    if already_generated_today(POSTS_DIR):
        print(f"Hot AI topic post already generated for {datetime.now(UTC):%Y-%m-%d}")
        return 0

    hot_topic = fetch_hot_ai_topic()
    if already_generated(POSTS_DIR, hot_topic):
        print(f"Hot topic already published for {hot_topic.url}")
        return 0

    analysis = generate_analysis(hot_topic)
    content = render_post(hot_topic, analysis)
    post_path = write_post(POSTS_DIR, analysis, content)
    write_outputs(post_path, analysis, hot_topic)
    print(f"Generated {post_path.relative_to(REPO_ROOT)} from {hot_topic.url} using model {analysis['model']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyError as exc:
        print(f"Missing required environment variable: {exc.args[0]}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
