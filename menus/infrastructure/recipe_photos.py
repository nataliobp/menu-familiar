"""Validate private WebP inputs and store immutable, content-addressed files."""

from dataclasses import dataclass
import hashlib
from io import BytesIO
import os
from pathlib import Path
import re
import stat
from tempfile import NamedTemporaryFile

from menus.infrastructure.private_recipe_bundle import InvalidBundle, SOURCE_IDS, indexed, read_json


DIGEST = re.compile(r"[a-f0-9]{64}")
MAX_PHOTO_BYTES = 4 * 1024 * 1024


def open_regular(root, name):
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        file = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    finally:
        os.close(directory)
    if not stat.S_ISREG(os.fstat(file).st_mode):
        os.close(file)
        raise OSError("Expected a regular photo file")
    return os.fdopen(file, "rb")


@dataclass(frozen=True)
class Photo:
    digest: str
    data: bytes


def read_photos(root):
    manifest = read_json(root / "photo-manifest.json")
    if manifest.get("schema_version") != "1":
        raise InvalidBundle("unsupported photo schema")
    photos = {}
    for source_id, row in sorted(indexed(manifest.get("photos"), SOURCE_IDS).items()):
        if row.get("status") == "pending_generation" and "file" in row and row["file"] is None:
            if set(row) != {"source_id", "status", "file"}:
                raise InvalidBundle(f"invalid pending photo for source ID {source_id}")
            continue
        photos[source_id] = read_photo(root / "photos", source_id, row)
    return photos


def read_photo(root, source_id, row):
    name = f"{source_id:02}.webp"
    try:
        if (row["status"] not in ("generated_from_contact_sheet", "generated")
                or row["file"] != f"photos/{name}" or not DIGEST.fullmatch(row["sha256"])
                or any(type(row[key]) is not int for key in ("width", "height", "size_bytes"))
                or not 0 < row["size_bytes"] <= MAX_PHOTO_BYTES):
            raise ValueError()
        with open_regular(root, name) as handle:
            data = handle.read(MAX_PHOTO_BYTES + 1)
        if len(data) != row["size_bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError()
        validate_webp(data, row["width"], row["height"])
        return Photo(row["sha256"], data)
    except InvalidBundle:
        raise
    except (KeyError, OSError, TypeError, ValueError) as exc:
        raise InvalidBundle(f"invalid photo for source ID {source_id}") from exc


def validate_webp(data, width, height):
    try:
        from PIL import Image
    except ImportError as exc:
        raise InvalidBundle("install Pillow in the private import environment to decode WebP") from exc
    if not (0 < width <= 2400 and 0 < height <= 1800 and width * 3 == height * 4):
        raise ValueError("Invalid photo dimensions")
    if (len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP"
            or int.from_bytes(data[4:8], "little") != len(data) - 8):
        raise ValueError("Invalid WebP container")
    try:
        with Image.open(BytesIO(data), formats=("WEBP",)) as image:
            if image.size != (width, height) or image.n_frames != 1:
                raise ValueError("Invalid WebP dimensions or frame count")
            image.load()
    except (Image.DecompressionBombError, RuntimeError) as exc:
        raise ValueError("Cannot decode WebP") from exc


class PhotoStore:
    def __init__(self, root):
        self.root = Path(root)

    def filename(self, source_id, digest):
        if type(source_id) is not int or source_id not in SOURCE_IDS or not DIGEST.fullmatch(digest):
            raise ValueError("Invalid photo identity")
        return f"{source_id:02}-{digest}.webp"

    def open(self, source_id, digest):
        return open_regular(self.root, self.filename(source_id, digest))

    def exists(self, source_id, digest):
        try:
            with self.open(source_id, digest):
                return True
        except (OSError, ValueError):
            return False

    def store(self, source_id, photo):
        name = self.filename(source_id, photo.digest)
        self.root.mkdir(mode=0o700, exist_ok=True)
        if self.root.is_symlink():
            raise OSError("Expected a real photo directory")
        with NamedTemporaryFile(dir=self.root) as staged:
            staged.write(photo.data)
            staged.flush()
            os.fsync(staged.fileno())
            try:
                os.link(staged.name, self.root / name, follow_symlinks=False)
            except FileExistsError:
                with self.open(source_id, photo.digest) as existing:
                    if existing.read(MAX_PHOTO_BYTES + 1) != photo.data:
                        raise OSError("Stored photo content does not match its digest")
            directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
