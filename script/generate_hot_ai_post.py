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
BACKGROUND_BRIEFS_PATH = Path(__file__).with_name("ai_topic_backgrounds.json")
DEFAULT_QUERY = 'AI OR "artificial intelligence" OR OpenAI OR Anthropic OR Claude OR Gemini OR DeepSeek OR Copilot when:1d'
GOOGLE_NEWS_RSS_URL = os.environ.get("GOOGLE_NEWS_RSS_URL", "https://news.google.com/rss/search")
HACKER_NEWS_RSS_URL = os.environ.get("HACKER_NEWS_RSS_URL", "https://news.ycombinator.com/rss")
ARXIV_RSS_URL = os.environ.get("ARXIV_RSS_URL", "https://rss.arxiv.org/rss/cs.AI")
DEFAULT_SOURCE = os.environ.get("HOT_AI_SOURCE", "hackernews")
MODELS_API_URL = os.environ.get("MODELS_API_URL", "https://models.github.ai/inference/chat/completions")
DEFAULT_RESEARCH_MODEL = "openai/gpt-5"
DEFAULT_WRITING_MODEL = "openai/gpt-4.1"
DEFAULT_REVIEW_MODEL = "openai/gpt-4.1"
DEFAULT_MODEL = DEFAULT_RESEARCH_MODEL
GPT5_MODEL_PREFIX = "openai/gpt-5"
MAX_RESEARCH_TOKENS = 8000
MAX_WRITING_TOKENS = 4000
MAX_REVIEW_TOKENS = 4000
MAX_SLUG_LENGTH = 60
POST_FILENAME_PREFIX = "ai"
REQUEST_TIMEOUT_SECONDS = 120
ERROR_SNIPPET_MAX_LENGTH = 500
MIN_FACT_COUNT = 3
MIN_UNCERTAINTY_COUNT = 1
MIN_BODY_LENGTH = 1400
JSON_DECODER = json.JSONDecoder()
AI_KEYWORDS = (
    "ai", "artificial intelligence", "openai", "anthropic", "claude", "gemini",
    "deepseek", "copilot", "machine learning", "deep learning", "llm", "large language model",
    "gpt", "neural", "transformer", "agent", "chatbot", "automation",
    "robotics", "computer vision", "nlp", "generative", "diffusion",
)
REQUIRED_HEADINGS: tuple[str, ...] = ()


@dataclass
class CoverageSource:
    title: str
    source_name: str
    url: str


@dataclass
class HotTopic:
    topic_id: str
    title: str
    summary: str
    source_name: str
    published_at: str
    url: str
    related_coverage: list[CoverageSource]
    background_briefs: list[dict[str, str]]


class HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def get_text(self) -> str:
        return "".join(self.parts)


class GoogleNewsDescriptionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._current_link: dict[str, str] | None = None
        self._in_source = False
        self._current_source_parts: list[str] = []
        self._current_title_parts: list[str] = []
        self.items: list[CoverageSource] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "a":
            self._current_link = {"url": attributes.get("href", "") or "", "title": ""}
            self._current_title_parts = []
        elif tag == "font":
            self._in_source = True
            self._current_source_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_link is not None:
            self._current_link["title"] = clean_text("".join(self._current_title_parts))
        elif tag == "font" and self._current_link is not None:
            source_name = clean_text("".join(self._current_source_parts))
            title = clean_text(self._current_link.get("title", ""))
            url = clean_text(self._current_link.get("url", ""))
            if title and url:
                self.items.append(
                    CoverageSource(
                        title=title,
                        source_name=source_name or "Unknown source",
                        url=url,
                    )
                )
            self._current_link = None
            self._in_source = False
            self._current_source_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_link is not None and not self._in_source:
            self._current_title_parts.append(data)
        elif self._in_source:
            self._current_source_parts.append(data)


def request_json(url: str, *, token: str, payload: dict | None = None) -> dict:
    headers = {
        "Authorization": "Bearer " + token,
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


def parse_related_coverage(description_html: str) -> list[CoverageSource]:
    parser = GoogleNewsDescriptionParser()
    parser.feed(unescape(description_html or ""))
    coverage: list[CoverageSource] = []
    seen: set[str] = set()
    for item in parser.items:
        dedupe_key = item.url or item.title
        if dedupe_key in seen:
            continue
        coverage.append(item)
        seen.add(dedupe_key)
    return coverage


def normalize_published_at(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return clean_text(value)
    return parsed.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def load_background_briefs(path: Path = BACKGROUND_BRIEFS_PATH) -> list[dict[str, str | list[str]]]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    briefs = data.get("briefs", [])
    if not isinstance(briefs, list):
        raise RuntimeError(f"Invalid background briefs format: {path}")
    return briefs


def select_background_briefs(
    title: str,
    summary: str,
    coverage: list[CoverageSource],
    briefs: list[dict[str, str | list[str]]] | None = None,
) -> list[dict[str, str]]:
    source_briefs = briefs if briefs is not None else load_background_briefs()
    topic_text = " ".join(
        [title, summary, *(item.title for item in coverage), *(item.source_name for item in coverage)]
    ).lower()
    matches: list[tuple[int, dict[str, str]]] = []
    for brief in source_briefs:
        keywords = [str(value).lower() for value in brief.get("keywords", [])]
        match_count = sum(1 for keyword in keywords if keyword and keyword in topic_text)
        if match_count == 0:
            continue
        matches.append(
            (
                match_count,
                {
                    "topic": str(brief.get("topic", "")),
                    "brief": str(brief.get("brief", "")).strip(),
                },
            )
        )
    matches.sort(key=lambda item: (-item[0], item[1]["topic"]))
    return [match for _, match in matches[:3] if match["brief"]]


def score_hot_topic(topic: HotTopic) -> tuple[int, int, int]:
    return (
        len(topic.related_coverage),
        len(topic.background_briefs),
        len(topic.summary),
    )


def is_ai_related(*texts: str) -> bool:
    combined = " ".join(texts).lower()
    return any(kw in combined for kw in AI_KEYWORDS)


def select_hot_topic(feed_xml: str, max_results: int) -> HotTopic:
    root = ElementTree.fromstring(feed_xml)
    items = root.findall("./channel/item")
    if not items:
        raise RuntimeError("RSS feed returned no items to analyze.")

    candidates: list[HotTopic] = []
    for item in items[:max_results]:
        title = clean_text(item.findtext("title", ""))
        source_name = clean_text(item.findtext("source", "Google News")) or "Google News"
        description_html = item.findtext("description", "")
        related_coverage = parse_related_coverage(description_html)
        summary = strip_html(description_html)
        published_at = normalize_published_at(item.findtext("pubDate", ""))
        link = clean_text(item.findtext("link", ""))
        guid = clean_text(item.findtext("guid", link))
        if not title or not link:
            continue
        background_briefs = select_background_briefs(title, summary, related_coverage)
        candidates.append(
            HotTopic(
                topic_id=guid or link,
                title=title,
                summary=summary,
                source_name=source_name,
                published_at=published_at,
                url=link,
                related_coverage=related_coverage,
                background_briefs=background_briefs,
            )
        )

    if not candidates:
        raise RuntimeError("RSS feed returned no usable AI topics to analyze.")

    candidates.sort(key=score_hot_topic, reverse=True)
    return candidates[0]


def fetch_hacker_news_topics(max_results: int) -> list[HotTopic]:
    feed_xml = request_text(HACKER_NEWS_RSS_URL)
    root = ElementTree.fromstring(feed_xml)
    items = root.findall("./channel/item")
    candidates: list[HotTopic] = []
    for item in items[:max_results]:
        title = clean_text(item.findtext("title", ""))
        link = clean_text(item.findtext("link", ""))
        if not title or not link or not is_ai_related(title):
            continue
        description_html = item.findtext("description", "") or ""
        summary = strip_html(description_html)
        published_at = normalize_published_at(item.findtext("pubDate", ""))
        source_name = "Hacker News"
        background_briefs = select_background_briefs(title, summary, [])
        candidates.append(HotTopic(
            topic_id=link,
            title=title,
            summary=summary,
            source_name=source_name,
            published_at=published_at,
            url=link,
            related_coverage=[],
            background_briefs=background_briefs,
        ))
    return candidates


def fetch_arxiv_papers(max_results: int) -> list[HotTopic]:
    feed_xml = request_text(ARXIV_RSS_URL)
    root = ElementTree.fromstring(feed_xml)
    items = root.findall("./channel/item")
    candidates: list[HotTopic] = []
    for item in items[:max_results]:
        raw_title = clean_text(item.findtext("title", ""))
        title = re.sub(r"^Title:\s*", "", raw_title, flags=re.IGNORECASE).strip()
        link = clean_text(item.findtext("link", ""))
        if not title or not link:
            continue
        description_html = item.findtext("description", "") or ""
        summary = strip_html(description_html)
        published_at = normalize_published_at(item.findtext("pubDate", ""))
        source_name = "arXiv"
        background_briefs = select_background_briefs(title, summary, [])
        candidates.append(HotTopic(
            topic_id=link,
            title=title,
            summary=summary,
            source_name=source_name,
            published_at=published_at,
            url=link,
            related_coverage=[],
            background_briefs=background_briefs,
        ))
    return candidates


def fetch_google_news_topics(max_results: int) -> list[HotTopic]:
    params = {
        "q": os.environ.get("HOT_AI_TOPIC_QUERY") or DEFAULT_QUERY,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }
    query = urllib.parse.urlencode(params)
    feed_xml = request_text(f"{GOOGLE_NEWS_RSS_URL}?{query}")
    return [select_hot_topic(feed_xml, max_results)]


SOURCE_FETCHERS: dict = {
    "google": fetch_google_news_topics,
    "hackernews": fetch_hacker_news_topics,
    "arxiv": fetch_arxiv_papers,
}


def fetch_hot_ai_topic() -> HotTopic:
    max_results = int(os.environ.get("HOT_AI_TOPIC_MAX_RESULTS") or "10")
    source = os.environ.get("HOT_AI_SOURCE") or DEFAULT_SOURCE
    sources = [s.strip() for s in source.split(",") if s.strip()]
    all_candidates: list[HotTopic] = []
    errors: list[str] = []
    for src in sources:
        fetcher = SOURCE_FETCHERS.get(src)
        if fetcher is None:
            errors.append(f"Unknown source: {src}")
            continue
        try:
            candidates = fetcher(max_results)
            all_candidates.extend(candidates)
            print(f"Fetched {len(candidates)} candidates from {src}", file=sys.stderr)
        except Exception as exc:
            errors.append(f"{src}: {exc}")
            print(f"Source {src} failed: {exc}", file=sys.stderr)
    if not all_candidates:
        detail = "; ".join(errors) if errors else "no candidates returned"
        raise RuntimeError(f"No hot AI topic found ({detail})")
    all_candidates.sort(key=score_hot_topic, reverse=True)
    return all_candidates[0]


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


def extract_text_content(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
                continue
            for field_name in ("content", "value"):
                field_value = item.get(field_name)
                if isinstance(field_value, str):
                    parts.append(field_value)
                    break
        return "".join(parts)
    if isinstance(value, dict):
        for field_name in ("text", "content", "value"):
            field_value = value.get(field_name)
            if isinstance(field_value, str):
                return field_value
    return ""


def truncate_for_error(text: str, max_length: int = ERROR_SNIPPET_MAX_LENGTH) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def summarize_choice(first_choice: dict[str, object]) -> str:
    keys = sorted(str(key) for key in first_choice.keys())
    message = first_choice.get("message")
    message_keys = sorted(str(key) for key in message.keys()) if isinstance(message, dict) else []
    return f"choice_keys={keys}, message_keys={message_keys}"


def extract_json_object(text: str) -> object | None:
    candidate_indexes: set[int] = set()
    index = text.find("{")
    while index >= 0:
        candidate_indexes.add(index)
        index = text.find("{", index + 1)
    for index in sorted(candidate_indexes):
        try:
            value, _ = JSON_DECODER.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        return value
    return None


def resolve_stage_model(env_name: str, default_model: str) -> str:
    configured_model = clean_text(os.environ.get(env_name, ""))
    if configured_model:
        return configured_model
    legacy_model = clean_text(os.environ.get("MODELS_MODEL", ""))
    if legacy_model:
        return legacy_model
    return default_model


def resolve_research_model() -> str:
    return resolve_stage_model("MODELS_RESEARCH_MODEL", DEFAULT_RESEARCH_MODEL)


def resolve_writing_model() -> str:
    return resolve_stage_model("MODELS_WRITING_MODEL", DEFAULT_WRITING_MODEL)


def resolve_review_model() -> str:
    return resolve_stage_model("MODELS_REVIEW_MODEL", DEFAULT_REVIEW_MODEL)


def supports_custom_temperature(model: str) -> bool:
    normalized_model = clean_text(model).lower()
    return not normalized_model.startswith(GPT5_MODEL_PREFIX)


def add_temperature(payload: dict[str, object], model: str, temperature: float) -> dict[str, object]:
    if supports_custom_temperature(model):
        return {**payload, "temperature": temperature}
    return payload


def render_related_coverage(topic: HotTopic) -> str:
    if not topic.related_coverage:
        return "- 无额外关联报道\n"
    lines = []
    for item in topic.related_coverage[:6]:
        lines.append(f"- {item.title}｜{item.source_name}｜{item.url}")
    return "\n".join(lines)


def render_background_briefs(topic: HotTopic) -> str:
    if not topic.background_briefs:
        return "- 无匹配到预置背景卡片"
    return "\n".join(f"- {item['topic']}: {item['brief']}" for item in topic.background_briefs)


def content_filter_blocked(first_choice: dict) -> str | None:
    filters = first_choice.get("content_filter_results")
    if not isinstance(filters, dict):
        return None
    blocked = [
        f"{cat}(severity={details.get('severity', 'unknown')})"
        for cat, details in filters.items()
        if isinstance(details, dict) and details.get("filtered")
    ]
    if blocked:
        return "content filtered: " + ", ".join(blocked)
    return None


def model_response_content(response: dict) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Models API response did not include any choices.")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise RuntimeError("Models API response choice is not an object.")
    message = first_choice.get("message")
    if isinstance(message, dict):
        content = extract_text_content(message.get("content"))
        finish_reason = first_choice.get("finish_reason", "")
        refusal = clean_text(extract_text_content(message.get("refusal")))
        if refusal:
            raise RuntimeError(f"Models API request was refused: {refusal}")
        blocked = content_filter_blocked(first_choice)
        if blocked:
            reason = first_choice.get("finish_reason", "unknown")
            raise RuntimeError(f"Models API response was blocked by content filter ({blocked}, finish_reason={reason})")
        if finish_reason == "length":
            hint = content[:200].strip() if content.strip() else "empty"
            raise RuntimeError(
                f"Model hit token limit (max_completion_tokens unknown). "
                f"Increase the token limit or reduce the response size. Content preview: {hint}..."
            )
        if content.strip():
            return content
    choice_text = extract_text_content(first_choice.get("text"))
    if choice_text.strip():
        return choice_text
    raise RuntimeError(f"Models API response did not include text content: {summarize_choice(first_choice)}")


def parse_model_json_response(response: dict, stage_name: str) -> dict[str, object]:
    content = strip_code_fences(model_response_content(response))
    if not content.strip():
        raise RuntimeError(f"{stage_name} model returned empty content.")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = extract_json_object(content)
    if not isinstance(parsed, dict):
        snippet = truncate_for_error(content)
        raise RuntimeError(f"{stage_name} model returned invalid JSON object: {snippet}")
    return parsed


def generate_research_package(topic: HotTopic) -> dict[str, object]:
    token = os.environ["MODELS_TOKEN"]
    model = resolve_research_model()
    payload = add_temperature({
        "model": model,
        "max_completion_tokens": MAX_RESEARCH_TOKENS,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a senior technology analyst preparing research notes for a Chinese engineering blog. "
                    "Return valid JSON only. Your job is to organize facts, competing interpretations, uncertainties, "
                    "and an article outline before anyone starts writing."
                ),
            },
            {
                "role": "user",
                "content": (
                    "请先做研究，不要写文章。基于下面的热点材料，输出 JSON 对象，字段必须包含：\n"
                    "angle（本篇分析的主线）\n"
                    "facts（数组，列出至少 3 条已知事实，每条都要说明来自哪些材料）\n"
                    "inferences（数组，列出至少 2 条推断/判断，并明确其依据）\n"
                    "uncertainties（数组，列出至少 1 条当前仍不确定、需要谨慎表达的点）\n"
                    "industry_impacts（数组）\n"
                    "engineering_actions（数组）\n"
                    "suggested_headings（数组，建议的文章章节标题）\n\n"
                    "要求：\n"
                    "1. 只能使用提供的材料和通用背景卡片，不要编造额外事实。\n"
                    "2. facts 中必须体现多信源视角，尽量引用不同媒体或不同背景卡片。\n"
                    "3. 如果材料不足以支撑强结论，必须在 uncertainties 中明确指出。\n\n"
                    f"主新闻来源：{topic.source_name}\n"
                    f"发布时间：{topic.published_at}\n"
                    f"主新闻标题：{topic.title}\n"
                    f"主新闻摘要：{topic.summary}\n"
                    f"主新闻链接：{topic.url}\n\n"
                    f"关联报道：\n{render_related_coverage(topic)}\n\n"
                    f"预置背景卡片：\n{render_background_briefs(topic)}\n"
                ),
            },
        ],
    }, model, 0.6)
    response = request_json(MODELS_API_URL, token=token, payload=payload)
    research = parse_model_json_response(response, "Research")
    research["model"] = model
    return research


def generate_article_draft(topic: HotTopic, research: dict[str, object]) -> dict[str, str]:
    token = os.environ["MODELS_TOKEN"]
    model = resolve_writing_model()
    payload = add_temperature({
        "model": model,
        "max_completion_tokens": MAX_WRITING_TOKENS,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are GitHub Copilot writing for a personal engineering blog built with Jekyll. "
                    "Return only valid JSON with keys: title, slug, excerpt, body. "
                    "The blog must be in Simplified Chinese, concrete, analytical, and must distinguish facts from judgment."
                ),
            },
            {
                "role": "user",
                "content": (
                    "请基于下面的研究材料写一篇中文技术博客分析文章，并返回 JSON 对象，字段必须是 title、slug、excerpt、body。\n"
                    "要求：\n"
                    "1. title 不超过 50 个字；slug 提供一个简短主题短语即可，程序会统一转成 URL slug；excerpt 1-2 句话。\n"
                    "2. body 仅返回 Markdown 正文，不要包含 YAML front matter。\n"
                    "3. 结构自定，但必须是一篇完整的分析文章：介绍背景 → 陈述事实与判断 → 分析影响 → 总结。\n"
                    "4. 明确区分已知事实、推断和不确定点。\n"
                    '5. 避免空话；凡是写"值得关注""影响深远""重要"这类判断，都要立刻给出原因。\n'
                    "6. 工程建议要可执行，不能只喊口号。\n"
                    "7. 正文中保留且只保留一次原始新闻链接。\n\n"
                    f"话题：{topic.title}\n"
                    f"主新闻链接：{topic.url}\n\n"
                    f"研究材料：\n{json.dumps(research, ensure_ascii=False, indent=2)}"
                ),
            },
        ],
    }, model, 0.8)
    response = request_json(MODELS_API_URL, token=token, payload=payload)
    draft = parse_model_json_response(response, "Writing")
    draft["slug"] = slugify(draft.get("slug") or draft.get("title", ""))
    draft["model"] = model
    return draft


def review_article_draft(
    topic: HotTopic,
    research: dict[str, object],
    draft: dict[str, str],
) -> dict[str, object]:
    token = os.environ["MODELS_TOKEN"]
    model = resolve_review_model()
    payload = add_temperature({
        "model": model,
        "max_completion_tokens": MAX_REVIEW_TOKENS,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a strict editorial reviewer for a Chinese engineering blog. "
                    "Return only valid JSON. Fix vague writing, remove unsupported claims, and keep the result publishable."
                ),
            },
            {
                "role": "user",
                "content": (
                    "请审阅并必要时改写下面的文章草稿，返回 JSON 对象，字段必须包含：\n"
                    "approved（布尔值）\n"
                    "title\nslug\nexcerpt\nbody\nissues（数组，列出你修正或仍然担心的问题）\n\n"
                    "审阅标准：\n"
                    "1. 删除没有依据的强结论。\n"
                    "2. 确保事实、推断和不确定点边界清晰。\n"
                    "3. 检查正文是否有具体信息，而不是套话。\n"
                    '4. 如果出现"值得关注""影响深远"等判断，必须补充原因。\n'
                    "5. 保留一次且仅一次原始新闻链接。\n"
                    "6. 保持文章结构完整：介绍背景、分析事实与判断、讨论影响、总结。\n\n"
                    f"话题：{topic.title}\n"
                    f"主新闻链接：{topic.url}\n\n"
                    f"研究材料：\n{json.dumps(research, ensure_ascii=False, indent=2)}\n\n"
                    f"文章草稿：\n{json.dumps(draft, ensure_ascii=False, indent=2)}"
                ),
            },
        ],
    }, model, 0.2)
    response = request_json(MODELS_API_URL, token=token, payload=payload)
    review = parse_model_json_response(response, "Review")
    review["model"] = model
    return review


def validate_analysis(topic: HotTopic, research: dict[str, object], analysis: dict[str, object]) -> list[str]:
    errors: list[str] = []
    title = clean_text(str(analysis.get("title", "")))
    excerpt = clean_text(str(analysis.get("excerpt", "")))
    body = str(analysis.get("body", "")).strip()
    if not title:
        errors.append("Missing title in final analysis output.")
    if not excerpt:
        errors.append("Missing excerpt in final analysis output.")
    if len(body) < MIN_BODY_LENGTH:
        errors.append(f"Body is too short for an in-depth analysis ({len(body)} chars).")
    link_count = body.count(topic.url)
    if link_count < 1:
        errors.append("Body must include the original news link at least once.")
    facts = research.get("facts")
    if not isinstance(facts, list) or len(facts) < MIN_FACT_COUNT:
        errors.append(f"Research package must contain at least {MIN_FACT_COUNT} facts.")
    uncertainties = research.get("uncertainties")
    if not isinstance(uncertainties, list) or len(uncertainties) < MIN_UNCERTAINTY_COUNT:
        errors.append("Research package must contain at least one uncertainty.")
    return errors


def generate_analysis(topic: HotTopic) -> dict[str, object]:
    research = generate_research_package(topic)
    draft = generate_article_draft(topic, research)
    review = review_article_draft(topic, research, draft)
    final_analysis = {
        "title": review.get("title") or draft.get("title", ""),
        "slug": slugify(str(review.get("slug") or draft.get("slug") or draft.get("title", ""))),
        "excerpt": review.get("excerpt") or draft.get("excerpt", ""),
        "body": review.get("body") or draft.get("body", ""),
        "approved": bool(review.get("approved", False)),
        "issues": review.get("issues") if isinstance(review.get("issues"), list) else [],
        "research": research,
        "models": {
            "research": research["model"],
            "writing": draft["model"],
            "review": review["model"],
        },
    }
    quality_errors = validate_analysis(topic, research, final_analysis)
    if not final_analysis["approved"]:
        quality_errors.append("Editorial review did not approve the article.")
    if quality_errors:
        body = str(final_analysis.get("body", "")).strip()
        print("DEBUG: article body preview (first 1000 chars):", file=sys.stderr)
        print(body[:1000], file=sys.stderr)
        if len(body) > 1000:
            print("...(truncated)", file=sys.stderr)
        raise RuntimeError("Quality gate failed:\n- " + "\n- ".join(quality_errors))
    return final_analysis


def yaml_string(value: str) -> str:
    return json.dumps((value or "").strip(), ensure_ascii=False)


def render_post(topic: HotTopic, analysis: dict[str, object]) -> str:
    now = datetime.now(UTC)
    title = str(analysis["title"]).strip()
    slug = slugify(str(analysis.get("slug") or title))
    excerpt = re.sub(r"\s+", " ", str(analysis.get("excerpt", ""))).strip()
    body = str(analysis["body"]).strip()
    permalink = f"/posts/{now:%Y/%m/%d}/{slug}.html"
    published_at = topic.published_at or "Unknown"
    models = analysis.get("models", {})
    research_model = models.get("research", "unknown")
    writing_model = models.get("writing", "unknown")
    review_model = models.get("review", "unknown")
    return f"""---
layout: post
title: {yaml_string(title)}
permalink: {permalink}
category: AI
tags:
  - AI
  - GitHub Copilot
excerpt: {yaml_string(excerpt)}
---

> 本文由 GitHub Actions 自动抓取热门 AI 话题，并使用“先研究、再写作、后审校”的多阶段流程生成初稿。
>
> 热点来源：[{topic.source_name}]({topic.url}) · 发布时间：{published_at}
> 关联报道数：{len(topic.related_coverage)} · 使用模型：research={research_model}, writing={writing_model}, review={review_model}

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


def write_post(posts_dir: Path, analysis: dict[str, object], content: str) -> Path:
    path = build_post_path(posts_dir, str(analysis["slug"]))
    suffix = 1
    while path.exists():
        path = build_post_path(posts_dir, str(analysis["slug"]), suffix)
        suffix += 1
    path.write_text(content, encoding="utf-8")
    return path


def write_github_action_output(handle, name: str, value: str) -> None:
    delimiter = "GITHUB_OUTPUT_EOF"
    while delimiter in value:
        delimiter += "_"
    handle.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")


def write_outputs(post_path: Path, analysis: dict[str, object], hot_topic: HotTopic) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        write_github_action_output(handle, "post_file", str(post_path.relative_to(REPO_ROOT)))
        write_github_action_output(handle, "post_title", str(analysis["title"]))
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
    print(
        f"Generated {post_path.relative_to(REPO_ROOT)} from {hot_topic.url} "
        f"using models {analysis['models']}"
    )
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
