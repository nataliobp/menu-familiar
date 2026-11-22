from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from menus.application.dishes import DishConflict
from menus.application.errors import DataIntegrityError
from menus.application.planning import PlanningConflict, Rollover
from menus.application.private_recipes import import_proposals
from menus.infrastructure.csv_catalogue import InvalidCatalogue, read_catalogue
from menus.infrastructure.django_planning import MadridClock
from menus.infrastructure.django_private_recipes import DjangoPrivateRecipeRepository
from menus.infrastructure.private_recipe_bundle import InvalidBundle, read_proposals
from menus.infrastructure.recipe_photos import PhotoStore, read_photos


class Command(BaseCommand):
    help = "Validate and preview the private recipe bundle. Supply --apply to make changes."

    def add_arguments(self, parser):
        parser.add_argument("bundle", type=Path)
        parser.add_argument("--legacy-catalogue", type=Path)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        root = options["bundle"]
        legacy_path = options["legacy_catalogue"]
        apply = options["apply"]
        if apply and options["dry_run"]:
            raise CommandError("Choose either --apply or --dry-run.")
        store = PhotoStore(settings.RECIPE_PHOTO_ROOT)
        if apply and store.root.resolve().is_relative_to(settings.BASE_DIR):
            raise CommandError("The private photo directory must be outside the source tree.")
        try:
            legacy = {dish.id: dish for dish in read_catalogue(legacy_path)} if legacy_path else {}
            proposals = read_proposals(root, legacy)
            photos = read_photos(root)
            repo = DjangoPrivateRecipeRepository()
            results = import_proposals(repo, MadridClock(), proposals, legacy,
                                       {key: photo.digest for key, photo in photos.items()}, not apply,
                                       store_photo=lambda key: store.store(key, photos[key]))
        except (InvalidBundle, InvalidCatalogue) as exc:
            raise CommandError(str(exc)) from None
        except (OSError, DatabaseError, DataIntegrityError, DishConflict, PlanningConflict, Rollover, ValueError):
            raise CommandError("Import aborted. Database changes rolled back. Check the target and retry with a dry run.") from None
        self.stdout.write("Applied" if apply else "Dry run")
        for result in results:
            self.stdout.write(f"{result.source_id:02}: recipe={result.recipe} rename={result.rename} photo={result.photo}")
        self.stdout.write(f"Bundle photos: {len(photos)}/{len(proposals)} available, {len(proposals) - len(photos)} pending")
