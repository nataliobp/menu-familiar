from datetime import date
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from menus.domain.shopping import aggregate
from menus.infrastructure.django_planning import DjangoPlanningRepository


class HistoryUpgradeTests(TransactionTestCase):
    before = [("menus", "0007_reciperecord")]
    after = [("menus", "0010_alter_generatedoverlayrecord_ingredient_key_and_more")]

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        apps = executor.loader.project_state(self.before).apps
        Category = apps.get_model("menus", "CategoryRecord")
        Dish = apps.get_model("menus", "DishRecord")
        Menu = apps.get_model("menus", "WeeklyMenuRecord")
        Slot = apps.get_model("menus", "MenuSlotRecord")
        Category.objects.get_or_create(key="cereals", defaults={"name_ca": "Cereals"})
        dish = Dish.objects.create(name="Plat sintètic", primary_category_id="cereals", meal_preference="both", special_occasion=False)
        self.week = date(2020, 1, 6)
        menu = Menu.objects.create(week_start=self.week, version=1, shopping_projection_version=1)
        snapshot = {"schema_version": 1, "dish_id": dish.pk, "name": dish.name,
                    "primary_category": {"key": "cereals", "name": "Cereals"}, "secondary_categories": [],
                    "meal_preference": "both", "special_occasion": False, "recipe_status": "published",
                    "recipe_content": {"schema_version": 1, "preparation": "Cou", "ingredients": [
                        {"name": "Arròs", "key": "arròs", "quantity": "160.000", "unit": "g", "taste": False, "note": ""}]}}
        Slot.objects.bulk_create([Slot(weekly_menu=menu, day_index=day, meal=meal,
                    state="selected" if (day, meal) == (0, "lunch") else "pending",
                    dish_id=dish.pk if (day, meal) == (0, "lunch") else None,
                    dish_snapshot=snapshot if (day, meal) == (0, "lunch") else None)
                    for day in range(7) for meal in ("lunch", "dinner")])

    def tearDown(self):
        MigrationExecutor(connection).migrate(self.after)
        super().tearDown()

    def test_pre_shopping_week_has_identical_projection_after_upgrade(self):
        before = aggregate(DjangoPlanningRepository().get(self.week).slots)
        MigrationExecutor(connection).migrate(self.after)
        after = aggregate(DjangoPlanningRepository().get(self.week).slots)
        self.assertEqual(before, after)
        self.assertEqual(str(after[0][0]["quantity"]), "160.000")


class OverlayUpgradeTests(TransactionTestCase):
    before = [("menus", "0009_generatedoverlayrecord_overlay_family_valid_and_more")]
    after = [("menus", "0010_alter_generatedoverlayrecord_ingredient_key_and_more")]

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        apps = executor.loader.project_state(self.before).apps
        Menu = apps.get_model("menus", "WeeklyMenuRecord")
        Slot = apps.get_model("menus", "MenuSlotRecord")
        State = apps.get_model("menus", "ShoppingStateRecord")
        Overlay = apps.get_model("menus", "GeneratedOverlayRecord")
        Manual = apps.get_model("menus", "ManualShoppingItemRecord")
        self.week = date(2020, 1, 6)
        menu = Menu.objects.create(week_start=self.week, version=2, shopping_projection_version=1)
        Slot.objects.bulk_create([Slot(weekly_menu=menu, day_index=day, meal=meal, state="pending")
                                  for day in range(7) for meal in ("lunch", "dinner")])
        state = State.objects.create(week=menu, version=3)
        Overlay.objects.create(shopping=state, ingredient_key="arròs", family="g", last_name="Arròs",
                               last_base_quantity="100.000", adjusted_quantity="150.000", checked=False)
        Manual.objects.create(shopping=state, name="Pa", quantity="2.000", unit="unit", checked=True)

    def tearDown(self):
        MigrationExecutor(connection).migrate(self.after)
        super().tearDown()

    def test_frozen_shopping_state_survives_overlay_schema_upgrade(self):
        from menus.infrastructure.django_shopping import DjangoShoppingRepository
        before = DjangoShoppingRepository().read(self.week)
        MigrationExecutor(connection).migrate(self.after)
        after = DjangoShoppingRepository().read(self.week)
        self.assertEqual(before, after)
        self.assertEqual(after[1].manual_items[0].quantity, "2.000")
        self.assertTrue(after[1].manual_items[0].checked)
        self.assertEqual(after[-1][0].adjusted_quantity, "150.000")
