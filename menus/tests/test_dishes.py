from datetime import date, timedelta
from uuid import uuid4
from django.test import TestCase
from menus.application.dishes import DishConflict, create_dish, update_dish
from menus.application.planning import change_menu
from menus.tests.planning_fixtures import create_legacy_menu
from menus.domain.dish_edit import DishInput
from menus.infrastructure.django_dishes import DjangoDishRepository
from menus.infrastructure.django_planning import DjangoPlanningRepository
from menus.tests.test_planning import Clock


class DishTests(TestCase):
    def test_recipe_error_returns_to_editor_and_rejects_conflicting_intent(self):
        from django.urls import reverse
        dish_id = create_dish(DjangoDishRepository(), DishInput("Plat", "cereals", frozenset(), "both", False), uuid4())
        publish = reverse("recipe_publish", args=[dish_id])
        editor = reverse("recipe_edit", args=[dish_id])
        data = {"action": "publish", "version": "1", "preparation": "", "name": "Arròs", "quantity": "", "unit": "g"}
        response = self.client.post(publish, data)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, f'action="{editor}"', status_code=400)
        response = self.client.post(publish, {**data, "action": "review_discard"})
        self.assertEqual(response.status_code, 400)
        response = self.client.post(editor, {**data, "action": "review_discard"})
        self.assertContains(response, f'action="{editor}"')

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
            create_legacy_menu(plans, target)
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
        create_legacy_menu(plans, week)
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

    def test_failed_propagation_rolls_back_dish_and_weeks(self):
        from unittest.mock import patch
        dishes, plans = DjangoDishRepository(), DjangoPlanningRepository()
        week = date(2026, 11, 16)
        dish_id = create_dish(dishes, DishInput("Plat", "cereals", frozenset(), "both", False), uuid4())
        for target in (week, week + timedelta(days=7)):
            create_legacy_menu(plans, target)
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

    def test_contextual_recipe_write_rejects_changed_slot_and_rollover(self):
        from menus.application.planning import PlanningConflict, Rollover
        from menus.application.recipes import save_recipe
        from menus.domain.recipe import recipe_content
        dishes, plans = DjangoDishRepository(), DjangoPlanningRepository()
        week = date(2026, 11, 16)
        dish_id = create_dish(dishes, DishInput("Plat A", "cereals", frozenset(), "both", False), uuid4())
        create_legacy_menu(plans, week)
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
        from menus.application.shopping import get_ingredient_reminder
        dishes, plans = DjangoDishRepository(), DjangoPlanningRepository()
        old_week = date(2026, 11, 16)
        next_week = old_week + timedelta(days=7)
        dish_id = create_dish(dishes, DishInput("Plat sintètic", "cereals", frozenset(), "both", False), uuid4())
        first = recipe_content("Cou", [{"name": "Arròs", "quantity": "160", "unit": "g"}], True)
        save_recipe(dishes, Clock(old_week), dish_id, 1, first, True)
        for week in (old_week, next_week):
            create_legacy_menu(plans, week)
            change_menu(plans, Clock(old_week), week, (0, "lunch"), 1, "assign", dish_id)
        second = recipe_content("Cou", [{"name": "Arròs", "quantity": "300", "unit": "g"}], True)
        save_recipe(dishes, Clock(next_week), dish_id, 2, second, True)
        self.assertEqual(str(get_ingredient_reminder(plans, old_week).rows[0]["quantity"]), "160.000")
        self.assertEqual(str(get_ingredient_reminder(plans, next_week).rows[0]["quantity"]), "300.000")

    def test_database_rejects_invalid_taste_overlay(self):
        from django.db import IntegrityError, transaction
        from menus.models import GeneratedOverlayRecord, ShoppingStateRecord
        week = date(2026, 11, 16)
        plans = DjangoPlanningRepository()
        create_legacy_menu(plans, week)
        state = ShoppingStateRecord.objects.create(week_id=week)
        with self.assertRaises(IntegrityError), transaction.atomic():
            GeneratedOverlayRecord.objects.create(shopping=state, ingredient_key="sal", family="taste", last_name="Sal", adjusted_quantity="1.000")
        self.assertFalse(GeneratedOverlayRecord.objects.exists())

    def test_snapshot_refresh_rebases_unrelated_undo_and_invalidates_related(self):
        from menus.application.planning import move_or_undo
        dishes, plans = DjangoDishRepository(), DjangoPlanningRepository()
        week = date(2026, 11, 16)
        a = create_dish(dishes, DishInput("Plat A", "cereals", frozenset(), "both", False), uuid4())
        b = create_dish(dishes, DishInput("Plat B", "eggs", frozenset(), "both", False), uuid4())
        create_legacy_menu(plans, week)
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
        create_legacy_menu(plans, week)
        change_menu(plans, Clock(week), week, (0, "lunch"), 1, "assign", dish_id)
        set_archived(dishes, dish_id, 1, True)
        self.assertIsNone(plans.dish_snapshot(dish_id))
        self.assertEqual(plans.get(week).slots[(0, "lunch")].dish["name"], "Plat sintètic")
        with self.assertRaises(ValueError):
            change_menu(plans, Clock(week), week, (1, "lunch"), 2, "assign", dish_id)
        set_archived(dishes, dish_id, 2, False)
        self.assertIsNotNone(plans.dish_snapshot(dish_id))

    def test_catalogue_search_is_accent_insensitive_and_deduplicated(self):
        from django.urls import reverse
        repo = DjangoDishRepository()
        dish_id = create_dish(repo, DishInput("Cafè sintètic", "cereals", frozenset({"vegetables"}), "both", False), uuid4())
        response = self.client.get(reverse("catalogue"), {"q": "CAFE", "category": "vegetables"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cafè sintètic", count=1)
        self.assertContains(response, reverse("dish_detail", args=[dish_id]))
