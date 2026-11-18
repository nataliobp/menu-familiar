from datetime import date, timedelta
from django.test import TestCase
from menus.application.planning import PastWeek, PlanningConflict, Rollover, change_menu, create_menu
from menus.infrastructure.django_planning import DjangoPlanningRepository
from menus.models import DishRecord, TemplateSlotRecord, WeeklyMenuRecord


class Clock:
    def __init__(self, *days):
        self.days = list(days)
    def today(self):
        return self.days.pop(0) if len(self.days) > 1 else self.days[0]


class PlanningTests(TestCase):
    def setUp(self):
        self.repo = DjangoPlanningRepository()
        self.week = date(2026, 11, 16)
        self.clock = Clock(self.week)
        self.dish = DishRecord.objects.create(name="Plat", primary_category_id="cereals", meal_preference="both", special_occasion=False)

    def test_create_copies_template_and_is_idempotent(self):
        TemplateSlotRecord.objects.filter(day_index=0, meal="lunch").update(suggested_category_id="cereals")
        menu = create_menu(self.repo, self.clock, self.week)
        self.assertEqual(menu.slots[(0, "lunch")].suggestion, ("cereals", "Cereals"))
        TemplateSlotRecord.objects.filter(day_index=0, meal="lunch").update(suggested_category_id="eggs")
        change_menu(self.repo, self.clock, self.week, (0, "lunch"), 1, "assign", self.dish.pk)
        again = create_menu(self.repo, self.clock, self.week)
        self.assertEqual(again.version, 2)
        self.assertEqual(again.slots[(0, "lunch")].suggestion, ("cereals", "Cereals"))

    def test_guards_and_rollover_rollback(self):
        with self.assertRaises(PastWeek):
            create_menu(self.repo, self.clock, self.week - timedelta(days=7))
        with self.assertRaises(Rollover):
            create_menu(self.repo, Clock(self.week, self.week + timedelta(days=7)), self.week)
        self.assertFalse(WeeklyMenuRecord.objects.exists())
        create_menu(self.repo, self.clock, self.week)
        change_menu(self.repo, self.clock, self.week, (0, "lunch"), 1, "assign", self.dish.pk)
        with self.assertRaises(PlanningConflict):
            change_menu(self.repo, self.clock, self.week, (0, "lunch"), 1, "remove")
        self.assertEqual(self.repo.get(self.week).slots[(0, "lunch")].state, "selected")

    def test_web_preview_creation_and_assignment(self):
        from unittest.mock import patch
        from django.urls import reverse
        with patch("menus.web.views.MadridClock", return_value=self.clock):
            url = reverse("menu_week", args=[self.week.isoformat()])
            response = self.client.get(url)
            self.assertContains(response, "Crea el menú")
            self.assertFalse(WeeklyMenuRecord.objects.exists())
            self.assertEqual(self.client.post(reverse("menu_create", args=[self.week.isoformat()])).status_code, 302)
            picker = reverse("menu_picker", args=[self.week.isoformat(), 0, "lunch"])
            self.assertContains(self.client.get(picker), "Plat")
            action = reverse("menu_action", args=[self.week.isoformat(), 0, "lunch", "assign"])
            self.assertEqual(self.client.post(action, {"version": 1, "dish": self.dish.pk}).status_code, 302)
            self.assertContains(self.client.get(url), "Plat")

    def test_move_undo_and_invalidation_survive_reload(self):
        from menus.application.planning import move_or_undo
        create_menu(self.repo, self.clock, self.week)
        change_menu(self.repo, self.clock, self.week, (0, "lunch"), 1, "assign", self.dish.pk)
        move_or_undo(self.repo, self.clock, self.week, 2, (0, "lunch"), (1, "dinner"))
        menu = self.repo.get(self.week)
        self.assertEqual(menu.slots[(1, "dinner")].state, "selected")
        move_or_undo(self.repo, self.clock, self.week, 3)
        self.assertEqual(self.repo.get(self.week).slots[(0, "lunch")].state, "selected")
        move_or_undo(self.repo, self.clock, self.week, 4, (0, "lunch"), (1, "dinner"))
        change_menu(self.repo, self.clock, self.week, (2, "lunch"), 5, "skip")
        with self.assertRaises(ValueError):
            move_or_undo(self.repo, self.clock, self.week, 6)

    def test_recipe_and_shopping_pages_render(self):
        from unittest.mock import patch
        from django.urls import reverse
        with patch("menus.web.views.MadridClock", return_value=self.clock):
            create_menu(self.repo, self.clock, self.week)
            self.assertEqual(self.client.get(reverse("recipe_edit", args=[self.dish.pk])).status_code, 200)
            self.assertEqual(self.client.get(reverse("shopping_week", args=[self.week.isoformat()])).status_code, 200)

    def test_skipped_move_requires_confirmation_and_undo_restores_skip(self):
        from menus.application.planning import move_or_undo
        create_menu(self.repo, self.clock, self.week)
        change_menu(self.repo, self.clock, self.week, (0, "lunch"), 1, "assign", self.dish.pk)
        change_menu(self.repo, self.clock, self.week, (1, "lunch"), 2, "skip")
        with self.assertRaises(ValueError):
            move_or_undo(self.repo, self.clock, self.week, 3, (0, "lunch"), (1, "lunch"))
        move_or_undo(self.repo, self.clock, self.week, 3, (0, "lunch"), (1, "lunch"), True)
        move_or_undo(self.repo, self.clock, self.week, 4)
        menu = self.repo.get(self.week)
        self.assertEqual(menu.slots[(0, "lunch")].state, "selected")
        self.assertEqual(menu.slots[(1, "lunch")].state, "skipped")

    def test_direct_historical_write_refused(self):
        create_menu(self.repo, self.clock, self.week)
        with self.assertRaises(PastWeek):
            change_menu(self.repo, Clock(self.week + timedelta(days=7)), self.week, (0, "lunch"), 1, "assign", self.dish.pk)
        self.assertEqual(self.repo.get(self.week).slots[(0, "lunch")].state, "pending")

    def test_remove_requires_confirmation_and_get_is_read_only(self):
        from unittest.mock import patch
        from django.urls import reverse
        create_menu(self.repo, self.clock, self.week)
        change_menu(self.repo, self.clock, self.week, (0, "lunch"), 1, "assign", self.dish.pk)
        url = reverse("confirm_remove", args=[self.week.isoformat(), 0, "lunch"])
        with patch("menus.web.views.MadridClock", return_value=self.clock):
            self.assertEqual(self.client.get(url).status_code, 200)
            self.assertEqual(self.client.post(url, {"version": 2}).status_code, 200)
            self.assertEqual(self.repo.get(self.week).slots[(0, "lunch")].state, "selected")
            self.assertEqual(self.client.post(url, {"version": 2, "confirm": "yes"}).status_code, 302)
            self.assertEqual(self.repo.get(self.week).slots[(0, "lunch")].state, "pending")

    def test_corrupt_snapshot_is_unavailable_not_silently_repaired(self):
        from django.urls import reverse
        from menus.models import MenuSlotRecord
        create_menu(self.repo, self.clock, self.week)
        change_menu(self.repo, self.clock, self.week, (0, "lunch"), 1, "assign", self.dish.pk)
        record = MenuSlotRecord.objects.get(weekly_menu_id=self.week, day_index=0, meal="lunch")
        record.dish_snapshot["schema_version"] = 999
        record.save(update_fields=["dish_snapshot"])
        response = self.client.get(reverse("menu_week", args=[self.week.isoformat()]))
        self.assertEqual(response.status_code, 503)
        record.refresh_from_db()
        self.assertEqual(record.dish_snapshot["schema_version"], 999)

    def test_shopping_invalid_input_is_preserved(self):
        from unittest.mock import patch
        from uuid import uuid4
        from django.urls import reverse
        create_menu(self.repo, self.clock, self.week)
        url = reverse("shopping_action", args=[self.week.isoformat(), "manual_add"])
        with patch("menus.web.views.MadridClock", return_value=self.clock):
            response = self.client.post(url, {"menu_version": 1, "overlay_version": 0, "token": str(uuid4()), "name": "Producte sintètic", "quantity": "abc", "unit": "g"})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Producte sintètic", status_code=400)
        self.assertContains(response, "abc", status_code=400)

    def test_recipe_publication_through_web_and_shopping_projection(self):
        from unittest.mock import patch
        from django.urls import reverse
        with patch("menus.web.views.MadridClock", return_value=self.clock):
            create_menu(self.repo, self.clock, self.week)
            change_menu(self.repo, self.clock, self.week, (0, "lunch"), 1, "assign", self.dish.pk)
            response = self.client.post(reverse("recipe_publish", args=[self.dish.pk]), {"version": 1, "preparation": "Coeu-ho", "name": ["Arròs"], "quantity": ["160"], "unit": ["g"], "note": [""]})
            self.assertEqual(response.status_code, 302)
            response = self.client.get(reverse("shopping_week", args=[self.week.isoformat()]))
            self.assertContains(response, "Arròs")
            self.assertContains(response, "160,000")
            recipe = self.client.get(reverse("recipe_view", args=[self.dish.pk]))
            self.assertContains(recipe, "160,000")

    def test_recipe_discard_review_preserves_unsaved_values(self):
        from django.urls import reverse
        url = reverse("recipe_edit", args=[self.dish.pk])
        payload = {"version": 1, "preparation": "Text encara no desat", "name": ["Ingredient"], "quantity": ["12"], "unit": ["g"], "note": [""], "action": "review_discard"}
        response = self.client.post(url, payload)
        self.assertContains(response, "Descarta els canvis?")
        payload["action"] = "continue"
        response = self.client.post(url, payload)
        self.assertContains(response, "Text encara no desat")
        self.assertContains(response, "Ingredient")
        from menus.models import RecipeRecord
        self.assertFalse(RecipeRecord.objects.exists())

    def test_shopping_retry_preserves_creation_token(self):
        from unittest.mock import patch
        from uuid import uuid4
        from django.db import OperationalError
        from django.urls import reverse
        token = str(uuid4())
        url = reverse("shopping_action", args=[self.week.isoformat(), "manual_add"])
        data = {"menu_version": 1, "overlay_version": 0, "token": token, "name": "Producte de prova", "quantity": "", "unit": ""}
        with patch("menus.web.views.mutate_shopping", side_effect=OperationalError("synthetic lock")):
            response = self.client.post(url, data)
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, token, status_code=503)
        self.assertContains(response, "Producte de prova", status_code=503)

    def test_recipe_conflict_shows_submitted_and_current_values(self):
        from unittest.mock import patch
        from django.urls import reverse
        with patch("menus.web.views.MadridClock", return_value=self.clock):
            url = reverse("recipe_publish", args=[self.dish.pk])
            data = {"version": 1, "preparation": "Preparació actual", "name": ["Arròs"], "quantity": ["160"], "unit": ["g"], "note": [""]}
            self.assertEqual(self.client.post(url, data).status_code, 302)
            data["preparation"] = "Preparació enviada"
            response = self.client.post(url, data)
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "Preparació actual", status_code=409)
        self.assertContains(response, "Preparació enviada", status_code=409)

    def test_move_failure_after_slot_write_rolls_back_root_and_undo(self):
        from unittest.mock import patch
        from django.db.models.query import QuerySet
        from menus.application.planning import move_or_undo
        from menus.models import MenuSlotRecord
        create_menu(self.repo, self.clock, self.week)
        change_menu(self.repo, self.clock, self.week, (0, "lunch"), 1, "assign", self.dish.pk)
        original = QuerySet.update
        writes = 0
        def fail_on_second_slot(queryset, **kwargs):
            nonlocal writes
            if queryset.model is MenuSlotRecord:
                writes += 1
                if writes == 2:
                    raise RuntimeError("synthetic write failure")
            return original(queryset, **kwargs)
        with patch.object(QuerySet, "update", fail_on_second_slot), self.assertRaises(RuntimeError):
            move_or_undo(self.repo, self.clock, self.week, 2, (0, "lunch"), (1, "lunch"))
        menu = self.repo.get(self.week)
        self.assertEqual(menu.version, 2)
        self.assertEqual(menu.slots[(0, "lunch")].state, "selected")
        self.assertEqual(menu.slots[(1, "lunch")].state, "pending")
        self.assertIsNone(menu.undo)

    def test_dish_creation_retry_preserves_token_after_database_failure(self):
        from unittest.mock import patch
        from uuid import uuid4
        from django.db import OperationalError
        from django.urls import reverse
        token = str(uuid4())
        data = {"token": token, "name": "Plat de prova", "primary": "cereals", "preference": "both"}
        with patch("menus.web.views.create_dish", side_effect=OperationalError("synthetic lock")):
            response = self.client.post(reverse("dish_create"), data)
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, token, status_code=503)
        self.assertContains(response, "Plat de prova", status_code=503)

    def test_corrupt_snapshot_blocks_post_with_unavailable_status(self):
        from unittest.mock import patch
        from django.urls import reverse
        from menus.models import MenuSlotRecord
        create_menu(self.repo, self.clock, self.week)
        change_menu(self.repo, self.clock, self.week, (0, "lunch"), 1, "assign", self.dish.pk)
        row = MenuSlotRecord.objects.get(weekly_menu_id=self.week, day_index=0, meal="lunch")
        row.dish_snapshot["schema_version"] = 999
        row.save(update_fields=["dish_snapshot"])
        url = reverse("menu_action", args=[self.week.isoformat(), 1, "lunch", "assign"])
        with patch("menus.web.views.MadridClock", return_value=self.clock):
            response = self.client.post(url, {"version": 2, "dish": self.dish.pk})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(WeeklyMenuRecord.objects.get(pk=self.week).version, 2)

    def test_shopping_get_does_not_create_overlay_state(self):
        from django.urls import reverse
        from menus.models import ShoppingStateRecord
        create_menu(self.repo, self.clock, self.week)
        url = reverse("shopping_week", args=[self.week.isoformat()])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertFalse(ShoppingStateRecord.objects.exists())
