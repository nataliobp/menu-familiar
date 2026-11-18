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
