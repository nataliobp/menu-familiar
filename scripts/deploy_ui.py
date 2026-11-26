"""Terminal views of the deployment journal. Only display allowlisted metadata."""

from contextlib import contextmanager, nullcontext
from datetime import datetime
import json
import re
import sys
from time import monotonic

try:
    from rich.console import Console, Group
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.table import Table
    from rich.text import Text
except ImportError:
    Console = None


STAGES = (
    "Automated tests", "Docker build and verification",
    "Production preflight", "SQLite and photo backup",
    "Migrations", "Container deployment", "LAN and HTTPS health checks",
    "GitHub synchronization",
)
# Journal boundaries, including the first observed probe in older journals.
BOUNDARIES = {
    "tests_started": 0, "tests_passed": 1, "image_verified": 2,
    "backup_started": 3, "backup_verified": 4, "deploying": 5,
    "checks_started": 6, "health": 6, "smoke": 6, "deployed": 7,
}
OPERATIONS = {
    "candidate": "Preparing tests", "tests_passed": "Docker authorization",
    "image_verification_started": STAGES[1], "migration_plan": "Reviewing migration plan",
    "migration_started": "Applying migrations", "migration_rehearsed": "Migration rehearsal verified",
    "rollback_started": "Restoring previous version",
}
RESULTS = {
    "failed": "Deployment failed", "rolled_back": "Rollback successful",
    "recovery_failed": "Recovery required", "recovery_required": "Recovery required",
    "sync_pending": "Deployment successful · GitHub synchronization pending",
    "complete": "Deployment successful",
}
FAILURE_HINTS = {
    "Commit or remove working tree changes": "Commit or remove working tree changes",
    "Docker authorization failed": "Docker authorization failed",
    "Pending migrations require explicit owner intervention": "Migrations require manual review",
    "Interrupted by signal": "Deployment interrupted",
    "Django tests:": "Django tests failed · django-verification.log",
    "Deployment tests:": "Deployment tests failed · django-verification.log",
    "Docker build and verification:": "Docker verification failed · docker-verification.log",
}
PENDING, RUNNING, OK, FAILED = "Pending", "Running", "Success", "Failure"
COLORS = {PENDING: "dim", RUNNING: "cyan", OK: "green", FAILED: "red"}


def duration(seconds):
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    return f"{minutes}:{seconds:02}"


class Dashboard:
    def __init__(self, run, stream=None, clock=monotonic):
        self.run = run
        self.stream = sys.stdout if stream is None else stream
        self.clock = clock
        self.start = clock()
        self.rows = [(PENDING, None, None) for _ in STAGES]
        self.active = None
        self.current = self.candidate = "—"
        self.operation = "Preparing deployment"
        self.result = self.error = ""
        self.console = Console(file=self.stream) if Console and self.stream.isatty() else None
        self.spinner = Spinner("dots", text=Text(RUNNING, style="cyan")) if self.console else None
        self.display = None
        if self.console and not self.console.is_interactive:
            self.console = None

    def live(self):
        if self.console:
            self.display = Live(console=self.console, get_renderable=self.render, refresh_per_second=4,
                                redirect_stdout=False, redirect_stderr=False)
            return self.display
        return nullcontext()

    @contextmanager
    def prompt(self):
        # Leave sudo in sole control of its terminal prompt.
        if self.display:
            self.display.stop()
        try:
            yield
        finally:
            if self.display:
                self.display.start()

    def finish_stage(self, status, when):
        if self.active is not None:
            self.rows[self.active] = (status, self.rows[self.active][1], when)
            self.active = None

    def accept(self, record, when=None, announce=True):
        when = self.clock() if when is None else when
        event = record.get("event")
        commit = record.get("commit")
        if isinstance(commit, str) and re.fullmatch("[a-f0-9]{40,64}", commit):
            if event == "production":
                self.current = commit[:12]
            elif event == "candidate":
                self.candidate = commit[:12]
        previous_operation = self.operation
        stage = BOUNDARIES.get(event)
        if event == "failed" and str(record.get("message", "")).startswith("Failed during health checks ("):
            stage = 6
        if stage is not None and stage != self.active and not self.result:
            self.finish_stage(OK, when)
            self.active = stage
            self.rows[stage] = (RUNNING, when, None)
            self.operation = STAGES[stage]
        if event in OPERATIONS:
            self.operation = OPERATIONS[event]
        if event == "failed":
            message = record.get("message", "")
            self.error = self.operation
            if isinstance(message, str):
                for reason, explanation in FAILURE_HINTS.items():
                    if reason in message:
                        self.error = explanation
                        break
            self.finish_stage(FAILED, when)
        if event in ("sync_pending", "sync_complete"):
            self.finish_stage(PENDING if event == "sync_pending" else OK, when)
        if event in RESULTS and not (event == "complete" and self.result):
            self.result = RESULTS[event]
            self.operation = self.result
        if announce and not self.console and previous_operation != self.operation:
            self.write(f"{duration(when - self.start)}  {self.operation}")

    def write(self, *lines):
        # A closed output pipe must never interrupt deployment or recovery.
        try:
            print(*lines, sep="\n", file=self.stream, flush=True)
        except OSError:
            pass

    def frame(self):
        now = self.clock()
        rows = [(name, state, "—" if start is None else duration((now if end is None else end) - start))
                for name, (state, start, end) in zip(STAGES, self.rows)]
        heading = f"Menú Familiar · {duration(now - self.start)}"
        commits = f"Current production {self.current}  ·  Candidate {self.candidate}"
        footer = [self.operation]
        if self.error:
            footer.append(f"Failed operation · {self.error}")
        footer.append(f"Logs · {self.run}")
        return heading, commits, rows, footer

    def render(self):
        heading, commits, rows, footer = self.frame()
        table = Table.grid(padding=(0, 1))
        for name, state, elapsed in rows:
            label = Text(state, style=COLORS[state])
            table.add_row(Text(name), self.spinner if state == RUNNING else label, elapsed)
        return Group(Text(heading, style="bold cyan"), Text(commits), table, *map(Text, footer))

    def summary(self):
        if self.console:
            self.console.print(self.render())
        else:
            heading, commits, rows, footer = self.frame()
            self.write(heading, commits, *(" · ".join(row) for row in rows), *footer)


def latest(run):
    last = 0
    view = Dashboard(run, clock=lambda: last)
    with (run / "events.jsonl").open() as journal:
        for line in journal:
            try:
                record = json.loads(line)
                stamp = datetime.fromisoformat(record["timestamp"]).timestamp()
            except (ValueError, KeyError, TypeError):
                continue
            if not last:
                view.start = stamp
            last = stamp
            view.accept(record, last, announce=False)
    if not view.result or view.operation != view.result:
        view.operation += " · no final result recorded"
    view.summary()
