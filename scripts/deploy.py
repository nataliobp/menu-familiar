"""Owner-operated deployment of the existing Menú Familiar Compose service."""

from datetime import date, datetime, timezone
import fcntl
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
from tempfile import NamedTemporaryFile, TemporaryDirectory, mkdtemp
from time import monotonic, sleep
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPErrorProcessor, ProxyHandler, build_opener

REPO = Path(__file__).resolve().parents[1]
if __package__:
    from .deploy_ui import Dashboard, latest
else:
    # The owner launcher uses -I, which excludes the script directory.
    sys.path.append(str(REPO / "scripts"))
    from deploy_ui import Dashboard, latest

STATE = Path.home() / "menu-familiar-deployments"
DATA = "/var/lib/menu-familiar/data"
SERVICE = "menu-familiar"
LAN = "192.168.1.22"
PORTS = {"8000/tcp": [{"HostIp": LAN, "HostPort": "18766"}],
         "8001/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18768"}]}
IMAGE_ID = re.compile(r"sha256:[a-f0-9]{64}")
COMMIT = re.compile(r"[a-f0-9]{40,64}")
TAIL_HOST = re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)*\.ts\.net")
APP_PATHS = ("/menu/", "/plats/", "/compra/", "/static/menus/app.css")
WEEKLY_PATHS = ("/menu/", "/compra/")
WEEK_PATH = re.compile(r"(/(?:menu|compra)/)([0-9]{4}-[0-9]{2}-[0-9]{2})/")
SAFE_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"}


class DeploymentError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise DeploymentError(message)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_write(path, content):
    with NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as file:
        temporary = Path(file.name)
        try:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
            temporary.replace(path)
            directory = os.open(path.parent, os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)


def command(label, args, *, env=None, cwd=REPO, output=None, log=None, stdin=None, timeout=None):
    # Docker/Compose/Git errors can include environment values, URLs and family
    # records. Persist only the stage and exit status. Synthetic gates log fully.
    try:
        result = subprocess.run(
            args, cwd=cwd, env=env, input=stdin, stdin=None if stdin is not None else subprocess.DEVNULL,
            stdout=log if log is not None else subprocess.PIPE if output is None else output,
            stderr=log if log is not None else subprocess.DEVNULL,
            timeout=timeout, check=False,
        )
    except OSError as error:
        raise DeploymentError(f"{label}: OS error {error.errno}") from None
    except subprocess.TimeoutExpired:
        raise DeploymentError(f"{label}: timed out") from None
    require(result.returncode == 0, f"{label}: exit {result.returncode}")
    return result.stdout.decode().strip() if result.stdout is not None else None


class RawResponses(HTTPErrorProcessor):
    def http_response(self, request, response):
        # Inspect status and Location before urllib dispatches to redirect handlers.
        return response

    https_response = http_response


def weekly_redirect(origin, path, location):
    if not location or re.search(r"[\s\x00-\x1f\x7f\\?#]", location):
        return None
    try:
        target = urlsplit(urljoin(origin + path, location))
        match = WEEK_PATH.fullmatch(target.path)
        if (f"{target.scheme}://{target.netloc.lower()}" == origin
                and match and match[1] == path and date.fromisoformat(match[2]).weekday() == 0):
            return origin + target.path
    except ValueError:
        return None


def smoke(tail_host, report):
    opener = build_opener(ProxyHandler({}), RawResponses())

    def probe(origin, path, timeout):
        url = origin + path
        redirect = ""
        for first_request in (True, False):
            detail = redirect + url
            try:
                with opener.open(url, timeout=timeout) as response:
                    detail += f": HTTP {response.status}"
                    locations = response.headers.get_all("Location", [])
                    for location in locations:
                        detail += f" Location={location!r}"
                    if response.status == 200:
                        if path == "/healthz":
                            require(response.read(3) == b"OK", f"{detail}: expected body 'OK'")
                        else:
                            expected_type = "text/css" if path.endswith(".css") else "text/html"
                            require(response.headers.get_content_type() == expected_type,
                                    f"{detail}: expected {expected_type}")
                            require(response.read(512).strip(), f"{detail}: empty or blank body")
                        return
                    if first_request and response.status == 302 and path in WEEKLY_PATHS and len(locations) == 1:
                        target = weekly_redirect(origin, path, locations[0])
                        if target:
                            redirect = f"{detail} -> "
                            url = target
                            continue
                    if 300 <= response.status < 400:
                        raise DeploymentError(f"{detail}: unexpected redirect")
                    raise DeploymentError(f"{detail}: expected HTTP 200")
            except (OSError, HTTPException) as error:
                raise DeploymentError(f"{detail}: {error}") from None

    for name, origin in (("LAN", f"http://{LAN}:18766"), ("HTTPS", f"https://{tail_host}:8443")):
        deadline = monotonic() + 45
        while True:
            try:
                probe(origin, "/healthz", 4)
            except DeploymentError:
                if monotonic() >= deadline:
                    raise
                sleep(1)
            else:
                break
        report("health", f"{name} /healthz passed")
        for path in APP_PATHS:
            probe(origin, path, 5)
        report("smoke", f"{name} menu, catalogue, shopping and stylesheet passed")


class Deployment:
    def __init__(self, run):
        self.run = run
        self.view = Dashboard(run)
        self.original_env = REPO / ".env"
        self.saved_env = run / "production.env"
        self.candidate_env = run / "candidate.env"
        self.compose_file = run / "compose.yaml"
        self.snapshot = run / "snapshot"
        self.pending_file = STATE / "recovery-required"
        self.migration_started = False
        self.cutover_started = False
        self.env_published = False
        self.old_commit = "unknown"
        self.stage = "preflight"

    def report(self, event, message, **fields):
        record = {"timestamp": now(), "event": event, "message": message, **fields}
        with (self.run / "events.jsonl").open("a") as log:
            log.write(json.dumps(record) + "\n")
            log.flush()
            os.fsync(log.fileno())
        self.view.accept(record)

    def report_recovery(self, event, message, **fields):
        try:
            self.report(event, message, **fields)
        except OSError:
            self.view.accept({"event": event})

    def git(self, *args, **options):
        return command("Git " + args[0], ["git", *args], **options)

    def docker(self, label, *args, **options):
        # Existing OS authorization in the owner's terminal. Fix the Docker
        # endpoint and discard contextual environment overrides.
        return command(label, ["sudo", "-n", "/usr/bin/docker", "--host", "unix:///var/run/docker.sock", *args],
                       env=SAFE_ENV, **options)

    def compose(self, env_file, label, *args):
        return self.docker(label, "compose", "--project-name", SERVICE, "--env-file", str(env_file),
                           "--project-directory", str(REPO), "-f", str(self.compose_file), *args)

    def clean_head(self):
        require(not self.git("status", "--porcelain=v1", "--untracked-files=all",
                             "--ignore-submodules=none"), "Commit or remove working tree changes before deploying")
        return self.git("rev-parse", "--verify", "HEAD")

    def current_container(self, env_file):
        value = self.compose(env_file, "Find Menu container", "ps", "--quiet", SERVICE)
        require(re.fullmatch(r"[a-f0-9]{12,64}", value), "Expected exactly one running Menú Familiar container")
        return value

    def inspect_runtime(self, container):
        # Inspect does return secrets. Keep its response in memory only.
        return json.loads(self.docker("Inspect Menu container", "container", "inspect", container))[0]

    def check_runtime(self, runtime, service):
        require(runtime["State"]["Running"], "Menú Familiar is stopped")
        labels = runtime["Config"]["Labels"]
        require(labels.get("com.docker.compose.project") == SERVICE
                and labels.get("com.docker.compose.service") == SERVICE, "Unexpected container ownership")
        require(runtime["HostConfig"]["PortBindings"] == PORTS, "Unexpected running port bindings")
        require(runtime["HostConfig"]["RestartPolicy"]["Name"] == service["restart"],
                "Unexpected running restart policy")
        mounts = runtime["Mounts"]
        require(len(mounts) == 1 and mounts[0]["Type"] == "bind" and mounts[0]["Source"] == DATA
                and mounts[0]["Destination"] == "/data" and mounts[0]["RW"], "Unexpected running data mount")
        actual_env = dict(entry.split("=", 1) for entry in runtime["Config"]["Env"])
        require(all(actual_env.get(key) == value for key, value in service["environment"].items()),
                "Running environment differs from the Compose configuration")
        networks = runtime["NetworkSettings"]["Networks"]
        require(set(networks) == {SERVICE + "_default"}
                and networks[SERVICE + "_default"]["Gateway"] == actual_env["DJANGO_TAILSCALE_PROXY_IP"],
                "Running Docker network differs from the configured Tailscale gateway")

    def read_config(self, env_file):
        config = json.loads(self.compose(env_file, "Validate Compose configuration", "config", "--format", "json"))
        require(set(config) == {"name", "services", "networks"} and config["name"] == SERVICE
                and set(config["services"]) == {SERVICE}, "Compose must define only Menú Familiar")
        service = config["services"][SERVICE]
        for key in ("command", "entrypoint"):
            if key in service and service[key] is None:
                del service[key]
        require(set(service) <= {"environment", "image", "networks", "ports", "restart", "volumes"}
                and service["networks"] == {"default": None} and service["restart"] == "unless-stopped",
                "Unsupported Compose service changes require owner review")
        require(config["networks"] in ({"default": {"name": SERVICE + "_default"}},
                                       {"default": {"name": SERVICE + "_default", "ipam": {}}}),
                "Unexpected Compose network configuration")
        ports = {f'{port["target"]}/{port["protocol"]}':
                 [{"HostIp": port["host_ip"], "HostPort": str(port["published"])}] for port in service["ports"]}
        require(len(service["ports"]) == len(PORTS) and ports == PORTS, "Unexpected Compose port bindings")
        require(service["volumes"] in ([{"type": "bind", "source": DATA, "target": "/data", "bind": {}}],
                                       [{"type": "bind", "source": DATA, "target": "/data",
                                         "bind": {"create_host_path": False}}]), "Unexpected Compose data mount")
        config_env = service["environment"]
        require(set(config_env) == {"DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS", "DJANGO_TAILSCALE_HOST",
                                    "DJANGO_TAILSCALE_PROXY_IP", "DJANGO_DB_PATH"}
                and config_env["DJANGO_DB_PATH"] == "/data/menu.sqlite3"
                and TAIL_HOST.fullmatch(config_env["DJANGO_TAILSCALE_HOST"] or ""),
                "Expected configured Django LAN and Tailscale endpoints")
        return service

    def verify(self, commit):
        self.report("tests_started", "Running Django and deployment tests in a disposable directory")
        with TemporaryDirectory(prefix="menu-deploy-", dir="/tmp") as work:
            work = Path(work)
            archive = work / "source.tar"
            with archive.open("wb") as output:
                command("Export committed source", ["git", "archive", commit], output=output)
            # Git archive is generated locally from the selected commit.
            command("Extract committed source", ["tar", "-xf", str(archive), "-C", str(work)])
            python = str(REPO / ".venv/bin/python")
            env = {**SAFE_ENV, "DJANGO_ENV": "development",
                   "DJANGO_DB_PATH": str(work / "unused.sqlite3"),
                   "DJANGO_TEST_DB_PATH": str(work / "test.sqlite3")}
            with (self.run / "django-verification.log").open("wb") as log:
                command("Django tests", [python, "manage.py", "test"], cwd=work, env=env, log=log)
                command("Deployment tests", [python, "-m", "unittest", "discover", "-s", "scripts/tests"],
                        cwd=work, env=env, log=log)
                command("Check model migration coverage",
                        [python, "manage.py", "makemigrations", "--check", "--dry-run"],
                        cwd=work, env=env, log=log)
            self.migration_script = (work / "scripts/deploy_migrations.py").read_bytes()
            verification_script = (work / "scripts/verify-docker.sh").read_bytes()
        self.report("tests_passed", "Django tests, deployment tests and migration coverage passed")
        with self.view.prompt():
            require(subprocess.run(["sudo", "-v"], env=SAFE_ENV, check=False).returncode == 0,
                    "Docker authorization failed")
        self.report("image_verification_started", "Building and verifying the committed image with disposable Docker resources")
        result = self.run / "verified-image"
        command("Docker build and verification",
                ["sh", "-s", "--", "--deployment-result", str(result), commit],
                env=SAFE_ENV, stdin=verification_script)
        image = result.read_text().strip()
        require(IMAGE_ID.fullmatch(image), "Invalid verified image ID")
        label = self.docker("Verify image revision", "image", "inspect", "--format",
                            '{{index .Config.Labels "org.opencontainers.image.revision"}}', image)
        require(label == commit, "Verified image revision does not match the deployment commit")
        self.report("image_verified", f"Docker verification passed for {image}", image_id=image)
        return image

    def maintenance(self, label, image, mounts, *args, root=False, stdin=None):
        options = ["--user", "0:0"] if root else []
        if stdin is not None:
            options += ["-i"]
        return self.docker(label, "run", "--rm", "--pull=never", "--network", "none", "--read-only",
                           "--label", f"menu-familiar.deployment={self.run.name}",
                           "--tmpfs", "/tmp:rw,mode=1777", *options, *mounts,
                           "-e", "DJANGO_SECRET_KEY=offline-deployment",
                           "-e", "DJANGO_ALLOWED_HOSTS=localhost",
                           "-e", "DJANGO_DB_PATH=/data/menu.sqlite3",
                           image, *args, stdin=stdin)

    def migrations(self, image, mode, pending=None, rehearsal=False):
        if rehearsal:
            mounts = ["--mount", f"type=bind,src={self.snapshot},dst=/backup,readonly", "--tmpfs", "/data:rw"]
            args = ["sh", "-ec", 'cp /backup/data/menu.sqlite3 /data/menu.sqlite3; exec python - "$@"',
                    "rehearsal", mode, json.dumps(pending)]
        else:
            mounts = ["--mount", f"type=bind,src={DATA},dst=/data" + (",readonly" if mode == "plan" else "")]
            args = ["python", "-", mode, json.dumps(pending)]
        return self.maintenance(f"{'Rehearsal' if rehearsal else 'Production'} migration {mode}", image,
                                mounts, *args, root=rehearsal, stdin=self.migration_script)

    def backup(self):
        self.snapshot.mkdir()
        self.maintenance("SQLite and photo backup", self.candidate,
                         ["--mount", f"type=bind,src={DATA},dst=/data,readonly",
                          "--mount", f"type=bind,src={self.snapshot},dst=/backup"],
                         "python", "manage.py", "backup_menu_data", "/backup/data", root=True)
        self.report("backup_verified", f"SQLite integrity, foreign keys and referenced photos verified at {self.snapshot / 'data'}")

    def replace_container(self, env_file, expected_image, service):
        self.compose(env_file, "Recreate Menú Familiar", "up", "--detach", "--no-deps", "--force-recreate",
                     "--no-build", "--pull", "never", SERVICE)
        runtime = self.inspect_runtime(self.current_container(env_file))
        require(runtime["Image"] == expected_image, "Running container image differs from selected image ID")
        self.check_runtime(runtime, service)

    def deploy(self):
        commit = self.clean_head()
        require(COMMIT.fullmatch(commit), "Invalid HEAD commit")
        branch = self.git("symbolic-ref", "--short", "HEAD")
        remote = self.git("config", "--get", f"branch.{branch}.remote")
        target = self.git("config", "--get", f"branch.{branch}.merge")
        require(remote != "." and target.startswith("refs/heads/"), "Configure a branch upstream before deploying")
        self.git("check-ref-format", target)
        self.git("remote", "get-url", "--push", "--", remote)
        self.report("candidate", f"Candidate commit {commit}", commit=commit)
        self.stage = "verification"
        self.candidate = self.verify(commit)

        self.stage = "production preflight"
        mode = self.original_env.lstat().st_mode
        require(stat.S_ISREG(mode) and not mode & 0o077, "Use a regular private .env file (chmod 600)")
        before = self.original_env.read_bytes()
        self.saved_env.write_bytes(before)
        self.compose_file.write_bytes(subprocess.check_output(
            ["git", "show", f"{commit}:compose.yaml"], cwd=REPO, stderr=subprocess.DEVNULL,
        ))
        self.old_service = self.read_config(self.saved_env)
        self.old_container = self.current_container(self.saved_env)
        runtime = self.inspect_runtime(self.old_container)
        self.check_runtime(runtime, self.old_service)
        self.old_image = runtime["Image"]
        require(IMAGE_ID.fullmatch(self.old_image), "Invalid production image ID")
        self.tail_host = self.old_service["environment"]["DJANGO_TAILSCALE_HOST"]
        old_ref = self.old_service["image"]
        actual_id = self.docker("Resolve production image", "image", "inspect", "--format", "{{.Id}}", old_ref)
        require(actual_id == self.old_image, "Configured image differs from running image")
        revision = runtime["Config"]["Labels"].get("org.opencontainers.image.revision", "")
        legacy = re.fullmatch(r"menu-familiar:verified-([a-f0-9]{40,64})", old_ref)
        self.old_commit = revision if COMMIT.fullmatch(revision) else legacy[1] if legacy else "unknown"
        self.report("production", f"Current production commit {self.old_commit}, image {self.old_image}",
                    commit=self.old_commit, image_id=self.old_image)
        (self.run / "image.txt").write_text(f"{old_ref}\n{self.old_image}\n")
        # Use the inspected content ID as the Compose image name. No tag can be
        # changed between verification and starting the container.
        candidate, changes = re.subn(rb"(?m)^MENU_IMAGE=[^\r\n]*", b"MENU_IMAGE=" + self.candidate.encode(), before)
        require(changes == 1, "Expected one MENU_IMAGE= assignment in .env")
        self.candidate_env.write_bytes(candidate)
        self.new_service = self.read_config(self.candidate_env)
        require(self.new_service == {**self.old_service, "image": self.candidate},
                "Candidate Compose configuration changes settings beyond the image")

        self.stage = "migration planning"
        pending = json.loads(self.migrations(self.candidate, "plan"))
        if pending:
            names = ", ".join(f"{app}.{name}" for app, name, _ in pending)
            self.report("migration_plan", f"Pending migrations: {names}")
            require(all(safe for _, _, safe in pending), "Pending migrations require explicit owner intervention")
        else:
            self.report("migration_plan", "No unapplied migrations")

        self.stage = "preparing backup"
        self.report("backup_started", f"Saving the current image and production configuration in {self.run}")
        # Archive the prior image before downtime. The paired data snapshot is
        # taken only after the running application has stopped accepting writes.
        with (self.run / "previous-image.tar").open("wb") as archive:
            self.docker("Save previous image", "image", "save", self.old_image, output=archive)
        require((self.run / "previous-image.tar").stat().st_size > 0, "Previous image archive is empty")
        require(self.clean_head() == commit and self.original_env.read_bytes() == before
                and self.current_container(self.saved_env) == self.old_container,
                "Checkout or production configuration changed during verification")

        self.stage = "backup"
        atomic_write(self.pending_file, (self.run.name + "\n").encode())
        self.cutover_started = True
        self.compose(self.saved_env, "Stop Menú Familiar for backup", "stop", SERVICE)
        require(not self.inspect_runtime(self.old_container)["State"]["Running"], "Container did not stop")
        self.backup()

        self.stage = "migration rehearsal"
        confirmed = json.loads(self.migrations(self.candidate, "plan"))
        require(confirmed == pending, "Migration plan changed during backup")
        if pending:
            self.migrations(self.candidate, "apply", pending, rehearsal=True)
            self.report("migration_rehearsed", "Migrations passed on a disposable copy of the backup")
            self.stage = "production migration"
            self.report("migration_started", "Applying approved production migrations")
            self.migration_started = True
            self.migrations(self.candidate, "apply", pending)
            self.report("migration_applied", "Production migrations and SQLite checks passed")

        self.stage = "container recreation"
        self.report("deploying", "Recreating only the Menú Familiar container")
        self.replace_container(self.candidate_env, self.candidate, self.new_service)
        self.stage = "health checks"
        self.report("checks_started", "Starting LAN and HTTPS checks")
        smoke(self.tail_host, self.report)
        self.stage = "recording deployment"
        require(self.original_env.read_bytes() == before, "Production .env changed during cutover")
        self.env_published = True
        atomic_write(self.original_env, candidate)
        self.report("deployed", f"Deployed commit {commit}, image {self.candidate}",
                    commit=commit, image_id=self.candidate)
        self.pending_file.unlink()
        self.cutover_started = False
        self.stage = "GitHub synchronization"
        try:
            command("GitHub push",
                    ["git", "-c", "credential.interactive=false", "-c", f"remote.{remote}.mirror=false",
                     "push", "--no-verify", "--no-follow-tags", "--recurse-submodules=no", "--",
                     remote, f"{commit}:{target}"],
                    env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_SSH_COMMAND": "ssh -o BatchMode=yes",
                         "GIT_ASKPASS": "/bin/false", "SSH_ASKPASS": "/bin/false"}, timeout=60)
        except DeploymentError as error:
            self.report("sync_pending", f"GitHub synchronization pending ({error})",
                        commit=commit, remote=remote, target=target)
        else:
            self.report("sync_complete", "GitHub synchronization passed", commit=commit, remote=remote, target=target)
        self.report("complete", f"Final deployed commit {commit}, image {self.candidate}",
                    commit=commit, image_id=self.candidate)

    def recover(self):
        if not self.cutover_started:
            return
        if self.migration_started:
            self.report_recovery("recovery_required", f"Migration may have changed SQLite. Use recovery files at {self.run}")
            self.compose(self.saved_env, "Stop candidate for manual recovery", "stop", SERVICE)
            self.report_recovery("service_stopped", "Menú Familiar is stopped pending manual recovery")
            return
        self.report_recovery("rollback_started", "Restoring the previous container with production data intact")
        current = self.compose(self.saved_env, "Find previous container", "ps", "--all", "--quiet", SERVICE)
        if current == self.old_container:
            self.docker("Restart previous container", "container", "start", self.old_container)
            self.check_runtime(self.inspect_runtime(self.old_container), self.old_service)
        else:
            # The original tag was checked in preflight, but an immutable ID is
            # also used on rollback so that a changed tag cannot start other code.
            rollback_env = self.run / "rollback.env"
            rollback_env.write_bytes(re.sub(rb"(?m)^MENU_IMAGE=[^\r\n]*",
                                            b"MENU_IMAGE=" + self.old_image.encode(), self.saved_env.read_bytes()))
            self.replace_container(rollback_env, self.old_image, self.old_service)
        if self.env_published:
            atomic_write(self.original_env, self.saved_env.read_bytes())
        smoke(self.tail_host, self.report_recovery)
        self.report_recovery("rolled_back",
                             f"Rollback verified. Final production commit {self.old_commit}, image {self.old_image}",
                             commit=self.old_commit, image_id=self.old_image)
        self.pending_file.unlink()


def interrupted(signum, frame):
    raise DeploymentError(f"Interrupted by signal {signum}")


def main(args):
    os.umask(0o077)
    if args == ["--latest"]:
        run_name = (STATE / "latest").read_text().strip()
        require(re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[a-z0-9_]+", run_name), "Invalid deployment history")
        latest(STATE / run_name)
        return 0
    require(not args, "Usage: ./deploy.sh [--latest]")
    require(os.getuid() != 0, "Run as the authorized repository owner without sudo")
    info = STATE.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077,
            "Deployment directory must be private and owned by the repository owner")
    with (STATE / "deploy.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise DeploymentError("Another Menú Familiar deployment holds the lock") from None
        pending_file = STATE / "recovery-required"
        require(not pending_file.exists(), f"Resolve the incomplete deployment in {STATE} before retrying")
        run = Path(mkdtemp(prefix=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-"), dir=STATE))
        atomic_write(STATE / "latest", (run.name + "\n").encode())
        deploy = Deployment(run)
        for sig in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, interrupted)
        exit_status = 0
        with deploy.view.live():
            try:
                deploy.deploy()
            except (Exception, KeyboardInterrupt) as error:
                message = str(error) if isinstance(error, DeploymentError) else type(error).__name__
                deploy.report_recovery("failed", f"Failed during {deploy.stage} ({message})")
                try:
                    deploy.recover()
                except (Exception, KeyboardInterrupt) as error:
                    message = str(error) if isinstance(error, DeploymentError) else type(error).__name__
                    deploy.report_recovery("recovery_failed", f"Recovery needs owner attention ({message}). See {run}")
                exit_status = 1
        if not deploy.view.console:
            deploy.view.summary()
    return exit_status


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (DeploymentError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
