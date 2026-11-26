"""Synthetic deployment histories for the terminal views."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import deploy_ui as ui


VERIFIED = "candidate tests_started tests_passed image_verification_started image_verified production"
CUTOVER = VERIFIED + " backup_started backup_verified deploying checks_started"
SCENARIOS = {
    "success": CUTOVER + " health smoke deployed sync_complete complete",
    "failure": "candidate tests_started failed",
    "rollback": CUTOVER + " failed rollback_started health smoke rolled_back",
    "manual": CUTOVER + " failed recovery_required service_stopped",
    "rollback_failure": CUTOVER + " failed rollback_started recovery_failed",
    "sync_pending": CUTOVER + " deployed sync_pending complete",
}


def records(scenario):
    for second, event in enumerate(SCENARIOS[scenario].split()):
        yield {"timestamp": f"2026-01-01T00:00:{second:02}+00:00", "event": event,
               "commit": ("b" if event == "candidate" else "a") * 40,
               "message": "synthetic-private", "remote": "synthetic-private"}


class DashboardTests(unittest.TestCase):
    def test_latest_outcomes_and_secret_filter(self):
        outcomes = ["Deployment successful", "Deployment failed", "Rollback successful",
                    "Recovery required", "Recovery required", "synchronization pending"]
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            for scenario, expected in zip(SCENARIOS, outcomes):
                with self.subTest(scenario=scenario):
                    (run / "events.jsonl").write_text("\n".join(map(json.dumps, records(scenario))))
                    with redirect_stdout(io.StringIO()) as output:
                        ui.latest(run)
                    summary = output.getvalue()
                    self.assertIn(expected, summary)
                    self.assertNotIn("synthetic-private", summary)
                    self.assertNotIn("\x1b", summary)
                    self.assertIn("bbbbbbbbbbbb", summary)
                    self.assertIn(str(run), summary)
                    if scenario == "rollback":
                        self.assertIn("LAN and HTTPS health checks · Failure · 0:01", summary)
                    if scenario == "failure":
                        self.assertIn("Automated tests · Failure · 0:01", summary)

    def test_missing_rich_on_terminal(self):
        stream = io.StringIO()
        stream.isatty = lambda: True
        with patch.object(ui, "Console", None):
            view = ui.Dashboard("/tmp/demo", stream)
            with view.live():
                view.accept({"event": "tests_started"})
            self.assertIn(ui.STAGES[0], stream.getvalue())

    @unittest.skipUnless(ui.Console, "optional host Rich package required")
    def test_pty_render_resize_and_interrupt_cleanup(self):
        stream = io.StringIO()
        stream.isatty = lambda: True
        view = ui.Dashboard("/tmp/demo", stream)
        view.console = ui.Console(file=stream, force_terminal=True, width=36)
        with self.assertRaises(KeyboardInterrupt), view.live():
            for record in records("success"):
                view.accept(record)
            view.console.width = 60
            raise KeyboardInterrupt
        self.assertIn("Deployment successful", stream.getvalue())
        self.assertIn("\x1b[?25h", stream.getvalue())


if __name__ == "__main__":
    # Replay fixtures without loading the engine or accessing deployment state.
    import argparse
    from time import sleep

    parser = argparse.ArgumentParser(description="Preview a synthetic deployment")
    parser.add_argument("scenario", choices=SCENARIOS)
    scenario = parser.parse_args().scenario
    dashboard = ui.Dashboard(Path("/tmp/demo") / scenario)
    with dashboard.live():
        for record in records(scenario):
            dashboard.accept(record)
            if dashboard.console:
                sleep(0.4)
    if not dashboard.console:
        dashboard.summary()
