import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from io import StringIO
from django.test import TestCase as DjangoTestCase

from menus.application.catalogue_import import CatalogueConflict, import_catalogue
from menus.domain.catalogue import CatalogueDish
from menus.infrastructure.csv_catalogue import InvalidCatalogue, read_catalogue
from menus.infrastructure.django_catalogue import DjangoCatalogueRepository
from menus.models import DishRecord


HEADERS = ["id", "name_ca", "primary_category", "secondary_categories", "meal_preference", "special_occasion", "recipe_status", "image_status"]
ROW = ["1", "Arròs, verd", "Cereals", "Verdures", "both", "false", "pending", "pending"]


class CSVTests(TestCase):
    def parse(self, rows, headers=HEADERS):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "catalogue.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as output:
                writer = csv.writer(output)
                writer.writerow(headers)
                writer.writerows(rows)
            return read_catalogue(path)

    def test_unicode_bom_crlf_quotes_and_false(self):
        dish = self.parse([ROW])[0]
        self.assertEqual(dish, CatalogueDish(1, "Arròs, verd", "Cereals", frozenset({"Verdures"}), "both", False))

    def test_reordered_headers_and_multiple_categories(self):
        headers = list(reversed(HEADERS))
        row = ["7", "Plat sintètic", "Cereals", "Verdures, Ous", "both", "false", "pending", "ignored"]
        dish = self.parse([list(reversed(row))], headers)[0]
        self.assertEqual(dish.secondary_categories, frozenset({"Verdures", "Ous"}))

    def test_invalid_data_is_rejected(self):
        cases = [
            ([ROW, ROW], HEADERS),
            ([ROW[:-1]], HEADERS),
            ([ROW + ["extra"]], HEADERS),
            ([ROW], HEADERS[:-1] + ["id"]),
            ([["0", *ROW[1:]]], HEADERS),
            ([[*ROW[:4], "breakfast", *ROW[5:]]], HEADERS),
            ([[*ROW[:5], "False", *ROW[6:]]], HEADERS),
            ([[ROW[0], "", *ROW[2:]]], HEADERS),
            ([["9223372036854775807", *ROW[1:]]], HEADERS),
            ([[ROW[0], "x" * 201, *ROW[2:]]], HEADERS),
            ([[*ROW[:2], "Desconeguda", *ROW[3:]]], HEADERS),
            ([[*ROW[:3], "Verdures, Verdures", *ROW[4:]]], HEADERS),
            ([[*ROW[:3], "Cereals", *ROW[4:]]], HEADERS),
        ]
        for rows, headers in cases:
            with self.subTest(rows=rows, headers=headers), self.assertRaises(InvalidCatalogue):
                self.parse(rows, headers)


class ImportTests(DjangoTestCase):
    def setUp(self):
        self.repository = DjangoCatalogueRepository()
        self.first = CatalogueDish(1, "Plat", "Cereals", frozenset({"Verdures"}), "lunch", False)
        self.second = CatalogueDish(2, "Altre", "Ous", frozenset(), "dinner", True)
        self.unrelated = CatalogueDish(99, "Familiar", "Peix", frozenset(), "both", False)

    def test_empty_repeat_partial_and_unrelated(self):
        self.repository.add(self.unrelated)
        self.assertEqual(import_catalogue([self.first], self.repository), 1)
        self.assertEqual(import_catalogue([self.first, self.second], self.repository), 1)
        self.assertEqual(import_catalogue([self.first, self.second], self.repository), 0)
        self.assertEqual(self.repository.get(1), self.first)
        self.assertEqual(self.repository.get(99), self.unrelated)
        self.assertEqual(DishRecord.objects.count(), 3)

    def test_conflict_preserves_existing_and_does_not_insert(self):
        self.repository.add(self.first)
        edited = CatalogueDish(1, "Editat", "Cereals", frozenset(), "lunch", False)
        with self.assertRaises(CatalogueConflict):
            import_catalogue([self.second, edited], self.repository)
        self.assertIsNone(self.repository.get(2))
        self.assertEqual(self.repository.get(1), self.first)

    def test_write_failure_rolls_back_prior_dish_and_categories(self):
        self.repository.add(self.unrelated)
        original = self.repository.add

        def fail_on_second(dish):
            if dish.id == 2:
                raise IntegrityError("simulated failure")
            original(dish)

        with mock.patch.object(self.repository, "add", side_effect=fail_on_second), self.assertRaises(IntegrityError):
            import_catalogue([self.first, self.second], self.repository)
        self.assertIsNone(self.repository.get(1))
        self.assertEqual(self.repository.get(99), self.unrelated)


class CommandTests(DjangoTestCase):
    def test_command_import_repeat_and_conflict(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "catalogue.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as output:
                writer = csv.writer(output)
                writer.writerow(HEADERS)
                writer.writerow(ROW)
            output = StringIO()
            call_command("import_catalogue", path, stdout=output)
            call_command("import_catalogue", path, stdout=output)
            self.assertIn("1 plats nous", output.getvalue())
            self.assertIn("0 plats nous", output.getvalue())
            DishRecord.objects.filter(pk=1).update(name="Editat")
            with self.assertRaises(CommandError):
                call_command("import_catalogue", path, stdout=StringIO())
            self.assertEqual(DishRecord.objects.get(pk=1).name, "Editat")


class SourceFidelityTests(DjangoTestCase):
    def test_local_private_source_when_provided(self):
        import os
        source = os.environ.get("MENU_CATALOGUE_CSV")
        if not source:
            self.skipTest("Set MENU_CATALOGUE_CSV to verify the private source")
        dishes = read_catalogue(Path(source))
        self.assertEqual(len(dishes), 57)
        self.assertTrue({dish.id for dish in dishes} == set(range(1, 58)), "Unexpected source identities")
        self.assertTrue({dish.id for dish in dishes if dish.special_occasion} == {25, 31, 43, 52, 55}, "Unexpected source flags")
        self.assertEqual(import_catalogue(dishes, DjangoCatalogueRepository()), 57)
        with Path(source).open(encoding="utf-8-sig", newline="") as input_file:
            for row in csv.DictReader(input_file):
                record = DishRecord.objects.get(pk=int(row["id"]))
                self.assertTrue(record.name == row["name_ca"], "Source name mismatch")
                self.assertTrue(record.primary_category.name_ca == row["primary_category"], "Source primary category mismatch")
                self.assertTrue(set(record.secondary_categories.values_list("category__name_ca", flat=True)) ==
                                {name.strip() for name in row["secondary_categories"].split(",") if name.strip()}, "Source secondary categories mismatch")
                self.assertTrue(record.meal_preference == row["meal_preference"], "Source preference mismatch")
                self.assertTrue(record.special_occasion == (row["special_occasion"] == "true"), "Source occasion mismatch")
