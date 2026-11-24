"""Exercise cutover with an isolated Git remote, synthetic config and Docker doubles."""

from contextlib import redirect_stdout
import fcntl
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import deploy

OLD_IMAGE = "sha256:" + "1" * 64
NEW_IMAGE = "sha256:" + "2" * 64
OLD = "1" * 64
NEW = "2" * 64
VERIFIER = deploy.REPO / "scripts/verify-docker.sh"
SAFE_PLAN = [["menus", "0100_add_optional_field", True]]
MANUAL_PLAN = [["menus", "0012_pizza_category", False]]


class Host(deploy.Deployment):
    def verify(self, commit):
        if self.failure in ("test", "build"):
            raise deploy.DeploymentError(f"Synthetic {self.failure} failure")
        return NEW_IMAGE

    def git(self, *args, **options):
        return deploy.command("Git " + args[0], ["git", *args], cwd=self.original_env.parent, **options)

    def read_config(self, env_file):
        image = next(line.removeprefix("MENU_IMAGE=") for line in env_file.read_text().splitlines()
                     if line.startswith("MENU_IMAGE="))
        return {"image": image, "environment": {"DJANGO_TAILSCALE_HOST": "test.example.ts.net"}}

    def inspect_runtime(self, container):
        return {"Image": self.image, "State": {"Running": self.running},
                "Config": {"Labels": {}}}

    def check_runtime(self, runtime, service):
        assert runtime["State"]["Running"]

    def compose(self, env_file, label, *args):
        self.calls.append(args)
        action = args[0]
        if action == "ps":
            return self.container if self.running or "--all" in args else ""
        if action == "stop":
            self.running = False
            return ""
        assert action == "up"
        service = self.read_config(env_file)
        self.image = service["image"]
        self.container = NEW
        self.running = True
        return ""

    def docker(self, label, *args, output=None, **options):
        self.calls.append(args)
        match args[:2]:
            case "image", "inspect":
                return OLD_IMAGE
            case "image", "save":
                output.write(b"synthetic image archive")
            case "container", "start":
                assert args[2] == OLD
                self.running = True
            case _:
                raise AssertionError(args)

    def migrations(self, image, mode, pending=None, rehearsal=False):
        self.calls.append((mode, rehearsal))
        assert image == NEW_IMAGE
        if mode == "plan":
            return json.dumps(self.plan)
        if self.failure == "rehearsal" and rehearsal:
            raise deploy.DeploymentError("Synthetic rehearsal failure")
        if not rehearsal:
            self.database.write_text("synthetic migrated data")
            if self.failure == "migration":
                raise deploy.DeploymentError("Synthetic live migration failure")

    def backup(self):
        assert not self.running
        self.calls.append(("backup",))
        if self.failure == "backup":
            raise deploy.DeploymentError("Synthetic backup failure")
        self.snapshot.mkdir()
        shutil.copyfile(self.database, self.snapshot / "menu.sqlite3")
        self.report("backup_verified", "Synthetic backup passed")


class CutoverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(prefix="menu-test-deploy-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.remote = self.root / "remote.git"
        self.run_git(self.root, "init", "--bare", str(self.remote))
        self.repo.mkdir()
        self.run_git(self.repo, "init", "-b", "main")
        self.run_git(self.repo, "config", "user.name", "Synthetic Operator")
        self.run_git(self.repo, "config", "user.email", "operator@example.invalid")
        (self.repo / "compose.yaml").write_text("synthetic configuration")
        (self.repo / ".gitignore").write_text(".env\n")
        self.run_git(self.repo, "add", ".")
        self.run_git(self.repo, "commit", "-m", "Synthetic candidate")
        self.commit = self.run_git(self.repo, "rev-parse", "HEAD").strip()
        self.run_git(self.repo, "remote", "add", "origin", str(self.remote))
        self.run_git(self.repo, "config", "branch.main.remote", "origin")
        self.run_git(self.repo, "config", "branch.main.merge", "refs/heads/main")
        state = self.root / "state"
        state.mkdir(mode=0o700)
        run = state / "run"
        run.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(deploy, "REPO", self.repo).start()
        patch.object(deploy, "STATE", state).start()

        original_command = deploy.command

        def command_in_repo(label, args, **options):
            options.setdefault("cwd", self.repo)
            return original_command(label, args, **options)

        patch.object(deploy, "command", command_in_repo).start()
        self.host = Host(run)
        self.host.database = self.root / "synthetic.sqlite3"
        self.host.database.write_text("synthetic original data")
        self.host.original_env.write_text(f"SECRET=synthetic-private\nMENU_IMAGE={OLD_IMAGE}\n")
        self.host.original_env.chmod(0o600)
        self.host.failure = None
        self.host.running = True
        self.host.plan = []
        self.host.image = OLD_IMAGE
        self.host.container = OLD
        self.host.calls = []

        def smoke(tail_host, report):
            if self.host.failure == "health" and self.host.image == NEW_IMAGE:
                raise deploy.DeploymentError("Synthetic HTTPS health failure")
            if self.host.failure == "rollback-health":
                raise deploy.DeploymentError("Synthetic health failure on both images")
            report("health", "Synthetic health passed")

        patch.object(deploy, "smoke", smoke).start()
        self.log = io.StringIO()

    @staticmethod
    def run_git(cwd, *args):
        return subprocess.check_output(["git", *args], cwd=cwd, stderr=subprocess.DEVNULL, text=True)

    def attempt(self, failure=None, plan=None):
        self.host.failure = failure
        self.host.plan = plan or []
        with redirect_stdout(self.log):
            try:
                self.host.deploy()
            except deploy.DeploymentError:
                self.host.recover()
                raise

    def pushed(self):
        return subprocess.run(["git", "--git-dir", self.remote, "rev-parse", "--verify", "refs/heads/main"],
                              capture_output=True, text=True).stdout.strip()

    def assert_original(self):
        self.assertIn(OLD_IMAGE, self.host.original_env.read_text())
        self.assertEqual(self.host.database.read_text(), "synthetic original data")
        self.assertEqual(self.pushed(), "")
        self.assertFalse(self.host.pending_file.exists())

    def test_success_pushes_exact_commit_after_cutover_and_keeps_backup(self):
        self.attempt()
        self.assertEqual(self.host.image, NEW_IMAGE)
        self.assertEqual(self.pushed(), self.commit)
        self.assertIn(NEW_IMAGE, self.host.original_env.read_text())
        self.assertEqual((self.host.snapshot / "menu.sqlite3").read_text(), "synthetic original data")
        self.assertFalse(self.host.pending_file.exists())
        events = [json.loads(line)["event"] for line in (self.host.run / "events.jsonl").read_text().splitlines()]
        self.assertLess(events.index("backup_verified"), events.index("deployed"))
        self.assertLess(events.index("deployed"), events.index("sync_complete"))
        self.assertNotIn("synthetic-private", self.log.getvalue())
        self.assertIn(("up", "--detach", "--no-deps", "--force-recreate", "--no-build", "--pull", "never",
                       deploy.SERVICE), self.host.calls)

    def test_dirty_tree_never_reaches_docker(self):
        (self.repo / "untracked").touch()
        with self.assertRaisesRegex(deploy.DeploymentError, "working tree"):
            self.attempt()
        self.assertEqual(self.host.calls, [])
        self.assert_original()

    def test_failed_test_and_build_never_reach_production(self):
        for gate in ("test", "build"):
            with self.subTest(gate=gate), self.assertRaisesRegex(deploy.DeploymentError, gate):
                self.attempt(gate)
            self.assertEqual(self.host.calls, [])
            self.assert_original()

    def test_verifier_uses_only_the_selected_docker_endpoint(self):
        directory = self.root / "bin"
        directory.mkdir()
        stub = directory / "sudo"
        stub.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >>"$SYNTHETIC_CALLS"\n[ "$5" = info ]\n')
        stub.chmod(0o700)
        calls = self.root / "docker-calls"
        result_file = self.host.run / "verified-image"
        result = subprocess.run(
            ["sh", "-s", "--", "--deployment-result", result_file, self.commit],
            cwd=self.repo, env={**deploy.SAFE_ENV, "PATH": f"{directory}:/usr/bin:/bin",
                                "SYNTHETIC_CALLS": str(calls)},
            input=VERIFIER.read_bytes(), capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        prefix = "-n /usr/bin/docker --host unix:///var/run/docker.sock "
        self.assertEqual(calls.read_text().splitlines(), [
            prefix + "info --format Docker server {{.ServerVersion}}",
            prefix + "compose version",
        ])
        self.assertIn("FAIL", (self.host.run / "docker-verification.log").read_text())
        self.assertFalse(result_file.exists())

    def test_manual_migration_is_blocked_before_stop(self):
        with self.assertRaisesRegex(deploy.DeploymentError, "explicit owner intervention"):
            self.attempt(plan=MANUAL_PLAN)
        self.assertTrue(self.host.running)
        self.assertNotIn(("backup",), self.host.calls)
        self.assert_original()

    def test_backup_failure_restarts_previous_container(self):
        with self.assertRaisesRegex(deploy.DeploymentError, "backup failure"):
            self.attempt("backup")
        self.assertIn(("container", "start", OLD), self.host.calls)
        self.assertTrue(self.host.running)
        self.assert_original()

    def test_rehearsal_failure_preserves_old_database_and_restarts_app(self):
        with self.assertRaisesRegex(deploy.DeploymentError, "rehearsal failure"):
            self.attempt("rehearsal", SAFE_PLAN)
        self.assertTrue(self.host.running)
        self.assertNotIn(("apply", False), self.host.calls)
        self.assert_original()

    def test_migration_failure_leaves_service_stopped_with_backup_and_recovery_marker(self):
        with self.assertRaisesRegex(deploy.DeploymentError, "live migration failure"):
            self.attempt("migration", SAFE_PLAN)
        self.assertFalse(self.host.running)
        self.assertTrue(self.host.pending_file.exists())
        self.assertEqual(self.host.database.read_text(), "synthetic migrated data")
        self.assertEqual((self.host.snapshot / "menu.sqlite3").read_text(), "synthetic original data")
        self.assertEqual(self.pushed(), "")

    def test_failed_health_rolls_back_code_only(self):
        with self.assertRaisesRegex(deploy.DeploymentError, "HTTPS health"):
            self.attempt("health")
        self.assertEqual(self.host.image, OLD_IMAGE)
        self.assertTrue(self.host.running)
        self.assert_original()

    def test_failed_health_after_migration_requires_manual_recovery(self):
        with self.assertRaisesRegex(deploy.DeploymentError, "HTTPS health"):
            self.attempt("health", SAFE_PLAN)
        self.assertEqual(self.host.image, NEW_IMAGE)
        self.assertFalse(self.host.running)
        self.assertTrue(self.host.pending_file.exists())
        self.assertEqual(self.pushed(), "")

    def test_supported_migration_is_rehearsed_and_applied_before_cutover(self):
        self.attempt(plan=SAFE_PLAN)
        self.assertLess(self.host.calls.index(("apply", True)), self.host.calls.index(("apply", False)))
        self.assertEqual(self.host.database.read_text(), "synthetic migrated data")
        self.assertEqual((self.host.snapshot / "menu.sqlite3").read_text(), "synthetic original data")
        self.assertEqual(self.pushed(), self.commit)

    def test_concurrent_deployment_is_refused(self):
        self.addCleanup(os.umask, os.umask(0o077))
        with (deploy.STATE / "deploy.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(deploy.DeploymentError, "holds the lock"):
                deploy.main([])

    def test_rollback_smoke_failure_keeps_recovery_marker(self):
        with self.assertRaisesRegex(deploy.DeploymentError, "health failure"):
            self.attempt("rollback-health")
        self.assertEqual(self.host.image, OLD_IMAGE)
        self.assertTrue(self.host.pending_file.exists())

    def test_remote_unavailable_reports_pending_while_keeping_deployed_image(self):
        self.run_git(self.repo, "remote", "set-url", "origin", str(self.root / "unavailable.git"))
        self.attempt()
        self.assertEqual(self.host.image, NEW_IMAGE)
        self.assertTrue(self.host.running)
        self.assertFalse(self.host.pending_file.exists())
        self.assertIn("synchronization pending", self.log.getvalue())


class ComposeConfigTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("docker"), "Docker CLI required for offline Compose validation")
    def test_real_compose_accepts_pinned_id_and_existing_ports(self):
        with TemporaryDirectory() as work:
            work = Path(work)
            instance = deploy.Deployment(work)
            instance.compose_file.write_bytes((deploy.REPO / "compose.yaml").read_bytes())
            instance.candidate_env.write_text(
                f"MENU_IMAGE={NEW_IMAGE}\nMENU_BIND_ADDRESS={deploy.LAN}\nMENU_DATA_DIR={deploy.DATA}\n"
                "DJANGO_SECRET_KEY=synthetic-only\nDJANGO_ALLOWED_HOSTS=192.168.1.22,test.example.ts.net\n"
                "DJANGO_TAILSCALE_HOST=test.example.ts.net\nDJANGO_TAILSCALE_PROXY_IP=172.18.0.1\n"
            )
            with patch.object(instance, "docker", side_effect=lambda label, *args: deploy.command(
                label, ["docker", *args], env=deploy.SAFE_ENV
            )):
                result = instance.read_config(instance.candidate_env)
            self.assertEqual(result["image"], NEW_IMAGE)


if __name__ == "__main__":
    unittest.main()
