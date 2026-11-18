import os
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
        self.assertEqual(self.run_settings(DJANGO_ENV="development").returncode, 0)
