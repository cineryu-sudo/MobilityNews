import unittest
from unittest.mock import patch

import main


class RuntimeConfigTests(unittest.TestCase):
    def test_ensure_llm_configured_raises_when_api_key_missing(self):
        with patch.object(main, "ANTHROPIC_API_KEY", ""):
            with self.assertRaisesRegex(RuntimeError, "ANTHROPIC_API_KEY"):
                main.ensure_llm_configured()

    def test_ensure_llm_configured_accepts_non_empty_api_key(self):
        with patch.object(main, "ANTHROPIC_API_KEY", "sk-ant-test"):
            main.ensure_llm_configured()


class HistoryPersistenceTests(unittest.TestCase):
    def test_should_save_history_skips_dry_run(self):
        self.assertFalse(main.should_save_history(success=True, dry_run=True))

    def test_should_save_history_requires_success(self):
        self.assertFalse(main.should_save_history(success=False, dry_run=False))
        self.assertTrue(main.should_save_history(success=True, dry_run=False))


if __name__ == "__main__":
    unittest.main()
