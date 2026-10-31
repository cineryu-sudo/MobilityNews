import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ops import reporting
from ops.models import DeliveryBatchResult, DeliveryResult, RunReport


RECIPIENTS = ["alice@example.com", "bob@example.com"]


def _report_with_delivery() -> RunReport:
    return RunReport(
        run_id="20261031T080000",
        mode="send",
        state="SENT",
        started_at="2026-10-31T08:00:00",
        delivery_result=DeliveryResult(
            success=True,
            subject="Mobility Business Radar",
            total_recipients=len(RECIPIENTS),
            batch_results=[
                DeliveryBatchResult(
                    batch_index=1,
                    total_batches=1,
                    recipients=list(RECIPIENTS),
                    success=True,
                    attempts=1,
                )
            ],
        ),
        notes=["주간 운영 리포트를 이메일로 발송했습니다: ops@example.com"],
    )


class SavedReportPrivacyTests(unittest.TestCase):
    def test_saved_report_does_not_contain_recipient_addresses(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(reporting, "RUN_ARTIFACTS_DIR", tmp):
                report = _report_with_delivery()
                reporting.save_run_report(report)

                json_text = Path(report.artifacts.report_json_path).read_text(encoding="utf-8")
                md_text = Path(report.artifacts.report_markdown_path).read_text(encoding="utf-8")

        for address in RECIPIENTS + ["ops@example.com"]:
            self.assertNotIn(address, json_text)
            self.assertNotIn(address, md_text)

        batch = json.loads(json_text)["delivery_result"]["batch_results"][0]
        self.assertNotIn("recipients", batch)
        self.assertEqual(batch["recipient_count"], 2)
        self.assertIn("recipients=2", md_text)

    def test_save_keeps_in_memory_report_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(reporting, "RUN_ARTIFACTS_DIR", tmp):
                report = _report_with_delivery()
                reporting.save_run_report(report)

        self.assertEqual(report.delivery_result.batch_results[0].recipients, RECIPIENTS)

    def test_scrub_saved_reports_cleans_legacy_files(self):
        legacy = {
            "run_id": "20261001T080000",
            "delivery_result": {
                "batch_results": [{"batch_index": 1, "recipients": list(RECIPIENTS)}]
            },
            "notes": ["sent to ops@example.com"],
            "selected_articles": [{"url": "https://medium.com/@writer/post"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "20261001T080000"
            run_dir.mkdir()
            path = run_dir / "report.json"
            path.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")

            with patch.object(reporting, "RUN_ARTIFACTS_DIR", tmp):
                cleaned = reporting.scrub_saved_reports()

            text = path.read_text(encoding="utf-8")

        self.assertEqual(cleaned, 1)
        for address in RECIPIENTS + ["ops@example.com"]:
            self.assertNotIn(address, text)
        data = json.loads(text)
        self.assertEqual(data["delivery_result"]["batch_results"][0]["recipient_count"], 2)
        self.assertEqual(data["selected_articles"][0]["url"], "https://medium.com/@writer/post")


if __name__ == "__main__":
    unittest.main()
