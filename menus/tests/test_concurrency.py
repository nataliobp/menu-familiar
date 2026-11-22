from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

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
        from menus.tests.planning_fixtures import create_legacy_menu
        self.week = date(2026, 11, 16)
        self.clock = type("Clock", (), {"today": lambda _: self.week})()
        self.repo = DjangoPlanningRepository()
        self.dish = DishRecord.objects.create(name="Plat sintètic", primary_category_id="cereals", meal_preference="both", special_occasion=False)
        create_legacy_menu(self.repo, self.week)

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

    def test_concurrent_first_writes_commit_only_one_atomic_edit(self):
        from datetime import timedelta
        from menus.application.planning import PlanningConflict, change_menu
        from menus.infrastructure.django_planning import DjangoPlanningRepository
        from menus.models import MenuSlotRecord, WeeklyMenuRecord

        self.require_file()
        future = self.week + timedelta(days=7)
        barrier = Barrier(2, timeout=10)

        class SynchronizedRepository(DjangoPlanningRepository):
            def create(self, menu):
                barrier.wait()
                super().create(menu)

        def write(position):
            close_old_connections()
            try:
                change_menu(SynchronizedRepository(), self.clock, future, position, 0, "assign", self.dish.pk)
                return "saved"
            except PlanningConflict:
                return "conflict"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, [(0, "lunch"), (1, "lunch")]))
        self.assertCountEqual(results, ["saved", "conflict"])
        self.assertEqual(WeeklyMenuRecord.objects.get(week_start=future).version, 2)
        self.assertEqual(MenuSlotRecord.objects.filter(weekly_menu_id=future).count(), 14)
        self.assertEqual(MenuSlotRecord.objects.filter(weekly_menu_id=future, state="selected").count(), 1)

    def test_reminder_reads_a_coherent_snapshot_during_recipe_publication(self):
        from decimal import Decimal
        from menus.application.planning import change_menu
        from menus.application.recipes import save_recipe
        from menus.application.shopping import get_ingredient_reminder
        from menus.domain.recipe import recipe_content
        from menus.infrastructure.django_dishes import DjangoDishRepository

        self.require_file()
        before = recipe_content("Cou", [{"name": "Arròs", "quantity": "100", "unit": "g"}], True)
        after = recipe_content("Cou", [{"name": "Arròs", "quantity": "200", "unit": "g"}], True)
        save_recipe(DjangoDishRepository(), self.clock, self.dish.pk, 1, before, True)
        version = change_menu(self.repo, self.clock, self.week, (0, "lunch"), 1, "assign", self.dish.pk).version
        change_menu(self.repo, self.clock, self.week, (1, "lunch"), version, "assign", self.dish.pk)
        updated = Event()
        finish = Event()

        class PausedPublisher(DjangoDishRepository):
            def refresh_dish(self, dish_id, current_week):
                super().refresh_dish(dish_id, current_week)
                updated.set()
                if not finish.wait(timeout=10):
                    raise RuntimeError("Timed out waiting for the read")

        def write():
            close_old_connections()
            try:
                save_recipe(PausedPublisher(), self.clock, self.dish.pk, 2, after, True)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=1) as pool:
            writer = pool.submit(write)
            try:
                self.assertTrue(updated.wait(timeout=10))
                self.assertEqual(get_ingredient_reminder(self.repo, self.week).rows[0]["quantity"], Decimal("200"))
            finally:
                finish.set()
            writer.result(timeout=10)
        self.assertEqual(get_ingredient_reminder(self.repo, self.week).rows[0]["quantity"], Decimal("400"))

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

    def test_archive_racing_assignment_has_serial_outcome(self):
        from menus.application.dishes import DishConflict, set_archived
        from menus.application.planning import PlanningConflict, change_menu
        from menus.infrastructure.django_dishes import DjangoDishRepository
        from menus.infrastructure.django_planning import DjangoPlanningRepository
        from menus.models import DishRecord
        self.require_file()
        barrier = Barrier(2, timeout=10)
        class SynchronizedDish(DjangoDishRepository):
            def set_archived(self, dish_id, version, archived):
                DishRecord.objects.get(pk=dish_id)
                barrier.wait()
                return super().set_archived(dish_id, version, archived)
        class SynchronizedPlanning(DjangoPlanningRepository):
            def dish_snapshot(self, dish_id, include_archived=False):
                snapshot = super().dish_snapshot(dish_id, include_archived)
                barrier.wait()
                return snapshot
        def archive():
            close_old_connections()
            try:
                set_archived(SynchronizedDish(), self.dish.pk, 1, True)
                return "saved"
            except (DishConflict, DatabaseError):
                return "rejected"
            finally:
                close_old_connections()
        def assign():
            close_old_connections()
            try:
                change_menu(SynchronizedPlanning(), self.clock, self.week, (0, "lunch"), 1, "assign", self.dish.pk)
                return "saved"
            except (PlanningConflict, ValueError, DatabaseError):
                return "rejected"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(archive), pool.submit(assign)]
            outcomes = [future.result(timeout=15) for future in futures]
        self.assertCountEqual(outcomes, ["saved", "rejected"])
        dish = DishRecord.objects.get(pk=self.dish.pk)
        selected = self.repo.get(self.week).slots[(0, "lunch")].state == "selected"
        self.assertEqual(dish.archived, outcomes[0] == "saved")
        self.assertEqual(selected, outcomes[1] == "saved")
