from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from menus.application.catalogue_import import CatalogueConflict, import_catalogue
from menus.infrastructure.csv_catalogue import InvalidCatalogue, read_catalogue
from menus.infrastructure.django_catalogue import DjangoCatalogueRepository


class Command(BaseCommand):
    help = "Import the initial dish catalogue from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=Path)

    def handle(self, *args, **options):
        try:
            dishes = read_catalogue(options["csv_path"])
            count = import_catalogue(dishes, DjangoCatalogueRepository())
        except InvalidCatalogue as exc:
            raise CommandError(f"Catàleg invàlid ({exc}); no s’ha modificat cap plat.") from exc
        except (OSError, CatalogueConflict, DatabaseError) as exc:
            raise CommandError("No s'ha pogut importar el catàleg; no s'ha modificat cap plat.") from exc
        self.stdout.write(f"Importació completada: {count} plats nous.")
