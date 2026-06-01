import importlib.util
import re
import sys
import tempfile
import unittest
from datetime import UTC
from datetime import datetime
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "script" / "generate_hot_ai_post.py"
WORKFLOW_PATH = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "hot-ai-topic.yml"
BACKGROUNDS_PATH = Path(__file__).resolve().parents[1] / "script" / "ai_topic_backgrounds.json"
SPEC = importlib.util.spec_from_file_location("generate_hot_ai_post", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def workflow_input_default(name: str) -> str:
    pattern = re.compile(
        rf"^\s+{re.escape(name)}:\s*$.*?^\s+default:\s+([^\n]+)\s*$",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(WORKFLOW_PATH.read_text(encoding="utf-8"))
    if match is None:
        raise AssertionError(f"Workflow input {name} missing")
    return match.group(1).strip().strip("'\"")


def workflow_env_fallback(name: str) -> str:
    pattern = re.compile(
        rf"^\s+{re.escape(name)}:\s+\$\{{\{{.*?\|\|\s+(['\"])([^'\"]+)\1\s*\}}\}}\s*$",
        re.MULTILINE,
    )
    match = pattern.search(WORKFLOW_PATH.read_text(encoding="utf-8"))
    if match is None:
        raise AssertionError(f"Workflow env {name} missing")
    return match.group(2)


class GenerateHotAIPostTests(unittest.TestCase):
    def test_stage_models_use_new_defaults(self):
        with mock.patch.dict(MODULE.os.environ, {}, clear=True):
            self.assertEqual(MODULE.resolve_research_model(), MODULE.DEFAULT_RESEARCH_MODEL)
            self.assertEqual(MODULE.resolve_writing_model(), MODULE.DEFAULT_WRITING_MODEL)
            self.assertEqual(MODULE.resolve_review_model(), MODULE.DEFAULT_REVIEW_MODEL)

    def test_stage_models_fall_back_to_legacy_override(self):
        with mock.patch.dict(MODULE.os.environ, {"MODELS_MODEL": "openai/gpt-4.1-mini"}, clear=True):
            self.assertEqual(MODULE.resolve_research_model(), "openai/gpt-4.1-mini")
            self.assertEqual(MODULE.resolve_writing_model(), "openai/gpt-4.1-mini")
            self.assertEqual(MODULE.resolve_review_model(), "openai/gpt-4.1-mini")

    def test_gpt5_models_skip_custom_temperature(self):
        payload = {"model": "openai/gpt-5"}
        self.assertNotIn("temperature", MODULE.add_temperature(payload, "openai/gpt-5", 0.6))

    def test_non_gpt5_models_keep_custom_temperature(self):
        payload = {"model": "openai/gpt-4.1"}
        self.assertEqual(MODULE.add_temperature(payload, "openai/gpt-4.1", 0.8)["temperature"], 0.8)

    def test_workflow_default_models_match_script_defaults(self):
        self.assertEqual(workflow_input_default("research_model"), MODULE.DEFAULT_RESEARCH_MODEL)
        self.assertEqual(workflow_input_default("writing_model"), MODULE.DEFAULT_WRITING_MODEL)
        self.assertEqual(workflow_input_default("review_model"), MODULE.DEFAULT_REVIEW_MODEL)
        self.assertEqual(workflow_env_fallback("MODELS_RESEARCH_MODEL"), MODULE.DEFAULT_RESEARCH_MODEL)
        self.assertEqual(workflow_env_fallback("MODELS_WRITING_MODEL"), MODULE.DEFAULT_WRITING_MODEL)
        self.assertEqual(workflow_env_fallback("MODELS_REVIEW_MODEL"), MODULE.DEFAULT_REVIEW_MODEL)

    def test_background_briefs_file_exists_and_loads(self):
        self.assertTrue(BACKGROUNDS_PATH.exists())
        briefs = MODULE.load_background_briefs()
        self.assertGreaterEqual(len(briefs), 3)

    def test_select_hot_topic_prefers_richer_coverage(self):
        feed_xml = """
        <rss>
          <channel>
            <item>
              <title>Minor AI update</title>
              <description><![CDATA[
                <a href="https://example.com/a1">Minor AI update</a> <font color="#6f6f6f">Source A</font>
              ]]></description>
              <link>https://news.google.com/minor</link>
              <guid>minor</guid>
            </item>
            <item>
              <title>OpenAI ships enterprise AI workflow</title>
              <description><![CDATA[
                <a href="https://example.com/b1">OpenAI ships enterprise AI workflow</a> <font color="#6f6f6f">Source B</font>
                <a href="https://example.com/b2">Customers test the rollout</a> <font color="#6f6f6f">Source C</font>
                <a href="https://example.com/b3">Analysts debate pricing</a> <font color="#6f6f6f">Source D</font>
              ]]></description>
              <link>https://news.google.com/rich</link>
              <guid>rich</guid>
            </item>
          </channel>
        </rss>
        """
        topic = MODULE.select_hot_topic(feed_xml, max_results=5)
        self.assertEqual(topic.topic_id, "rich")
        self.assertGreaterEqual(len(topic.related_coverage), 3)
        self.assertTrue(any(item["topic"] == "OpenAI / ChatGPT" for item in topic.background_briefs))

    def test_parse_related_coverage_extracts_titles_sources_and_urls(self):
        coverage = MODULE.parse_related_coverage(
            """
            <a href="https://example.com/1">Headline One</a> <font color="#6f6f6f">Source One</font>
            <a href="https://example.com/2">Headline Two</a> <font color="#6f6f6f">Source Two</font>
            """
        )
        self.assertEqual(len(coverage), 2)
        self.assertEqual(coverage[0].title, "Headline One")
        self.assertEqual(coverage[0].source_name, "Source One")
        self.assertEqual(coverage[1].url, "https://example.com/2")

    def test_already_generated_today_only_matches_today_ai_posts(self):
        now = datetime(2026, 4, 6, 2, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as temp_dir:
            posts_dir = Path(temp_dir)
            (posts_dir / "2026-04-06-ai-sample.md").write_text("generated", encoding="utf-8")
            (posts_dir / "2026-04-05-ai-old.md").write_text("generated", encoding="utf-8")

            self.assertTrue(MODULE.already_generated_today(posts_dir, now))
            self.assertFalse(
                MODULE.already_generated_today(
                    posts_dir,
                    datetime(2026, 4, 7, 2, 0, tzinfo=UTC),
                )
            )

    def test_generate_analysis_runs_research_write_and_review_stages(self):
        topic = MODULE.HotTopic(
            topic_id="topic-1",
            title="OpenAI enterprise push",
            summary="Summary",
            source_name="Google News",
            published_at="2026-04-06 00:00:00 UTC",
            url="https://example.com/topic",
            related_coverage=[
                MODULE.CoverageSource("Source one", "Source A", "https://example.com/1"),
                MODULE.CoverageSource("Source two", "Source B", "https://example.com/2"),
            ],
            background_briefs=[{"topic": "OpenAI / ChatGPT", "brief": "brief"}],
        )
        draft_body = (
            "## 事件概览\n内容与依据，说明这次变化直接来自企业客户开始付费和试点扩容。\n\n"
            "## 背景脉络\n这里解释背景。\n\n"
            "## 已知事实与判断\n### 已知事实\n- 事实1\n- 事实2\n- 事实3\n\n"
            "### 推断/判断\n- 判断1，因为已有企业试点。\n\n"
            "### 不确定点\n- 不确定点1。\n\n"
            "## 为什么值得关注\n因为它会改变预算分配和采购节奏。\n\n"
            "## 技术与产业影响\n讨论基础设施与产品化。\n\n"
            "## 真正影响行业的变量\n变量包括成本、集成深度与分发。\n\n"
            "## 工程负责人该如何响应\n列出评估指标、权限隔离、回滚方案。\n\n"
            "## 风险与争议\n讨论锁定风险与安全边界。\n\n"
            "## 可能被高估的地方\n指出短期内不会立刻改变所有团队。\n\n"
            "## 总结\n最后附上原文链接 https://example.com/topic，并总结判断。"
        )
        reviewed_body = (
            "## 事件概览\n内容与依据，说明这次变化直接来自企业客户开始付费和试点扩容。\n\n"
            "## 背景脉络\n这里解释背景以及历史脉络。\n\n"
            "## 已知事实与判断\n### 已知事实\n- 事实1\n- 事实2\n- 事实3\n\n"
            "### 推断/判断\n- 判断1，因为已有企业试点。\n\n"
            "### 不确定点\n- 不确定点1。\n\n"
            "## 为什么值得关注\n因为它会改变预算分配、产品路线和采购节奏。\n\n"
            "## 技术与产业影响\n讨论基础设施、模型接入和集成成本。\n\n"
            "## 真正影响行业的变量\n变量包括成本、集成深度、分发和治理能力。\n\n"
            "## 工程负责人该如何响应\n列出评估指标、权限隔离、回滚方案和审计流程。\n\n"
            "## 风险与争议\n讨论锁定风险、安全边界和组织错配。\n\n"
            "## 可能被高估的地方\n指出短期内不会立刻改变所有团队，采购周期仍然很长。\n\n"
            "## 总结\n最后附上原文链接 https://example.com/topic，并总结判断。"
            + ("更多分析与执行细节。" * 220)
        )
        responses = [
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"angle":"angle","facts":["f1","f2","f3"],'
                                '"inferences":["i1","i2"],"uncertainties":["u1"],'
                                '"industry_impacts":["impact"],"engineering_actions":["act"],'
                                '"outline":["事件概览","背景脉络","已知事实与判断","为什么值得关注","技术与产业影响","真正影响行业的变量","工程负责人该如何响应","风险与争议","可能被高估的地方","总结"]}'
                            )
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "message": {
                            "content": MODULE.json.dumps(
                                {"title": "标题", "slug": "custom slug", "excerpt": "摘要", "body": draft_body},
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "message": {
                            "content": MODULE.json.dumps(
                                {
                                    "approved": True,
                                    "title": "标题",
                                    "slug": "custom slug",
                                    "excerpt": "摘要",
                                    "issues": ["ok"],
                                    "body": reviewed_body,
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        ]

        with mock.patch.dict(MODULE.os.environ, {"MODELS_TOKEN": "test-token"}, clear=False):
            with mock.patch.object(MODULE, "request_json", side_effect=responses) as request_json:
                analysis = MODULE.generate_analysis(topic)

        self.assertEqual(request_json.call_count, 3)
        self.assertEqual(request_json.call_args_list[0].kwargs["payload"]["model"], MODULE.DEFAULT_RESEARCH_MODEL)
        self.assertEqual(request_json.call_args_list[1].kwargs["payload"]["model"], MODULE.DEFAULT_WRITING_MODEL)
        self.assertEqual(request_json.call_args_list[2].kwargs["payload"]["model"], MODULE.DEFAULT_REVIEW_MODEL)
        self.assertNotIn("temperature", request_json.call_args_list[0].kwargs["payload"])
        self.assertEqual(request_json.call_args_list[1].kwargs["payload"]["temperature"], 0.8)
        self.assertEqual(request_json.call_args_list[2].kwargs["payload"]["temperature"], 0.2)
        self.assertEqual(analysis["models"]["research"], MODULE.DEFAULT_RESEARCH_MODEL)
        self.assertEqual(analysis["slug"], "custom-slug")

    def test_model_response_content_supports_structured_content_parts(self):
        response = {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "output_text", "text": '{"title":"标题"'},
                            {"type": "output_text", "text": ',"body":"正文"}'},
                        ]
                    }
                }
            ]
        }

        self.assertEqual(MODULE.model_response_content(response), '{"title":"标题","body":"正文"}')

    def test_model_response_content_supports_nested_text_values(self):
        response = {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "output_text", "text": {"value": '{"title":"标题"'}},
                            {"type": "output_text", "text": {"value": ',"body":"正文"}'}},
                        ]
                    }
                }
            ]
        }

        self.assertEqual(MODULE.model_response_content(response), '{"title":"标题","body":"正文"}')

    def test_parse_model_json_response_extracts_json_from_wrapped_text(self):
        response = {
            "choices": [
                {
                    "message": {
                        "content": "下面是整理后的 JSON：\n```json\n{\"title\":\"标题\",\"body\":\"正文\"}\n```"
                    }
                }
            ]
        }

        parsed = MODULE.parse_model_json_response(response, "Writing")

        self.assertEqual(parsed["title"], "标题")
        self.assertEqual(parsed["body"], "正文")

    def test_parse_model_json_response_rejects_empty_content(self):
        response = {"choices": [{"message": {"content": "   "}}]}

        with self.assertRaisesRegex(RuntimeError, "did not include text content"):
            MODULE.parse_model_json_response(response, "Research")

    def test_validate_analysis_rejects_missing_sections(self):
        topic = MODULE.HotTopic(
            topic_id="topic-1",
            title="AI topic",
            summary="Summary",
            source_name="Google News",
            published_at="2026-04-06 00:00:00 UTC",
            url="https://example.com/topic",
            related_coverage=[
                MODULE.CoverageSource("Source one", "Source A", "https://example.com/1"),
                MODULE.CoverageSource("Source two", "Source B", "https://example.com/2"),
            ],
            background_briefs=[],
        )
        research = {"facts": ["a", "b", "c"], "uncertainties": ["u1"]}
        analysis = {"title": "标题", "excerpt": "摘要", "body": "https://example.com/topic"}
        errors = MODULE.validate_analysis(topic, research, analysis)
        self.assertTrue(any("Missing required section heading" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
