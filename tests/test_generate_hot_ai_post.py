import importlib.util
import sys
import tempfile
import unittest
from datetime import UTC
from datetime import datetime
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "script" / "generate_hot_ai_post.py"
SPEC = importlib.util.spec_from_file_location("generate_hot_ai_post", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateHotAIPostTests(unittest.TestCase):
    def test_resolve_model_uses_default_gpt5_when_not_overridden(self):
        original_value = MODULE.os.environ.get("MODELS_MODEL")
        try:
            MODULE.os.environ.pop("MODELS_MODEL", None)
            self.assertEqual(MODULE.resolve_model(), "openai/gpt-5")
        finally:
            if original_value is None:
                MODULE.os.environ.pop("MODELS_MODEL", None)
            else:
                MODULE.os.environ["MODELS_MODEL"] = original_value

    def test_resolve_model_prefers_explicit_override(self):
        original_value = MODULE.os.environ.get("MODELS_MODEL")
        try:
            MODULE.os.environ["MODELS_MODEL"] = "openai/gpt-5-mini"
            self.assertEqual(MODULE.resolve_model(), "openai/gpt-5-mini")
        finally:
            if original_value is None:
                MODULE.os.environ.pop("MODELS_MODEL", None)
            else:
                MODULE.os.environ["MODELS_MODEL"] = original_value

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


if __name__ == "__main__":
    unittest.main()
