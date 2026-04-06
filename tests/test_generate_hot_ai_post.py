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
    def test_select_latest_model_id_prefers_newest_openai_gpt_text_model(self):
        models = [
            {
                "id": "openai/gpt-4.1-mini",
                "version": "2025-04-14",
                "supported_input_modalities": ["text"],
                "supported_output_modalities": ["text"],
            },
            {
                "id": "openai/gpt-5",
                "version": "2026-03-01",
                "supported_input_modalities": ["text"],
                "supported_output_modalities": ["text"],
            },
            {
                "id": "openai/whisper",
                "version": "2026-04-01",
                "supported_input_modalities": ["audio"],
                "supported_output_modalities": ["text"],
            },
        ]

        self.assertEqual(MODULE.select_latest_model_id(models), "openai/gpt-5")

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
