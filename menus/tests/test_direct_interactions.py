from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

from django.contrib.staticfiles import finders
from django.db import DatabaseError
from django.test import Client, TestCase
from django.urls import reverse

from menus.application.planning import change_menu
from menus.tests.planning_fixtures import create_legacy_menu
from menus.domain.categories import CATEGORIES
from menus.infrastructure.django_planning import DjangoPlanningRepository
from menus.models import DishRecord, MenuSlotRecord, TemplateSlotRecord, WeeklyMenuRecord
from menus.web.presentation import category_art


class DirectInteractionTests(TestCase):
    def setUp(self):
        self.week = date(2026, 11, 16)
        self.clock = patch("menus.infrastructure.django_planning.MadridClock.today", return_value=self.week)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.chicken = DishRecord.objects.create(name="Pollastre al curri", primary_category_id="chicken",
                                                meal_preference="both", special_occasion=False)
        self.legumes = DishRecord.objects.create(name="Cigrons de prova", primary_category_id="legumes",
                                                meal_preference="both", special_occasion=False)
        self.repo = DjangoPlanningRepository()

    def url(self, route, *args, week=None):
        return reverse(route, args=[(week or self.week).isoformat(), *args])

    def template(self, key, version):
        response = self.client.post(reverse("template_edit", args=[1, "dinner"]), {
            "category": key, "version": version,
        }, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        return response.json()["version"]

    def test_virtual_reads_invalid_edit_and_first_success(self):
        menu = self.url("menu_week")
        picker = self.url("menu_picker", 1, "dinner")
        assignment = self.url("menu_action", 1, "dinner", "assign")
        self.template("legumes", 1)
        self.assertContains(self.client.get(menu), 'class="slot pending"', count=14)
        self.assertContains(self.client.get(menu), "Suggeriment de la plantilla: Llegums.")
        self.assertContains(self.client.get(picker), "Cigrons de prova")
        self.assertNotContains(self.client.get(picker), "Pollastre al curri")
        self.assertContains(self.client.get(picker, {"category": "", "q": "POLLÁSTRE"}), "Pollastre al curri")
        self.assertFalse(WeeklyMenuRecord.objects.exists())
        self.assertEqual(self.client.post(assignment, {"version": 0, "dish": 999}).status_code, 400)
        original_save = DjangoPlanningRepository.save

        def fail_after_save(repo, menu, version):
            original_save(repo, menu, version)
            raise DatabaseError("synthetic failure after persisting the menu")

        with patch.object(DjangoPlanningRepository, "save", fail_after_save):
            self.assertEqual(self.client.post(assignment, {"version": 0, "dish": self.chicken.pk}).status_code, 503)
        self.assertFalse(WeeklyMenuRecord.objects.exists())
        self.assertFalse(MenuSlotRecord.objects.exists())
        data = {"version": 0, "dish": self.chicken.pk, "from_picker": "yes", "category": "", "q": "POLLÁSTRE"}
        self.assertEqual(Client(enforce_csrf_checks=True).post(assignment, data).status_code, 403)
        response = self.client.post(assignment, data, HTTP_ACCEPT="application/json")
        self.assertEqual(response.json(), {"location": menu})
        self.assertContains(self.client.get(menu), "Pollastre al curri")
        conflict = self.client.post(assignment, data)
        self.assertContains(conflict, "action=replace", status_code=409)
        self.assertContains(conflict, "POLL%C3%81STRE", status_code=409)
        self.assertEqual(WeeklyMenuRecord.objects.get().version, 2)
        self.assertEqual(MenuSlotRecord.objects.filter(state="selected").count(), 1)
        self.assertFalse(MenuSlotRecord.objects.filter(suggested_category_key__isnull=False).exists())

    def test_current_template_applies_to_legacy_rows_and_after_removal(self):
        legacy_clock = type("Clock", (), {"today": lambda _: self.week - timedelta(days=7)})()
        previous = legacy_clock.today()
        TemplateSlotRecord.objects.filter(day_index=1, meal="dinner").update(suggested_category_id="pork")
        create_legacy_menu(self.repo, previous)
        change_menu(self.repo, legacy_clock, previous, (0, "lunch"), 1, "assign", self.chicken.pk)
        create_legacy_menu(self.repo, self.week)
        future = self.week + timedelta(days=7)
        TemplateSlotRecord.objects.filter(day_index=1, meal="dinner").update(suggested_category_id=None)
        create_legacy_menu(self.repo, future)
        menu = self.url("menu_week")
        picker = self.url("menu_picker", 1, "dinner")
        rows_before = list(MenuSlotRecord.objects.order_by("pk").values())
        roots_before = list(WeeklyMenuRecord.objects.order_by("pk").values())
        version = self.template("legumes", 1)
        self.assertContains(self.client.get(menu), "Suggeriment de la plantilla: Llegums.")
        self.assertContains(self.client.get(self.url("menu_week", week=future)), "Suggeriment de la plantilla: Llegums.")
        self.assertContains(self.client.get(picker), "Cigrons de prova")
        version = self.template("fish", version)
        self.assertContains(self.client.get(menu), "Suggeriment de la plantilla: Peix.")
        self.assertNotContains(self.client.get(picker), "Cigrons de prova")
        self.assertNotContains(self.client.get(self.url("menu_week", week=previous)), "slot-suggestion")
        self.assertContains(self.client.get(self.url("menu_week", week=previous)), "Pollastre al curri")
        version = self.template("", version)
        self.assertNotContains(self.client.get(menu), "slot-suggestion")
        self.assertContains(self.client.get(picker), "Pollastre al curri")
        self.assertEqual(list(MenuSlotRecord.objects.order_by("pk").values()), rows_before)
        self.assertEqual(list(WeeklyMenuRecord.objects.order_by("pk").values()), roots_before)
        change_menu(self.repo, legacy_clock, self.week, (1, "dinner"), 1, "assign", self.chicken.pk)
        self.template("legumes", version)
        self.assertNotContains(self.client.get(menu), "slot-suggestion")
        self.assertContains(self.client.get(picker, {"action": "replace"}), "Cigrons de prova")
        remove = self.url("confirm_remove", 1, "dinner")
        self.assertEqual(self.client.post(remove, {"version": 2, "confirm": "yes"}).status_code, 302)
        self.assertContains(self.client.get(menu), "Suggeriment de la plantilla: Llegums.")

    def test_first_skip_and_historical_missing_week(self):
        self.template("legumes", 1)
        previous = self.week - timedelta(days=7)
        self.assertNotContains(self.client.get(self.url("menu_week", week=previous)), "slot-suggestion")
        self.assertEqual(self.client.get(self.url("menu_picker", 1, "dinner", week=previous)).status_code, 404)
        self.assertEqual(self.client.post(self.url("confirm_skip", 1, "dinner", week=previous), {"version": 0}).status_code, 403)
        self.assertFalse(WeeklyMenuRecord.objects.exists())
        self.assertEqual(self.client.post(self.url("confirm_skip", 1, "dinner"), {"version": 0}).status_code, 302)
        self.assertNotContains(self.client.get(self.url("menu_week")), "slot-suggestion")
        assignment = self.url("menu_action", 1, "dinner", "assign")
        self.assertEqual(self.client.post(assignment, {"version": 2, "dish": self.legumes.pk}).status_code, 400)
        self.assertEqual(self.client.post(self.url("menu_action", 1, "dinner", "reactivate"), {"version": 2}).status_code, 302)
        self.assertContains(self.client.get(self.url("menu_week")), "Suggeriment de la plantilla: Llegums.")

    def test_local_multicolour_category_assets_and_labels(self):
        for key, label in (*CATEGORIES, ("", "Lliure")):
            with self.subTest(category=key):
                asset = category_art(key)
                self.assertEqual(asset, f"menus/category-icons/{key or 'free'}.svg")
                source = Path(finders.find(asset)).read_text()
                root = ElementTree.fromstring(source)
                self.assertEqual(root[0].text, label)
                self.assertGreaterEqual(len({element.get("fill") for element in root.iter()
                                             if element.get("fill", "").startswith("#")}), 2 if key else 1)
                self.assertGreaterEqual(len({element.get(attribute) for element in root.iter()
                                             for attribute in ("fill", "stroke")
                                             if element.get(attribute, "").startswith("#")}), 2)
                self.assertNotRegex(source, r"currentColor|<script|<image|href=|url\(")
        page = self.client.get(reverse("weekly_template"))
        self.assertContains(page, '/static/menus/category-icons/pork.svg')
        self.assertContains(page, "Amanides")
        self.assertContains(page, '/static/menus/icons.svg#grid')
