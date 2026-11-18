from datetime import date, timedelta
from uuid import uuid4
from django.test import TestCase
from menus.application.dishes import DishConflict, create_dish, update_dish
from menus.application.planning import create_menu, change_menu
from menus.domain.dish_edit import DishInput
from menus.infrastructure.django_dishes import DjangoDishRepository
from menus.infrastructure.django_planning import DjangoPlanningRepository
from menus.tests.test_planning import Clock


class DishTests(TestCase):
    def test_receipt_replay_and_conflict(self):
        repo = DjangoDishRepository()
        token = uuid4()
        data = DishInput("Plat", "cereals", frozenset({"vegetables"}), "both", False)
        first = create_dish(repo, data, token)
        self.assertEqual(create_dish(repo, data, token), first)
        with self.assertRaises(DishConflict):
            create_dish(repo, DishInput("Altre", "cereals", frozenset(), "both", False), token)

    def test_edit_updates_only_editable_snapshots(self):
        dishes, plans = DjangoDishRepository(), DjangoPlanningRepository()
        week = date(2026, 11, 16)
        data = DishInput("Plat", "cereals", frozenset(), "both", False)
        dish_id = create_dish(dishes, data, uuid4())
        for target in (week, week + timedelta(days=7)):
            create_menu(plans, Clock(week), target)
            change_menu(plans, Clock(week), target, (0, "lunch"), 1, "assign", dish_id)
        update_dish(dishes, Clock(week + timedelta(days=7)), dish_id, DishInput("Nou", "eggs", frozenset(), "both", False), 1)
        self.assertEqual(plans.get(week).slots[(0, "lunch")].dish["name"], "Plat")
        self.assertEqual(plans.get(week + timedelta(days=7)).slots[(0, "lunch")].dish["name"], "Nou")

    def test_recipe_effective_draft_and_publication_refresh(self):
        from menus.application.recipes import save_recipe
        from menus.domain.recipe import recipe_content
        dishes, plans = DjangoDishRepository(), DjangoPlanningRepository()
        week = date(2026, 11, 16)
        dish_id = create_dish(dishes, DishInput("Plat", "cereals", frozenset(), "both", False), uuid4())
        create_menu(plans, Clock(week), week)
        change_menu(plans, Clock(week), week, (0, "lunch"), 1, "assign", dish_id)
        draft = recipe_content("", [{"name": "Arròs", "quantity": "", "unit": "g"}])
        save_recipe(dishes, Clock(week), dish_id, 1, draft)
        self.assertEqual(plans.get(week).slots[(0, "lunch")].dish["recipe_status"], "draft")
        published = recipe_content("Cou", [{"name": "Arròs", "quantity": "160", "unit": "g"}], True)
        save_recipe(dishes, Clock(week), dish_id, 2, published, True)
        save_recipe(dishes, Clock(week), dish_id, 3, draft)
        snapshot = plans.get(week).slots[(0, "lunch")].dish
        self.assertEqual(snapshot["recipe_status"], "published")
        self.assertEqual(snapshot["recipe_content"], published)

    def test_shopping_reconciliation_preserves_adjusted_orphan(self):
        from menus.application.recipes import save_recipe
        from menus.application.shopping import mutate_shopping
        from menus.domain.recipe import recipe_content
        from menus.infrastructure.django_shopping import DjangoShoppingRepository
        dishes, plans, shopping = DjangoDishRepository(), DjangoPlanningRepository(), DjangoShoppingRepository()
        week = date(2026, 11, 16)
        dish_id = create_dish(dishes, DishInput("Plat", "cereals", frozenset(), "both", False), uuid4())
        save_recipe(dishes, Clock(week), dish_id, 1, recipe_content("Cou", [{"name": "Arròs", "quantity": "160", "unit": "g"}], True), True)
        create_menu(plans, Clock(week), week)
        change_menu(plans, Clock(week), week, (0, "lunch"), 1, "assign", dish_id)
        mutate_shopping(shopping, Clock(week), week, 2, 0, "adjust", {"key": "arròs", "family": "g", "quantity": "200"})
        change_menu(plans, Clock(week), week, (0, "lunch"), 2, "remove")
        view = shopping.read(week)
        self.assertEqual(len(view[-1]), 1)
        self.assertEqual(view[-1][0].adjusted_quantity, "200.000")

    def test_manual_receipt_replay_survives_deletion_and_rollover(self):
        from menus.application.shopping import mutate_shopping
        from menus.infrastructure.django_shopping import DjangoShoppingRepository, ShoppingConflict
        from menus.models import ManualShoppingItemRecord
        plans, shopping = DjangoPlanningRepository(), DjangoShoppingRepository()
        week = date(2026, 11, 16)
        create_menu(plans, Clock(week), week)
        data = {"name": "Pa", "quantity": "", "unit": "", "token": str(uuid4())}
        mutate_shopping(shopping, Clock(week), week, 1, 0, "manual_add", data)
        item = ManualShoppingItemRecord.objects.get()
        item_id = item.pk
        mutate_shopping(shopping, Clock(week), week, 1, 1, "manual_remove", {"id": item_id})
        self.assertEqual(mutate_shopping(shopping, Clock(week + timedelta(days=7)), week, 1, 0, "manual_add", data), item_id)
        self.assertFalse(ManualShoppingItemRecord.objects.exists())
        with self.assertRaises(ShoppingConflict):
            mutate_shopping(shopping, Clock(week), week, 1, 2, "manual_add", {**data, "name": "Llet"})

    def test_failed_propagation_rolls_back_dish_and_weeks(self):
        from unittest.mock import patch
        dishes, plans = DjangoDishRepository(), DjangoPlanningRepository()
        week = date(2026, 11, 16)
        dish_id = create_dish(dishes, DishInput("Plat", "cereals", frozenset(), "both", False), uuid4())
        for target in (week, week + timedelta(days=7)):
            create_menu(plans, Clock(week), target)
            change_menu(plans, Clock(week), target, (0, "lunch"), 1, "assign", dish_id)
        original = DjangoPlanningRepository.save
        def fail_later(repository, menu, version):
            if menu.week > week:
                raise RuntimeError("synthetic failure")
            return original(repository, menu, version)
        with patch.object(DjangoPlanningRepository, "save", fail_later), self.assertRaises(RuntimeError):
            update_dish(dishes, Clock(week), dish_id, DishInput("Nou", "eggs", frozenset(), "both", False), 1)
        from menus.models import DishRecord
        self.assertEqual(DishRecord.objects.get(pk=dish_id).name, "Plat")
        self.assertEqual(plans.get(week).slots[(0, "lunch")].dish["name"], "Plat")

    def test_matching_check_and_override_survive_refresh_then_orphan_return(self):
        from menus.application.recipes import save_recipe
        from menus.application.shopping import mutate_shopping
        from menus.domain.recipe import recipe_content
        from menus.infrastructure.django_shopping import DjangoShoppingRepository
        dishes, plans, shopping = DjangoDishRepository(), DjangoPlanningRepository(), DjangoShoppingRepository()
        week = date(2026, 11, 16)
        dish_id = create_dish(dishes, DishInput("Plat A", "cereals", frozenset(), "both", False), uuid4())
        first = recipe_content("Cou", [{"name": "Arròs", "quantity": "160", "unit": "g"}], True)
        save_recipe(dishes, Clock(week), dish_id, 1, first, True)
        create_menu(plans, Clock(week), week)
        change_menu(plans, Clock(week), week, (0, "lunch"), 1, "assign", dish_id)
        key = {"key": "arròs", "family": "g"}
        mutate_shopping(shopping, Clock(week), week, 2, 0, "adjust", {**key, "quantity": "200"})
        mutate_shopping(shopping, Clock(week), week, 2, 1, "check", {**key, "checked": "1"})
        second = recipe_content("Cou", [{"name": "Arròs", "quantity": "180", "unit": "g"}], True)
        save_recipe(dishes, Clock(week), dish_id, 2, second, True)
        menu, state, rows, *_ = shopping.read(week)
        self.assertEqual(str(rows[0]["quantity"]), "180.000")
        self.assertTrue(rows[0]["overlay"].checked)
        self.assertEqual(rows[0]["overlay"].adjusted_quantity, "200.000")
        change_menu(plans, Clock(week), week, (0, "lunch"), menu.version, "remove")
        menu, state, rows, _, _, orphans = shopping.read(week)
        self.assertFalse(orphans[0].checked)
        change_menu(plans, Clock(week), week, (0, "lunch"), menu.version, "assign", dish_id)
        row = shopping.read(week)[2][0]
        self.assertEqual(row["overlay"].adjusted_quantity, "200.000")
        self.assertFalse(row["overlay"].checked)

    def test_contextual_recipe_write_rejects_changed_slot_and_rollover(self):
        from menus.application.planning import PlanningConflict, Rollover
        from menus.application.recipes import save_recipe
        from menus.domain.recipe import recipe_content
        dishes, plans = DjangoDishRepository(), DjangoPlanningRepository()
        week = date(2026, 11, 16)
        dish_id = create_dish(dishes, DishInput("Plat A", "cereals", frozenset(), "both", False), uuid4())
        create_menu(plans, Clock(week), week)
        change_menu(plans, Clock(week), week, (0, "lunch"), 1, "assign", dish_id)
        change_menu(plans, Clock(week), week, (0, "lunch"), 2, "remove")
        content = recipe_content("", [])
        with self.assertRaises(PlanningConflict):
            save_recipe(dishes, Clock(week), dish_id, 1, content, context=(week, (0, "lunch")))
        with self.assertRaises(Rollover):
            save_recipe(dishes, Clock(week, week + timedelta(days=7)), dish_id, 1, content)
        from menus.models import RecipeRecord, DishRecord
        self.assertFalse(RecipeRecord.objects.filter(dish_id=dish_id).exists())
        self.assertEqual(DishRecord.objects.get(pk=dish_id).version, 1)

    def test_historical_shopping_stays_frozen_after_recipe_edit(self):
        from menus.application.recipes import save_recipe
        from menus.domain.recipe import recipe_content
        from menus.infrastructure.django_shopping import DjangoShoppingRepository
        dishes, plans, shopping = DjangoDishRepository(), DjangoPlanningRepository(), DjangoShoppingRepository()
        old_week = date(2026, 11, 16)
        next_week = old_week + timedelta(days=7)
        dish_id = create_dish(dishes, DishInput("Plat sintètic", "cereals", frozenset(), "both", False), uuid4())
        first = recipe_content("Cou", [{"name": "Arròs", "quantity": "160", "unit": "g"}], True)
        save_recipe(dishes, Clock(old_week), dish_id, 1, first, True)
        for week in (old_week, next_week):
            create_menu(plans, Clock(old_week), week)
            change_menu(plans, Clock(old_week), week, (0, "lunch"), 1, "assign", dish_id)
        second = recipe_content("Cou", [{"name": "Arròs", "quantity": "300", "unit": "g"}], True)
        save_recipe(dishes, Clock(next_week), dish_id, 2, second, True)
        self.assertEqual(str(shopping.read(old_week)[2][0]["quantity"]), "160.000")
        self.assertEqual(str(shopping.read(next_week)[2][0]["quantity"]), "300.000")

    def test_database_rejects_invalid_taste_overlay(self):
        from django.db import IntegrityError, transaction
        from menus.models import GeneratedOverlayRecord, ShoppingStateRecord
        week = date(2026, 11, 16)
        plans = DjangoPlanningRepository()
        create_menu(plans, Clock(week), week)
        state = ShoppingStateRecord.objects.create(week_id=week)
        with self.assertRaises(IntegrityError), transaction.atomic():
            GeneratedOverlayRecord.objects.create(shopping=state, ingredient_key="sal", family="taste", last_name="Sal", adjusted_quantity="1.000")
        self.assertFalse(GeneratedOverlayRecord.objects.exists())

    def test_adjustment_equal_to_base_clears_override_and_keeps_check(self):
        from menus.application.recipes import save_recipe
        from menus.application.shopping import mutate_shopping
        from menus.domain.recipe import recipe_content
        from menus.infrastructure.django_shopping import DjangoShoppingRepository
        dishes, plans, shopping = DjangoDishRepository(), DjangoPlanningRepository(), DjangoShoppingRepository()
        week = date(2026, 11, 16)
        dish_id = create_dish(dishes, DishInput("Plat", "cereals", frozenset(), "both", False), uuid4())
        save_recipe(dishes, Clock(week), dish_id, 1, recipe_content("Cou", [{"name": "Arròs", "quantity": "160", "unit": "g"}], True), True)
        create_menu(plans, Clock(week), week)
        change_menu(plans, Clock(week), week, (0, "lunch"), 1, "assign", dish_id)
        key = {"key": "arròs", "family": "g"}
        mutate_shopping(shopping, Clock(week), week, 2, 0, "adjust", {**key, "quantity": "160"})
        self.assertIsNone(shopping.read(week)[1])
        mutate_shopping(shopping, Clock(week), week, 2, 0, "check", {**key, "checked": "1"})
        mutate_shopping(shopping, Clock(week), week, 2, 1, "adjust", {**key, "quantity": "200"})
        mutate_shopping(shopping, Clock(week), week, 2, 2, "adjust", {**key, "quantity": "160"})
        overlay = shopping.read(week)[2][0]["overlay"]
        self.assertTrue(overlay.checked)
        self.assertIsNone(overlay.adjusted_quantity)

    def test_snapshot_refresh_rebases_unrelated_undo_and_invalidates_related(self):
        from menus.application.planning import move_or_undo
        dishes, plans = DjangoDishRepository(), DjangoPlanningRepository()
        week = date(2026, 11, 16)
        a = create_dish(dishes, DishInput("Plat A", "cereals", frozenset(), "both", False), uuid4())
        b = create_dish(dishes, DishInput("Plat B", "eggs", frozenset(), "both", False), uuid4())
        create_menu(plans, Clock(week), week)
        change_menu(plans, Clock(week), week, (0, "lunch"), 1, "assign", a)
        change_menu(plans, Clock(week), week, (2, "lunch"), 2, "assign", b)
        move_or_undo(plans, Clock(week), week, 3, (0, "lunch"), (1, "lunch"))
        update_dish(dishes, Clock(week), b, DishInput("Plat B nou", "eggs", frozenset(), "both", False), 1)
        menu = plans.get(week)
        self.assertEqual(menu.undo["eligible_version"], menu.version)
        move_or_undo(plans, Clock(week), week, menu.version)
        menu = plans.get(week)
        move_or_undo(plans, Clock(week), week, menu.version, (0, "lunch"), (1, "lunch"))
        update_dish(dishes, Clock(week), a, DishInput("Plat A nou", "cereals", frozenset(), "both", False), 1)
        self.assertIsNone(plans.get(week).undo)

    def test_archive_restore_preserves_selected_snapshot_and_picker_eligibility(self):
        from menus.application.dishes import set_archived
        dishes, plans = DjangoDishRepository(), DjangoPlanningRepository()
        week = date(2026, 11, 16)
        dish_id = create_dish(dishes, DishInput("Plat sintètic", "cereals", frozenset(), "both", False), uuid4())
        create_menu(plans, Clock(week), week)
        change_menu(plans, Clock(week), week, (0, "lunch"), 1, "assign", dish_id)
        set_archived(dishes, dish_id, 1, True)
        self.assertIsNone(plans.dish_snapshot(dish_id))
        self.assertEqual(plans.get(week).slots[(0, "lunch")].dish["name"], "Plat sintètic")
        with self.assertRaises(ValueError):
            change_menu(plans, Clock(week), week, (1, "lunch"), 2, "assign", dish_id)
        set_archived(dishes, dish_id, 2, False)
        self.assertIsNotNone(plans.dish_snapshot(dish_id))

    def test_manual_item_and_check_survive_plan_recalculation(self):
        from menus.application.shopping import mutate_shopping
        from menus.infrastructure.django_shopping import DjangoShoppingRepository
        from menus.models import ManualShoppingItemRecord
        plans, shopping = DjangoPlanningRepository(), DjangoShoppingRepository()
        week = date(2026, 11, 16)
        create_menu(plans, Clock(week), week)
        mutate_shopping(shopping, Clock(week), week, 1, 0, "manual_add", {"name": "Pa", "quantity": "2", "unit": "unit", "token": str(uuid4())})
        item_id = ManualShoppingItemRecord.objects.get().pk
        mutate_shopping(shopping, Clock(week), week, 1, 1, "manual_check", {"id": item_id, "checked": "1"})
        change_menu(plans, Clock(week), week, (0, "lunch"), 1, "skip")
        view = shopping.read(week)
        self.assertEqual(view[1].manual_items[0].name, "Pa")
        self.assertTrue(view[1].manual_items[0].checked)

    def test_catalogue_search_is_accent_insensitive_and_deduplicated(self):
        from django.urls import reverse
        repo = DjangoDishRepository()
        dish_id = create_dish(repo, DishInput("Cafè sintètic", "cereals", frozenset({"vegetables"}), "both", False), uuid4())
        response = self.client.get(reverse("catalogue"), {"q": "CAFE", "category": "vegetables"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cafè sintètic", count=1)
        self.assertContains(response, reverse("dish_detail", args=[dish_id]))

    def test_corrupt_overlay_aborts_planning_write(self):
        from menus.application.errors import DataIntegrityError
        from menus.models import GeneratedOverlayRecord, ShoppingStateRecord
        plans = DjangoPlanningRepository()
        week = date(2026, 11, 16)
        create_menu(plans, Clock(week), week)
        state = ShoppingStateRecord.objects.create(week_id=week)
        GeneratedOverlayRecord.objects.create(shopping=state, ingredient_key="arròs", family="g", last_name="Arròs", last_base_quantity="100.000", adjusted_quantity="1e3")
        with self.assertRaises(DataIntegrityError):
            change_menu(plans, Clock(week), week, (0, "lunch"), 1, "skip")
        menu = plans.get(week)
        self.assertEqual(menu.version, 1)
        self.assertEqual(menu.slots[(0, "lunch")].state, "pending")

    def test_maximum_override_survives_orphan_and_reappearance(self):
        from menus.application.recipes import save_recipe
        from menus.application.shopping import mutate_shopping
        from menus.domain.recipe import recipe_content
        from menus.infrastructure.django_shopping import DjangoShoppingRepository
        dishes, plans, shopping = DjangoDishRepository(), DjangoPlanningRepository(), DjangoShoppingRepository()
        week = date(2026, 11, 16)
        dish_id = create_dish(dishes, DishInput("Plat sintètic", "cereals", frozenset(), "both", False), uuid4())
        save_recipe(dishes, Clock(week), dish_id, 1, recipe_content("Cou", [{"name": "Arròs", "quantity": "1", "unit": "g"}], True), True)
        create_menu(plans, Clock(week), week)
        change_menu(plans, Clock(week), week, (0, "lunch"), 1, "assign", dish_id)
        maximum = "1399999999998600.000"
        mutate_shopping(shopping, Clock(week), week, 2, 0, "adjust", {"key": "arròs", "family": "g", "quantity": maximum})
        change_menu(plans, Clock(week), week, (0, "lunch"), 2, "remove")
        self.assertEqual(shopping.read(week)[-1][0].adjusted_quantity, maximum)
        change_menu(plans, Clock(week), week, (0, "lunch"), 3, "assign", dish_id)
        self.assertEqual(shopping.read(week)[2][0]["overlay"].adjusted_quantity, maximum)
