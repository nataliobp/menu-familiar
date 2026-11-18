from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import DatabaseError, close_old_connections, connection
from django.test import TransactionTestCase

from menus.application.template import TemplateConflict, set_template_category
from menus.infrastructure.django_template import DjangoTemplateRepository
from menus.models import CategoryRecord, TemplateSlotRecord, WeeklyTemplateRecord
from menus.domain.categories import CATEGORIES


def ensure_seed():
    for key, name in CATEGORIES:
        CategoryRecord.objects.get_or_create(key=key, defaults={"name_ca": name})
    template, _ = WeeklyTemplateRecord.objects.get_or_create(pk=1, defaults={"version": 1})
    for day in range(7):
        for meal in ("lunch", "dinner"):
            TemplateSlotRecord.objects.get_or_create(template=template, day_index=day, meal=meal)


class TemplateConcurrencyTests(TransactionTestCase):
    def setUp(self):
        ensure_seed()

    def test_same_version_writes_do_not_overwrite_each_other(self):
        if "mode=memory" in str(connection.settings_dict["NAME"]):
            self.skipTest("Requires an explicit disposable file-backed test database")
        barrier = Barrier(2, timeout=10)

        class SynchronizedRepository(DjangoTemplateRepository):
            def get(self):
                value = super().get()
                barrier.wait()
                return value

        def write(category):
            close_old_connections()
            try:
                set_template_category(SynchronizedRepository(), (0, "lunch"), category, 1)
                return "saved"
            except (TemplateConflict, DatabaseError):
                return "rejected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, ("cereals", "eggs")))
        self.assertCountEqual(results, ["saved", "rejected"])
        self.assertEqual(WeeklyTemplateRecord.objects.get().version, 2)
        self.assertIn(TemplateSlotRecord.objects.get(day_index=0, meal="lunch").suggested_category_id, {"cereals", "eggs"})


class PlanningConcurrencyTests(TransactionTestCase):
    def setUp(self):
        ensure_seed()
        from datetime import date
        from menus.models import DishRecord
        from menus.infrastructure.django_planning import DjangoPlanningRepository
        from menus.application.planning import create_menu
        self.week = date(2026, 11, 16)
        self.clock = type("Clock", (), {"today": lambda _: self.week})()
        self.repo = DjangoPlanningRepository()
        self.dish = DishRecord.objects.create(name="Plat sintètic", primary_category_id="cereals", meal_preference="both", special_occasion=False)
        create_menu(self.repo, self.clock, self.week)

    def require_file(self):
        if "mode=memory" in str(connection.settings_dict["NAME"]):
            self.skipTest("Requires an explicit disposable file-backed test database")

    def test_concurrent_assignments_with_one_version(self):
        from menus.application.planning import PlanningConflict, change_menu
        from menus.infrastructure.django_planning import DjangoPlanningRepository
        self.require_file()
        barrier = Barrier(2, timeout=10)
        class SynchronizedRepository(DjangoPlanningRepository):
            def get(self, week):
                value = super().get(week)
                barrier.wait()
                return value
        def write(position):
            close_old_connections()
            try:
                change_menu(SynchronizedRepository(), self.clock, self.week, position, 1, "assign", self.dish.pk)
                return "saved"
            except (PlanningConflict, DatabaseError):
                return "rejected"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, [(0, "lunch"), (1, "lunch")]))
        self.assertCountEqual(results, ["saved", "rejected"])
        menu = self.repo.get(self.week)
        self.assertEqual(menu.version, 2)
        self.assertEqual(sum(slot.state == "selected" for slot in menu.slots.values()), 1)

    def test_competing_first_overlay_creation(self):
        from menus.application.planning import change_menu
        from menus.application.recipes import save_recipe
        from menus.application.shopping import mutate_shopping
        from menus.domain.recipe import recipe_content
        from menus.infrastructure.django_dishes import DjangoDishRepository
        from menus.infrastructure.django_shopping import DjangoShoppingRepository, ShoppingConflict
        self.require_file()
        content = recipe_content("Cou", [{"name": "Arròs", "quantity": "100", "unit": "g"}], True)
        save_recipe(DjangoDishRepository(), self.clock, self.dish.pk, 1, content, True)
        change_menu(self.repo, self.clock, self.week, (0, "lunch"), 1, "assign", self.dish.pk)
        barrier = Barrier(2, timeout=10)
        class SynchronizedShopping(DjangoShoppingRepository):
            def read(self, week):
                value = super().read(week)
                barrier.wait()
                return value
        def write(quantity):
            close_old_connections()
            try:
                mutate_shopping(SynchronizedShopping(), self.clock, self.week, 2, 0, "adjust", {"key": "arròs", "family": "g", "quantity": quantity})
                return "saved"
            except (ShoppingConflict, DatabaseError):
                return "rejected"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, ["200", "300"]))
        self.assertCountEqual(results, ["saved", "rejected"])
        view = DjangoShoppingRepository().read(self.week)
        self.assertEqual(view[1].version, 1)
        self.assertIn(view[2][0]["overlay"].adjusted_quantity, {"200.000", "300.000"})

    def test_recipe_publication_racing_shopping_adjustment(self):
        from menus.application.dishes import DishConflict
        from menus.application.planning import PlanningConflict, change_menu
        from menus.application.recipes import save_recipe
        from menus.application.shopping import mutate_shopping
        from menus.domain.recipe import recipe_content
        from menus.infrastructure.django_dishes import DjangoDishRepository
        from menus.infrastructure.django_shopping import DjangoShoppingRepository, ShoppingConflict
        self.require_file()
        first = recipe_content("Cou", [{"name": "Arròs", "quantity": "100", "unit": "g"}], True)
        second = recipe_content("Cou", [{"name": "Arròs", "quantity": "200", "unit": "g"}], True)
        save_recipe(DjangoDishRepository(), self.clock, self.dish.pk, 1, first, True)
        change_menu(self.repo, self.clock, self.week, (0, "lunch"), 1, "assign", self.dish.pk)
        barrier = Barrier(2, timeout=10)
        class SynchronizedDish(DjangoDishRepository):
            def save_recipe(self, *args):
                result = super().save_recipe(*args)
                barrier.wait()
                return result
        class SynchronizedShopping(DjangoShoppingRepository):
            def read(self, week):
                result = super().read(week)
                barrier.wait()
                return result
        def recipe_write():
            close_old_connections()
            try:
                save_recipe(SynchronizedDish(), self.clock, self.dish.pk, 2, second, True)
                return "saved"
            except (DishConflict, PlanningConflict, DatabaseError):
                return "rejected"
            finally:
                close_old_connections()
        def shopping_write():
            close_old_connections()
            try:
                mutate_shopping(SynchronizedShopping(), self.clock, self.week, 2, 0, "adjust", {"key": "arròs", "family": "g", "quantity": "150"})
                return "saved"
            except (ShoppingConflict, DatabaseError):
                return "rejected"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(recipe_write), pool.submit(shopping_write)]
            outcomes = [future.result(timeout=15) for future in futures]
        self.assertCountEqual(outcomes, ["saved", "rejected"])
        menu, state, rows, *_ = DjangoShoppingRepository().read(self.week)
        if outcomes[0] == "saved":
            self.assertEqual(str(rows[0]["quantity"]), "200.000")
            self.assertIsNone(state)
        else:
            self.assertEqual(str(rows[0]["quantity"]), "100.000")
            self.assertEqual(rows[0]["overlay"].adjusted_quantity, "150.000")

    def test_duplicate_dish_creation_retries_same_receipt(self):
        from uuid import uuid4
        from menus.application.dishes import DishConflict, create_dish
        from menus.domain.dish_edit import DishInput
        from menus.infrastructure.django_dishes import DjangoDishRepository
        from menus.models import DishRecord
        self.require_file()
        barrier = Barrier(2, timeout=10)
        token = uuid4()
        data = DishInput("Plat de prova", "cereals", frozenset(), "both", False)
        class SynchronizedDish(DjangoDishRepository):
            def receipt(self, key):
                result = super().receipt(key)
                barrier.wait()
                return result
        def write(_):
            close_old_connections()
            try:
                return create_dish(SynchronizedDish(), data, token)
            except (DishConflict, DatabaseError):
                return None
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, range(2)))
        self.assertEqual(len([value for value in results if value is not None]), 1)
        recovered = create_dish(DjangoDishRepository(), data, token)
        self.assertIn(recovered, results)
        self.assertEqual(DishRecord.objects.filter(name="Plat de prova").count(), 1)
