import os
from pathlib import Path
import subprocess
import sys
from unittest import TestCase


class SettingsTests(TestCase):
    def run_settings(self, **environment):
        env = {k: v for k, v in os.environ.items() if not k.startswith("DJANGO_")}
        env.update(environment)
        return subprocess.run([sys.executable, "-c", "import config.settings"], env=env, capture_output=True, text=True)

    def test_production_requires_configuration(self):
        self.assertNotEqual(self.run_settings().returncode, 0)
        self.assertNotEqual(self.run_settings(DJANGO_SECRET_KEY="test", DJANGO_ALLOWED_HOSTS="localhost", DJANGO_DB_PATH="relative.sqlite3").returncode, 0)
        self.assertEqual(self.run_settings(DJANGO_SECRET_KEY="test", DJANGO_ALLOWED_HOSTS="localhost", DJANGO_DB_PATH="/tmp/disposable.sqlite3").returncode, 0)

    def test_development_is_explicit(self):
        self.assertNotEqual(self.run_settings(DJANGO_ENV="development").returncode, 0)
        self.assertEqual(self.run_settings(DJANGO_ENV="development", DJANGO_DB_PATH="/tmp/disposable.sqlite3").returncode, 0)

    def test_release_runbook_starts_service_only_after_successful_migration(self):
        readme = Path(__file__).resolve().parents[2] / "README.md"
        release = readme.read_text(encoding="utf-8").split("With the owner-approved private environment file and backup prepared:")[1]
        commands = release.split("```sh\n")[1].split("```")[0]
        docker_stub = """
docker() {
    printf '%s\\n' "$4"
    if [ "$4" = run ]; then return "$MENU_TEST_MIGRATION_STATUS"; fi
}
"""
        for status, operations in ((0, ["config", "stop", "run", "up"]), (7, ["config", "stop", "run"])):
            with self.subTest(migration_status=status):
                result = subprocess.run(
                    ["sh", "-c", docker_stub + commands],
                    env={**os.environ, "MENU_TEST_MIGRATION_STATUS": str(status)}, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual(result.stdout.splitlines(), operations)
