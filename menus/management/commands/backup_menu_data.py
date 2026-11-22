from pathlib import Path
import sqlite3

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from menus.infrastructure.menu_backup import backup_menu_data


class Command(BaseCommand):
    help = "Back up the configured SQLite database and its referenced recipe photos to a new directory."

    def add_arguments(self, parser):
        parser.add_argument("destination", type=Path)

    def handle(self, *args, **options):
        destination = options["destination"]
        if destination.resolve().is_relative_to(settings.BASE_DIR):
            raise CommandError("The private backup directory must be outside the source tree.")
        try:
            count = backup_menu_data(settings.DATABASES["default"]["NAME"], settings.RECIPE_PHOTO_ROOT, destination)
        except (OSError, sqlite3.Error, ValueError):
            raise CommandError("Backup failed. Check the source database, its photo files and the new destination.") from None
        self.stdout.write(f"Backup complete. Referenced photos: {count}.")
