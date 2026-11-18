from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class CatalogueUpgradeTests(TransactionTestCase):
    migrate_from = [("menus", "0001_initial")]
    migrate_to = [("menus", "0002_catalogue_upgrade")]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        self.old_apps = executor.loader.project_state(self.migrate_from).apps

    def tearDown(self):
        # Ensure the test database is left at the latest schema even after a failed upgrade.
        executor = MigrationExecutor(connection)
        if ("menus", "0002_catalogue_upgrade") not in executor.loader.applied_migrations:
            old_dish = self.old_apps.get_model("menus", "DishRecord")
            old_dish.objects.filter(primary_category="Unknown").delete()
            executor.migrate(self.migrate_to)
        super().tearDown()

    def test_populated_upgrade_preserves_fields_and_allocates_id(self):
        Dish = self.old_apps.get_model("menus", "DishRecord")
        Secondary = self.old_apps.get_model("menus", "SecondaryCategoryRecord")
        dish = Dish.objects.create(id=42, name="Plat", primary_category="Cereals", meal_preference="both", special_occasion=True)
        Secondary.objects.create(dish=dish, name="Verdures")
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to).apps
        upgraded = apps.get_model("menus", "DishRecord")
        row = upgraded.objects.get(pk=42)
        self.assertEqual((row.name, row.primary_category_id, row.meal_preference, row.special_occasion, row.version, row.archived),
                         ("Plat", "cereals", "both", True, 1, False))
        self.assertEqual(row.secondary_categories.get().category_id, "vegetables")
        self.assertGreater(upgraded.objects.create(name="Nou", primary_category_id="eggs", meal_preference="lunch", special_occasion=False).pk, 42)

    def test_invalid_category_rolls_back(self):
        Dish = self.old_apps.get_model("menus", "DishRecord")
        Dish.objects.create(id=1, name="Plat", primary_category="Unknown", meal_preference="both", special_occasion=False)
        with self.assertRaises(ValueError):
            MigrationExecutor(connection).migrate(self.migrate_to)
        self.assertEqual(Dish.objects.get(pk=1).primary_category, "Unknown")
