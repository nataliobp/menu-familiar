import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
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

    def test_proxy_settings_require_an_exact_allowed_host_and_peer_ip(self):
        environment = {
            "DJANGO_SECRET_KEY": "test", "DJANGO_DB_PATH": "/tmp/disposable.sqlite3",
            "DJANGO_ALLOWED_HOSTS": "192.168.1.22,homeserver.tail02b38e.ts.net",
            "DJANGO_TAILSCALE_HOST": "homeserver.tail02b38e.ts.net", "DJANGO_TAILSCALE_PROXY_IP": "172.24.0.1",
        }
        self.assertEqual(self.run_settings(**environment).returncode, 0)
        for invalid in (
            {"DJANGO_TAILSCALE_PROXY_IP": ""}, {"DJANGO_TAILSCALE_PROXY_IP": "172.24.0.0/16"},
            {"DJANGO_ALLOWED_HOSTS": "192.168.1.22"}, {"DJANGO_TAILSCALE_HOST": "https://homeserver.tail02b38e.ts.net"},
        ):
            with self.subTest(invalid=invalid):
                self.assertNotEqual(self.run_settings(**(environment | invalid)).returncode, 0)

    def test_release_runbook_starts_service_only_after_successful_migration(self):
        root = Path(__file__).resolve().parents[2]
        release = (root / "README.md").read_text(encoding="utf-8").split("## Updates", 1)[1]
        update = release.split("Run the migration and start only if it succeeds.", 1)[1]
        commands = update.split("```bash\n", 1)[1].split("```", 1)[0]
        # Intercept the actual wrappers used by the runbook before they reach Docker.
        with TemporaryDirectory() as directory:
            sudo = Path(directory) / "sudo"
            sudo.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$9"\n'
                'if [ "$9" = run ]; then exit "$MENU_TEST_MIGRATION_STATUS"; fi\n',
                encoding="utf-8",
            )
            sudo.chmod(0o700)
            for status, operations in ((0, ["config", "run", "up", "ps"]), (7, ["config", "run"])):
                with self.subTest(migration_status=status):
                    result = subprocess.run(
                        ["sh", "-c", commands],
                        cwd=root,
                        env={**os.environ, "MENU_TEST_MIGRATION_STATUS": str(status),
                             "PATH": f"{directory}{os.pathsep}{os.environ['PATH']}"},
                        capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, status, result.stderr)
                    self.assertEqual(result.stdout.splitlines(), operations)
