import copy
from dataclasses import replace
from datetime import timedelta
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, SimpleTestCase, TestCase, override_settings

from menus.application.dishes import DishConflict, update_dish
from menus.application.planning import change_menu
from menus.application.private_recipes import Proposal, import_proposals
from menus.application.recipes import save_recipe
from menus.domain.catalogue import CatalogueDish
from menus.domain.planning import monday
from menus.domain.recipe import recipe_content
from menus.infrastructure.django_planning import DjangoPlanningRepository, MadridClock
from menus.infrastructure.django_private_recipes import DjangoPrivateRecipeRepository
from menus.infrastructure.menu_backup import backup_menu_data
from menus.infrastructure.private_recipe_bundle import InvalidBundle, SOURCE_IDS, read_proposals
from menus.infrastructure.recipe_photos import Photo, PhotoStore, read_photos
from menus.models import CatalogueSourceRecord, CategoryRecord, DishRecord, RecipeRecord


def record(source_id):
    return {
        "source_id": source_id, "expected_original_name_ca": f"Plat de prova {source_id}",
        "proposed_name_ca": f"Plat {'aprovat' if source_id in {7, 17} else 'de prova'} {source_id}",
        "primary_category": "Ensalades", "secondary_categories": [], "servings": 2,
        "review_status": "proposta_pendent_de_validacio", "provenance": "generated_draft",
        "prep_minutes": 5, "cook_minutes": 10, "preparation_steps_ca": ["Bull l’arròs.", "Serveix-lo."],
        "ingredients": [{"name_ca": "Arròs", "ingredient_key": "arros", "quantity": "1", "unit": "u"}],
        "image_filename": f"{source_id:02}.webp",
    }


def make_bundle(root):
    recipes = {"schema_version": "2.3-2.4-draft-1", "type": "private_household_recipe_proposals",
               "language": "ca-ES", "intended_servings": 2, "recipes": [record(n) for n in sorted(SOURCE_IDS)]}
    renames = {"schema_version": 1, "do_not_change_unapproved_names": True,
               "category_display_overrides": [{"source_category": "Ensalades", "display_ca": "Amanides"}],
               "approved_name_overrides": [{"source_id": n, "expected_name_ca": record(n)["expected_original_name_ca"],
                                            "new_name_ca": record(n)["proposed_name_ca"]} for n in (7, 17)]}
    manifest = {"schema_version": "1", "photos": [{"source_id": n, "status": "pending_generation", "file": None}
                                                   for n in sorted(SOURCE_IDS)]}
    for name, data in (("recipes-57", recipes), ("catalogue-renames", renames), ("photo-manifest", manifest)):
        (root / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
    return recipes, renames, manifest


def sample_webp():
    from PIL import Image

    encoded = BytesIO()
    Image.new("RGB", (8, 6), "#286044").save(encoded, format="WEBP")
    return encoded.getvalue()


class BundleTests(SimpleTestCase):
    def test_full_bundle_validates_and_normalizes_for_existing_shopping_projection(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            proposals = read_proposals(root, {})
            self.assertEqual(len(proposals), 57)
            self.assertEqual(read_photos(root), {})
            content = proposals[0].content
            self.assertEqual(content["preparation"].splitlines(), ["Bull l’arròs.", "Serveix-lo."])
            self.assertEqual(content["ingredients"][0], {
                "name": "Arròs", "key": "arròs", "quantity": "1.000", "unit": "unit", "taste": False, "note": "",
            })

    def test_invalid_recipes_and_ambiguous_source_ids_are_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            recipes, _, _ = make_bundle(root)
            path = root / "recipes-57.json"
            changes = [
                {"preparation_steps_ca": []}, {"servings": True}, {"primary_category": "other"},
                {"source_id": True}, {"source_id": 2}, {"source_id": 58}, {"proposed_name_ca": "No aprovat"},
                *({"ingredients": [{**record(1)["ingredients"][0], **change}]} for change in (
                    {"quantity": "0"}, {"quantity": "NaN"}, {"quantity": "2.1234"},
                    {"unit": "oz"}, {"ingredient_key": "other"},
                )),
                {"ingredients": record(1)["ingredients"] * 2},
            ]
            for change in changes:
                invalid = copy.deepcopy(recipes)
                invalid["recipes"][0].update(change)
                path.write_text(json.dumps(invalid), encoding="utf-8")
                with self.subTest(change=change), self.assertRaises(InvalidBundle):
                    read_proposals(root, {})
            path.write_text('{"schema_version":"1","schema_version":"2"}', encoding="utf-8")
            with self.assertRaises(InvalidBundle):
                read_proposals(root, {})

    def test_photo_requires_safe_path_real_webp_matching_digest_and_dimensions(self):
        try:
            valid = sample_webp()
        except ImportError:
            self.skipTest("Pillow is required for decoded WebP tests")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, manifest = make_bundle(root)
            (root / "photos").mkdir()
            photo = root / "photos" / "01.webp"
            entry = {"source_id": 1, "status": "generated", "file": "photos/01.webp", "width": 8, "height": 6}
            for data, metadata, accepted in (
                (valid, {}, True), (valid, {"file": "photos/../01.webp"}, False),
                (valid, {"file": "/01.webp"}, False), (valid, {"file": "photos/02.webp"}, False),
                (valid, {"width": 16, "height": 12}, False), (valid, {"height": 7}, False),
                (valid, {"sha256": "0" * 64}, False), (valid[:24], {}, False), (b"not an image", {}, False),
            ):
                with self.subTest(metadata=metadata, size=len(data)):
                    photo.write_bytes(data)
                    manifest["photos"][0] = {**entry, "sha256": hashlib.sha256(data).hexdigest(),
                                               "size_bytes": len(data), **metadata}
                    (root / "photo-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                    if accepted:
                        self.assertEqual(read_photos(root)[1].data, valid)
                    else:
                        with self.assertRaises(InvalidBundle):
                            read_photos(root)


class ImportTests(TestCase):
    def setUp(self):
        self.repo = DjangoPrivateRecipeRepository()
        self.planning = DjangoPlanningRepository()
        self.clock = MadridClock()
        self.week = monday(self.clock.today())
        self.content = recipe_content("Bull l’arròs.", [{"name": "Arròs", "quantity": "75", "unit": "g"}], True)
        self.content["proposal"] = {"servings": 2, "provenance": "generated_draft", "prep_minutes": 5,
                                    "cook_minutes": 10, "notes": ""}

    def dish(self, pk, name="Plat original", source_id=None):
        dish = DishRecord.objects.create(pk=pk, name=name, primary_category_id="salads", meal_preference="both", special_occasion=False)
        if source_id:
            CatalogueSourceRecord.objects.create(source_id=source_id, dish=dish)
        return dish

    def apply(self, proposals, legacy=None, dry_run=False, photos=None, store_photo=lambda _: None):
        return import_proposals(self.repo, self.clock, proposals, legacy or {}, photos or {}, dry_run, store_photo)

    def test_verified_identity_can_differ_from_pk_and_refreshes_only_editable_weeks(self):
        unrelated = self.dish(7, "Plat de propietari")
        target = self.dish(101, source_id=7)
        past = self.week - timedelta(days=7)
        future = self.week + timedelta(days=7)
        for week in (past, self.week, future):
            change_menu(self.planning, SimpleNamespace(today=lambda: week), week, (0, "lunch"), 0, "assign", target.pk)
        old = self.planning.get(past)
        proposal = Proposal(7, target.name, "Plat aprovat", self.content)
        preview = self.apply([proposal], dry_run=True)
        self.assertEqual(preview, self.apply([proposal]))
        self.assertEqual(preview[0].rename, "renamed")
        self.assertEqual(self.planning.get(past), old)
        for week in (self.week, future):
            slot = self.planning.get(week).slots[0, "lunch"]
            self.assertEqual(slot.dish["name"], "Plat aprovat")
            self.assertEqual(slot.dish["recipe_content"], self.content)
            shopping = self.client.get(f"/compra/{week}/")
            self.assertContains(shopping, "Arròs")
            self.assertContains(shopping, "75 g")
        target.refresh_from_db()
        unrelated.refresh_from_db()
        self.assertEqual(unrelated.name, "Plat de propietari")
        self.assertEqual(self.apply([proposal])[0].recipe, "unchanged")
        self.assertEqual(DishRecord.objects.get(pk=target.pk).version, target.version)
        # If the owner later restores the original name, the import cannot rename it again.
        target.name = proposal.original_name
        target.save(update_fields=["name"])
        self.assertEqual(self.apply([proposal])[0].recipe, "name_conflict")

    def test_legacy_ambiguity_and_owner_rename_are_reported_without_writes(self):
        expected = CatalogueDish(7, "Plat original", "Amanides", frozenset(), "both", False)
        proposal = Proposal(7, expected.name, "Plat aprovat", self.content)
        other = self.dish(7, "Nom del propietari")
        self.dish(80, expected.name)
        self.assertEqual(self.apply([proposal])[0].recipe, "unknown_source")
        self.assertEqual(self.apply([proposal], {7: expected})[0].recipe, "name_conflict")
        CatalogueSourceRecord.objects.create(source_id=17, dish=other)
        self.assertEqual(self.apply([proposal], {7: expected})[0].recipe, "identity_conflict")
        self.assertFalse(RecipeRecord.objects.exists())

    def test_catalogue_edit_blocks_unapplied_rename_even_if_name_matches(self):
        dish = self.dish(101, source_id=17)
        before = self.repo.resolve_source(17, None)
        update_dish(self.repo, self.clock, dish.pk, replace(before.dish, meal_preference="dinner"), before.version)
        outcome = self.apply([Proposal(17, dish.name, "Plat aprovat", self.content)])[0]
        self.assertEqual((outcome.recipe, outcome.rename), ("identity_conflict", "blocked"))
        dish.refresh_from_db()
        self.assertEqual((dish.name, dish.meal_preference), ("Plat original", "dinner"))
        self.assertFalse(RecipeRecord.objects.exists())

    def test_import_preserves_draft_and_published_recipes(self):
        published = self.dish(100, source_id=1)
        draft = self.dish(101, source_id=2)
        owner_content = recipe_content("Recepta de casa", [{"name": "Sal", "taste": True}], True)
        save_recipe(self.repo, self.clock, published.pk, 1, owner_content, True)
        draft_content = recipe_content("Encara hi falten les quantitats", [{"name": "Pebre"}])
        save_recipe(self.repo, self.clock, draft.pk, 1, draft_content)
        outcomes = self.apply([Proposal(key, "Plat original", "Plat original", self.content) for key in (1, 2)])
        self.assertEqual([outcome.recipe for outcome in outcomes], ["preserved_published", "preserved_draft"])
        self.assertEqual(RecipeRecord.objects.get(dish=published).published, owner_content)
        self.assertEqual(RecipeRecord.objects.get(dish=draft).draft, draft_content)

    def test_legacy_adoption_and_stale_version_guard(self):
        self.dish(7)
        expected = CatalogueDish(7, "Plat original", "Amanides", frozenset(), "both", False)
        proposal = Proposal(7, expected.name, "Plat aprovat", self.content)
        resolve = self.repo.resolve_source

        def stale(*args):
            target = resolve(*args)
            DishRecord.objects.filter(pk=7).update(version=2)
            return target

        with patch.object(self.repo, "resolve_source", side_effect=stale), self.assertRaises(DishConflict):
            self.apply([proposal], {7: expected})
        self.assertFalse(CatalogueSourceRecord.objects.exists())
        self.assertEqual(self.apply([proposal], {7: expected})[0].recipe, "imported")
        self.assertTrue(CatalogueSourceRecord.objects.get(pk=7).rename_applied)

    def test_release_mode_preserves_names_and_uses_verified_identity(self):
        linked = self.dish(101, "Nom de casa", source_id=7)
        legacy = self.dish(17, "Plat original")
        self.dish(2, "Plat amb identitat incerta")
        seed = {
            key: CatalogueDish(key, "Plat original", "Amanides", frozenset(), "both", False)
            for key in (2, 17)
        }
        proposals = [Proposal(key, "Plat original", "Nom aprovat", self.content) for key in (2, 7, 17)]
        options = dict(store_photo=lambda _: None, preserve_dish_names=True)
        preview = import_proposals(self.repo, self.clock, proposals, seed, {}, True, **options)
        self.assertFalse(RecipeRecord.objects.exists())
        self.assertEqual(preview, import_proposals(self.repo, self.clock, proposals, seed, {}, False, **options))
        self.assertEqual([(row.recipe, row.rename) for row in preview], [
            ("name_conflict", "blocked"), ("imported", "preserved_name"), ("imported", "preserved_name"),
        ])
        self.assertEqual(set(RecipeRecord.objects.values_list("dish_id", flat=True)), {linked.pk, legacy.pk})
        self.assertEqual(set(DishRecord.objects.values_list("name", flat=True)), {
            "Nom de casa", "Plat original", "Plat amb identitat incerta",
        })
        self.assertFalse(CatalogueSourceRecord.objects.get(pk=17).rename_applied)

    def test_command_is_read_only_by_default_and_rejects_invalid_input_before_change(self):
        self.dish(110, "Plat de prova 1", source_id=1)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            recipes, _, _ = make_bundle(root)
            photo_root = root / "store"
            output = StringIO()
            with override_settings(RECIPE_PHOTO_ROOT=photo_root):
                call_command("import_recipe_proposals", root, stdout=output)
                self.assertIn("01: recipe=imported", output.getvalue())
                self.assertIn("02: recipe=unknown_source", output.getvalue())
                self.assertFalse(RecipeRecord.objects.exists())
                self.assertFalse(photo_root.exists())
                recipes["recipes"][-1]["ingredients"] = []
                (root / "recipes-57.json").write_text(json.dumps(recipes), encoding="utf-8")
                with self.assertRaisesMessage(CommandError, "source ID 57"):
                    call_command("import_recipe_proposals", root, apply=True, stdout=output)
                self.assertFalse(RecipeRecord.objects.exists())

    def test_photo_detail_missing_file_and_locale(self):
        dish = self.dish(101, "Plat de prova", source_id=1)
        CategoryRecord.objects.filter(pk="salads").update(name_ca="Ensalades")
        data = b"synthetic bytes already validated at import boundary"
        digest = hashlib.sha256(data).hexdigest()
        url = f"/plats/{dish.pk}/recepta/foto/"
        with TemporaryDirectory() as directory, override_settings(RECIPE_PHOTO_ROOT=Path(directory)):
            store = PhotoStore(directory)
            proposal = Proposal(1, dish.name, dish.name, self.content)
            self.apply([proposal])
            self.assertNotContains(self.client.get(f"/plats/{dish.pk}/"), "Imatge generada")
            version = DishRecord.objects.get(pk=dish.pk).version
            outcome = self.apply([proposal], photos={1: digest},
                                 store_photo=lambda key: store.store(key, Photo(digest, data)))[0]
            self.assertEqual((outcome.recipe, outcome.photo), ("unchanged", "linked"))
            self.assertEqual(DishRecord.objects.get(pk=dish.pk).version, version)
            detail = self.client.get(f"/plats/{dish.pk}/")
            for copy_text in ("Amanides", "Recepta proposada, pendent de validar.", "2 adults", "Imatge generada", "Bull l’arròs."):
                self.assertContains(detail, copy_text)
            self.assertNotContains(detail, "Ensalades")
            catalogue = self.client.get("/plats/?category=salads")
            self.assertContains(catalogue, "Recepta proposada")
            self.assertNotContains(catalogue, url)
            media = self.client.get(url)
            self.assertEqual(media.status_code, 200)
            self.assertEqual(media["Content-Type"], "image/webp")
            self.assertEqual(b"".join(media.streaming_content), data)
            self.assertEqual(self.client.get(url + "%2e%2e/01.webp").status_code, 404)
            self.assertEqual(self.client.get("/recipe-photos/").status_code, 404)
            method_error = self.client.post(url)
            self.assertContains(method_error, "Aquesta acció no està disponible", status_code=405)
            self.assertEqual(method_error["Allow"], "GET, HEAD")
            path = store.root / store.filename(1, digest)
            path.unlink()
            path.symlink_to("/etc/hosts")
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertNotContains(self.client.get(f"/plats/{dish.pk}/"), "Imatge generada")
            self.assertContains(self.client.get(f"/plats/{dish.pk}/"), "Preparació")

    def test_private_file_failure_rolls_back_dishes(self):
        self.dish(101, source_id=7)
        proposal = Proposal(7, "Plat original", "Plat aprovat", self.content)
        with self.assertRaises(OSError):
            self.apply([proposal], photos={7: "a" * 64}, store_photo=Mock(side_effect=OSError()))
        self.assertEqual(DishRecord.objects.get(pk=101).name, "Plat original")
        self.assertFalse(RecipeRecord.objects.exists())
        self.assertFalse(CatalogueSourceRecord.objects.get(pk=7).rename_applied)

    def test_different_existing_photo_is_preserved_on_preview_and_apply(self):
        dish = self.dish(101, source_id=1)
        proposal = Proposal(1, dish.name, dish.name, self.content)
        original = b"original photo"
        digest = hashlib.sha256(original).hexdigest()
        with TemporaryDirectory() as directory:
            store = PhotoStore(directory)
            self.apply([proposal], photos={1: digest}, store_photo=lambda key: store.store(key, Photo(digest, original)))
            storage = Mock()
            for dry_run in (True, False):
                result = self.apply([proposal], photos={1: "b" * 64}, dry_run=dry_run, store_photo=storage)
                self.assertEqual(result[0].photo, "preserved_existing")
            storage.assert_not_called()
            with store.open(1, digest) as stored:
                self.assertEqual(stored.read(), original)
        self.assertEqual(CatalogueSourceRecord.objects.get(pk=1).photo_digest, digest)
        version = DishRecord.objects.get(pk=dish.pk).version
        with self.assertRaises(DishConflict):
            self.repo.link_photo(1, dish.pk, version, "b" * 64)
        self.assertEqual(CatalogueSourceRecord.objects.get(pk=1).photo_digest, digest)


class ErrorLocaleTests(SimpleTestCase):
    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_framework_errors_render_in_catalan(self):
        self.assertContains(self.client.get("/absent/"), "No s’ha trobat la pàgina", status_code=404)
        self.assertContains(self.client.get("/menu/", HTTP_HOST="invalid.example"),
                            "La sol·licitud no és vàlida", status_code=400)
        response = Client(enforce_csrf_checks=True).post("/plantilla/0/lunch/")
        self.assertContains(response, "No s’ha pogut confirmar la sol·licitud", status_code=403)


class BackupTests(SimpleTestCase):
    def test_backup_accepts_v1_without_photo_table_and_restores_wal_commit(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "original.sqlite3"
            with sqlite3.connect(database) as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("CREATE TABLE django_migrations (id, app, name)")
                connection.execute("INSERT INTO django_migrations VALUES (?, ?, ?)", (
                    1, "menus", "0010_alter_generatedoverlayrecord_ingredient_key_and_more",
                ))
                connection.commit()
                backup = root / "backup"
                self.assertEqual(backup_menu_data(database, root / "recipe-photos", backup), 0)
                with sqlite3.connect(backup / "menu.sqlite3") as restored:
                    self.assertEqual(restored.execute("SELECT * FROM django_migrations").fetchall(),
                                     connection.execute("SELECT * FROM django_migrations").fetchall())
                restored.close()
                connection.execute("INSERT INTO django_migrations VALUES (2, 'menus', '0011_catalogue_source')")
                connection.commit()
                with self.assertRaises(ValueError):
                    backup_menu_data(database, root / "recipe-photos", root / "bad")
            connection.close()

    def test_backup_and_restore_keep_only_verified_referenced_photos(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = PhotoStore(root / "recipe-photos")
            data = b"synthetic photo contents"
            digest = hashlib.sha256(data).hexdigest()
            source.store(1, Photo(digest, data))
            source.store(2, Photo(digest, data))
            database = root / "original.sqlite3"
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE menus_cataloguesourcerecord (source_id, photo_digest)")
                connection.execute("INSERT INTO menus_cataloguesourcerecord VALUES (?, ?)", (1, digest))
            connection.close()
            backup = root / "backup"
            self.assertEqual(backup_menu_data(database, source.root, backup), 1)
            restored = root / "restored"
            backup.rename(restored)
            with sqlite3.connect(restored / "menu.sqlite3") as connection:
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone(), ("ok",))
                self.assertEqual(connection.execute("SELECT * FROM menus_cataloguesourcerecord").fetchall(), [(1, digest)])
            connection.close()
            photos = PhotoStore(restored / "recipe-photos")
            with photos.open(1, digest) as photo:
                self.assertEqual(photo.read(), data)
            self.assertFalse(photos.exists(2, digest))
            (source.root / source.filename(1, digest)).write_bytes(b"damaged photo")
            with self.assertRaises(ValueError):
                backup_menu_data(database, source.root, backup)
            self.assertFalse(backup.exists())
