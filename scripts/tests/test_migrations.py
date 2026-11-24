"""Exercise the deployment migration gate against real Django and SQLite."""

from contextlib import closing
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from scripts.deploy import REPO, SAFE_ENV

ADD_COLUMN = '''
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("menus", "0012_pizza_category")]
    operations = [
        migrations.AddField("dishrecord", "deployment_test", models.TextField(null=True)),
    ]
'''
SAFE_PLAN = [["menus", "0013_deployment_test", True]]


@unittest.skipUnless(importlib.util.find_spec("django"), "Run with the project's Python environment")
class MigrationTests(unittest.TestCase):
    def setUp(self):
        root = TemporaryDirectory(prefix="menu-test-migrations-")
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.source = self.root / "source"
        self.source.mkdir()
        for folder in ("config", "menus"):
            shutil.copytree(REPO / folder, self.source / folder, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(REPO / "manage.py", self.source / "manage.py")
        self.database = self.root / "menu.sqlite3"
        self.env = {**SAFE_ENV, "DJANGO_ENV": "development", "DJANGO_DB_PATH": str(self.database)}
        self.script = (REPO / "scripts/deploy_migrations.py").read_text()

    def run_python(self, *arguments, script=None, check=True, env=None):
        return subprocess.run([sys.executable, *arguments], cwd=self.source, env=env or self.env,
                              input=script, capture_output=True, text=True, check=check)

    def test_production_migration_gate_blocks_pizza_data_migration(self):
        self.run_python("manage.py", "migrate", "--noinput")
        self.run_python("manage.py", "migrate", "menus", "0011", "--noinput")
        result = self.run_python("-", "plan", script=self.script)
        self.assertEqual(json.loads(result.stdout), [["menus", "0012_pizza_category", False]])
        refused = self.run_python("-", "apply", result.stdout, script=self.script, check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("requires manual review", refused.stderr)
        self.assertEqual(self.run_python("-", "plan", script=self.script).stdout, result.stdout)

    def test_supported_migration_uses_real_backup_copy_without_changing_source(self):
        self.run_python("manage.py", "migrate", "--noinput")
        self.run_python("manage.py", "shell", "-c",
                        'import hashlib; from django.conf import settings; '
                        'from menus.models import CatalogueSourceRecord, DishRecord; '
                        'from menus.infrastructure.recipe_photos import Photo, PhotoStore; '
                        'dish = DishRecord.objects.create('
                        'name="Plat sintètic", primary_category_id="cereals", meal_preference="both", '
                        'special_occasion=False); raw = b"synthetic photograph"; '
                        'digest = hashlib.sha256(raw).hexdigest(); '
                        'PhotoStore(settings.RECIPE_PHOTO_ROOT).store(1, Photo(digest, raw)); '
                        'CatalogueSourceRecord.objects.create(source_id=1, dish=dish, photo_digest=digest)')
        backup = self.root / "paired-backup"
        self.run_python("manage.py", "backup_menu_data", str(backup))
        self.assertEqual([photo.read_bytes() for photo in (backup / "recipe-photos").iterdir()],
                         [b"synthetic photograph"])
        restore = self.root / "restore.sqlite3"
        shutil.copyfile(backup / "menu.sqlite3", restore)
        (self.source / "menus/migrations/0013_deployment_test.py").write_text(ADD_COLUMN)
        result = self.run_python("-", "plan", script=self.script)
        self.assertEqual(json.loads(result.stdout), SAFE_PLAN)
        restore_env = {**self.env, "DJANGO_DB_PATH": str(restore)}
        self.run_python("-", "apply", result.stdout, script=self.script, env=restore_env)
        self.assertEqual(json.loads(self.run_python("-", "plan", script=self.script, env=restore_env).stdout), [])
        self.assertEqual(json.loads(self.run_python("-", "plan", script=self.script).stdout), SAFE_PLAN)
        with closing(sqlite3.connect(restore)) as connection:
            self.assertEqual(connection.execute("SELECT name, deployment_test FROM menus_dishrecord").fetchall(),
                             [("Plat sintètic", None)])
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchall(), [("ok",)])


if __name__ == "__main__":
    unittest.main()
