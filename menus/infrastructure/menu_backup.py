"""Create a consistent SQLite backup and copy the photos it references."""

from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from menus.infrastructure.recipe_photos import MAX_PHOTO_BYTES, Photo, PhotoStore


def backup_menu_data(database, photo_root, destination):
    database, destination = Path(database), Path(destination)
    if not database.is_absolute() or not destination.is_absolute() or destination.exists() or destination.is_symlink():
        raise ValueError("Use an absolute database path and a new absolute backup directory")
    source = PhotoStore(photo_root)
    with TemporaryDirectory(prefix=".menu-backup-", dir=destination.parent) as staged:
        staged = Path(staged)
        snapshot = staged / "menu.sqlite3"
        with (closing(sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)) as live,
              closing(sqlite3.connect(snapshot)) as backup):
            live.backup(backup)
            if backup.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("Backup integrity check failed")
            references = backup.execute("SELECT source_id, photo_digest FROM menus_cataloguesourcerecord WHERE photo_digest != ''").fetchall()
        snapshot.chmod(0o600)
        target = PhotoStore(staged / "recipe-photos")
        for source_id, digest in references:
            with source.open(source_id, digest) as photo:
                data = photo.read(MAX_PHOTO_BYTES + 1)
            if len(data) > MAX_PHOTO_BYTES or hashlib.sha256(data).hexdigest() != digest:
                raise ValueError("Backup photo integrity check failed")
            target.store(source_id, Photo(digest, data))
        # Claim the final name exclusively so a concurrent backup cannot be replaced.
        destination.mkdir(mode=0o700)
        try:
            os.replace(staged, destination)
        except OSError:
            destination.rmdir()
            raise
    return len(references)
