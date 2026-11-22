from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from django.db import connection
from django.test import Client, TestCase as DjangoTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from menus.application.dishes import set_archived
from menus.application.planning import change_menu, move_or_undo
from menus.application.recipes import save_recipe
from menus.domain.planning import Slot
from menus.domain.recipe import recipe_content
from menus.domain.shopping import aggregate
from menus.infrastructure.django_dishes import DjangoDishRepository
from menus.infrastructure.django_planning import DjangoPlanningRepository
from menus.models import (
    CreationReceipt, DishRecord, GeneratedOverlayRecord, ManualShoppingItemRecord,
    MenuSlotRecord, ShoppingStateRecord, TemplateSlotRecord, WeeklyMenuRecord,
)


class ShoppingTests(TestCase):
    def test_conversion_repetition_coverage_and_taste(self):
        content = recipe_content("Cou", [{"name": "Arròs", "quantity": "160", "unit": "g"}, {"name": "Sal", "taste": True}], True)
        second = recipe_content("Cou", [{"name": "arròs", "quantity": "0.18", "unit": "kg"}], True)
        def selected(recipe):
            return Slot(None, "selected", {"name": "Plat", "recipe_status": "published", "recipe_content": recipe})
        rows, pending, incomplete = aggregate({(0, "lunch"): selected(content), (1, "lunch"): selected(second), (2, "lunch"): selected(content), (3, "lunch"): Slot(None)})
        self.assertEqual(rows[0]["quantity"], Decimal("500"))
        self.assertEqual(rows[1]["key"][1], "taste")
        self.assertEqual(pending, 1)
        self.assertEqual(incomplete, [])

    def test_rejects_corrupt_persisted_quantity(self):
        content = recipe_content("Cou", [{"name": "Arròs", "quantity": "1", "unit": "kg"}], True)
        content["ingredients"][0]["quantity"] = "NaN"
        slot = Slot(None, "selected", {"name": "Plat", "recipe_status": "published", "recipe_content": content})
        with self.assertRaises(ValueError):
            aggregate({(0, "lunch"): slot})

    def test_maximum_total_and_recipe_line_limit(self):
        line = {"name": "Farina", "quantity": "999999999.999", "unit": "kg"}
        content = recipe_content("Cou", [line] * 100, True)
        slots = {(day, meal): Slot(None, "selected", {"name": "Plat", "recipe_status": "published", "recipe_content": content})
                 for day in range(7) for meal in ("lunch", "dinner")}
        rows, _, _ = aggregate(slots)
        self.assertEqual(rows[0]["quantity"], Decimal("1399999999998600.000"))
        with self.assertRaises(ValueError):
            recipe_content("Cou", [line] * 101, True)

    def test_normalization_families_and_note_order(self):
        content = recipe_content("Cou", [
            {"name": "  CAFÈ  ", "quantity": "1", "unit": "g", "note": "z"},
            {"name": "cafe\u0300", "quantity": "1", "unit": "unit", "note": "a"},
            {"name": "cafè", "quantity": "2", "unit": "g", "note": "a"},
            {"name": "cafe", "taste": True},
        ], True)
        slot = Slot(None, "selected", {"name": "Plat", "recipe_status": "published", "recipe_content": content})
        rows, _, _ = aggregate({(0, "lunch"): slot})
        self.assertEqual([row["key"] for row in rows], [("cafe", "taste"), ("cafè", "g"), ("cafè", "unit")])
        self.assertEqual(rows[1]["quantity"], Decimal("3.000"))
        self.assertEqual(rows[1]["notes"], ("a", "z"))


    def test_unknown_quantities_preserve_known_subtotals_by_family(self):
        published = recipe_content("Cou", [
            {"name": "Ceba", "quantity": "1", "unit": "unit"},
            {"name": "Ceba", "quantity": "10,125", "unit": "g"},
            {"name": "Pebre", "taste": True},
        ], True)
        draft = recipe_content("", [
            {"name": "ceba", "unit": "kg"},
            {"name": "Brou", "unit": "ml"},
            {"name": "Pebre"},
            {"name": "Olives"},
        ])
        slots = {
            (1, "dinner"): Slot(None, "selected", {"name": "Segon", "recipe_status": "draft", "recipe_content": draft}),
            (0, "lunch"): Slot(None, "selected", {"name": "Primer", "recipe_status": "published", "recipe_content": published}),
        }
        rows, _, incomplete = aggregate(slots)
        values = {row["key"]: row for row in rows}
        self.assertEqual(values[("ceba", "g")]["quantity"], Decimal("10.125"))
        self.assertTrue(values[("ceba", "g")]["unknown"])
        self.assertTrue(values[("ceba", "g")]["subtotal"])
        self.assertFalse(values[("ceba", "g")]["provisional"])
        self.assertFalse(values[("ceba", "unit")]["subtotal"])
        self.assertIsNone(values[("brou", "ml")]["quantity"])
        self.assertTrue(values[("olives", "unknown")]["unknown"])
        self.assertFalse(values[("pebre", "taste")]["unknown"])
        self.assertTrue(values[("pebre", "unknown")]["unknown"])
        self.assertEqual(incomplete, [((1, "dinner"), "Segon", "draft")])

    def test_exact_volume_and_named_forms_stay_distinct_even_with_low_decimal_context(self):
        from decimal import localcontext

        first = recipe_content("Cou", [
            {"name": "Llet", "quantity": "0,001", "unit": "l"},
            {"name": "Cigrons secs", "quantity": "20", "unit": "g"},
        ], True)
        second = recipe_content("Cou", [
            {"name": "llet", "quantity": "0,019", "unit": "ml"},
            {"name": "Cigrons cuits", "quantity": "100", "unit": "g"},
        ], True)
        slots = {(n, "lunch"): Slot(None, "selected", {"name": "Plat", "recipe_status": "published", "recipe_content": content})
                 for n, content in enumerate((first, second))}
        with localcontext() as context:
            context.prec = 2
            rows, _, _ = aggregate(slots)
        self.assertEqual([(row["key"], row["quantity"]) for row in rows], [
            (("cigrons cuits", "g"), Decimal("100")), (("cigrons secs", "g"), Decimal("20")),
            (("llet", "ml"), Decimal("1.019")),
        ])


class ReminderTests(DjangoTestCase):
    def setUp(self):
        self.week = date(2026, 11, 16)
        self.clock = SimpleNamespace(today=lambda: self.week)
        self.plans = DjangoPlanningRepository()
        self.dishes = DjangoDishRepository()
        self.url = reverse("shopping_week", args=[self.week])
        clock = patch("menus.infrastructure.django_planning.MadridClock.today", return_value=self.week)
        clock.start()
        self.addCleanup(clock.stop)

    def dish(self, name):
        return DishRecord.objects.create(name=name, primary_category_id="cereals", meal_preference="both", special_occasion=False)

    def change(self, position, version, operation, dish_id=None, confirmed=False):
        return change_menu(self.plans, self.clock, self.week, position, version, operation, dish_id, confirmed).version

    def test_unplanned_empty_and_incomplete_weeks_are_read_only(self):
        response = self.client.get(self.url)
        self.assertContains(response, "No hi ha cap menú per a aquesta setmana.")
        self.assertFalse(WeeklyMenuRecord.objects.exists())
        version = self.change((0, "dinner"), 0, "skip")
        response = self.client.get(self.url)
        self.assertContains(response, "Encara no hi ha plats seleccionats per a aquesta setmana.")
        self.assertContains(response, "S’ha omès 1 àpat.")
        self.assertNotContains(response, "Receptes incompletes")
        missing = self.dish("Plat sense recepta")
        draft = self.dish("Plat en esborrany")
        save_recipe(self.dishes, self.clock, draft.pk, 1, recipe_content("", [
            {"name": "Farina", "quantity": "0,125", "unit": "kg"}, {"name": "Cigrons"},
        ]))
        version = self.change((0, "lunch"), version, "assign", missing.pk)
        self.change((1, "dinner"), version, "assign", draft.pk)
        before = list(MenuSlotRecord.objects.values())
        response = self.client.get(self.url)
        self.assertContains(response, "Receptes incompletes")
        self.assertContains(response, "Plat sense recepta")
        self.assertContains(response, "dilluns, dinar")
        self.assertContains(response, "Plat en esborrany")
        self.assertContains(response, "dimarts, sopar")
        self.assertContains(response, "Quantitats provisionals")
        self.assertContains(response, "125 g")
        self.assertContains(response, "Cigrons")
        self.assertContains(response, "Quantitat pendent")
        self.assertContains(response, "Provisional")
        self.assertNotContains(response, "<form")
        self.assertEqual(list(MenuSlotRecord.objects.values()), before)
        self.assertFalse(ShoppingStateRecord.objects.exists())

    def test_reminder_follows_replacement_skip_remove_move_and_undo(self):
        one = self.dish("Plat amb farina")
        two = self.dish("Plat amb llet")
        save_recipe(self.dishes, self.clock, one.pk, 1, recipe_content("Cou", [
            {"name": "Farina", "quantity": "12,345", "unit": "g"},
        ], True), True)
        save_recipe(self.dishes, self.clock, two.pk, 1, recipe_content("Escalfa", [
            {"name": "Llet", "quantity": "1", "unit": "l"},
        ], True), True)
        version = self.change((0, "lunch"), 0, "assign", one.pk)
        version = self.change((1, "dinner"), version, "assign", one.pk)
        self.assertContains(self.client.get(self.url), "24,69 g")
        version = self.change((1, "dinner"), version, "replace", two.pk)
        reminder = self.client.get(self.url)
        self.assertContains(reminder, "12,345 g")
        self.assertContains(reminder, "1000 ml")
        version = move_or_undo(self.plans, self.clock, self.week, version, (1, "dinner"), (5, "lunch")).version
        self.assertContains(self.client.get(self.url), "1000 ml")
        version = move_or_undo(self.plans, self.clock, self.week, version).version
        version = self.change((1, "dinner"), version, "skip", confirmed=True)
        reminder = self.client.get(self.url)
        self.assertNotContains(reminder, "Llet")
        self.assertContains(reminder, "12,345 g")
        self.change((0, "lunch"), version, "remove")
        self.assertNotContains(self.client.get(self.url), "Farina")

    def test_legacy_data_survives_blocked_requests_and_menu_and_recipe_changes(self):
        dish = self.dish("Plat de prova")
        content = recipe_content("Cou", [{"name": "Arròs", "quantity": "160", "unit": "g"}], True)
        save_recipe(self.dishes, self.clock, dish.pk, 1, content, True)
        version = self.change((0, "lunch"), 0, "assign", dish.pk)
        state = ShoppingStateRecord.objects.create(week_id=self.week, version=5)
        item = ManualShoppingItemRecord.objects.create(shopping=state, name="Producte antic", checked=True)
        GeneratedOverlayRecord.objects.create(shopping=state, ingredient_key="arròs", family="g", last_name="Arròs",
                                              last_base_quantity="160.000", adjusted_quantity="200.000", checked=True)
        token = uuid4()
        CreationReceipt.objects.create(token=token, operation="manual_add", scope=str(self.week), digest="a" * 64, result_id=item.pk)
        models = (ShoppingStateRecord, GeneratedOverlayRecord, ManualShoppingItemRecord, CreationReceipt)
        before = [model.objects.values().get() for model in models]
        response = self.client.get(self.url)
        self.assertContains(response, "160 g")
        for text in ("200 g", "Producte antic", "Ajusta la quantitat", "Comprat", "Afegeix un producte"):
            self.assertNotContains(response, text)
        client = Client(enforce_csrf_checks=True)
        edit = client.get(reverse("dish_edit", args=[dish.pk]))
        token_header = {"HTTP_X_CSRFTOKEN": edit.cookies["csrftoken"].value}
        old_paths = ("manual/add/", f"manual/{item.pk}/edit/", f"manual/{item.pk}/remove/", "adjust/",
                     "manual_add/", "manual_edit/", "manual_remove/", "manual_check/", "reset/", "check/", "checked/")
        for path in old_paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(self.url + path).status_code, 404)
                self.assertEqual(client.post(self.url + path, {"token": token}, **token_header).status_code, 404)
        for path in (self.url, reverse("current_shopping")):
            response = client.post(path, {"action": "check"}, **token_header)
            self.assertEqual(response.status_code, 405)
            self.assertEqual(response["Allow"], "GET, HEAD")
        self.change((0, "lunch"), version, "remove")
        self.change((1, "lunch"), version + 1, "assign", dish.pk)
        updated = recipe_content("Cou", [{"name": "Arròs", "quantity": "170", "unit": "g"}], True)
        save_recipe(self.dishes, self.clock, dish.pk, 2, updated, True)
        self.assertContains(self.client.get(self.url), "170 g")
        self.assertEqual([model.objects.values().get() for model in models], before)

    def test_historic_reminder_uses_frozen_snapshot_even_when_the_recipe_is_published_later(self):
        dish = self.dish("Plat de prova")
        past = self.week - timedelta(days=7)
        change_menu(self.plans, SimpleNamespace(today=lambda: past), past, (0, "lunch"), 0, "assign", dish.pk)
        self.change((0, "lunch"), 0, "assign", dish.pk)
        content = recipe_content("Cou", [{"name": "Arròs", "quantity": "160", "unit": "g"}], True)
        snapshot = MenuSlotRecord.objects.get(weekly_menu_id=past, day_index=0, meal="lunch").dish_snapshot
        save_recipe(self.dishes, self.clock, dish.pk, 1, content, True)
        historic = self.client.get(reverse("shopping_week", args=[past]))
        self.assertContains(historic, "Setmana passada · només de consulta")
        self.assertContains(historic, "Recepta històrica no disponible")
        self.assertNotContains(historic, "160 g")
        current = self.client.get(self.url)
        self.assertContains(current, "160 g")
        self.assertNotContains(current, "Receptes incompletes")
        self.assertEqual(MenuSlotRecord.objects.get(weekly_menu_id=past, day_index=0, meal="lunch").dish_snapshot, snapshot)

    def test_suggestions_skipped_slots_and_other_weeks_contribute_nothing(self):
        TemplateSlotRecord.objects.update(suggested_category_id="cereals")
        dish = self.dish("Plat de prova")
        content = recipe_content("Cou", [{"name": "Sal", "quantity": "2", "unit": "g"}], True)
        save_recipe(self.dishes, self.clock, dish.pk, 1, content, True)
        self.assertContains(self.client.get(self.url), "Encara no hi ha plats seleccionats")
        self.change((0, "dinner"), 0, "skip")
        self.assertNotContains(self.client.get(self.url), "2 g")
        future = self.week + timedelta(days=7)
        change_menu(self.plans, self.clock, future, (0, "lunch"), 0, "assign", dish.pk)
        set_archived(self.dishes, dish.pk, 2, True)
        self.assertContains(self.client.get(reverse("shopping_week", args=[future])), "2 g")
        self.assertNotContains(self.client.get(self.url), "2 g")

    def test_existing_publication_stays_effective_until_next_publication(self):
        dish = self.dish("Plat de prova")
        self.change((0, "lunch"), 0, "assign", dish.pk)
        first = recipe_content("Cou", [{"name": "Sal", "quantity": "2", "unit": "g"}], True)
        second = recipe_content("Cou", [{"name": "Sal", "quantity": "3", "unit": "g"}], True)
        save_recipe(self.dishes, self.clock, dish.pk, 1, first, True)
        save_recipe(self.dishes, self.clock, dish.pk, 2, second)
        response = self.client.get(self.url)
        self.assertContains(response, "2 g")
        self.assertNotContains(response, "Provisional")
        save_recipe(self.dishes, self.clock, dish.pk, 3, second, True)
        self.assertContains(self.client.get(self.url), "3 g")

    def test_historical_unreadable_snapshot_is_explicit_and_never_falls_back_to_live_recipe(self):
        past = self.week - timedelta(days=7)
        dish = self.dish("Plat de prova")
        change_menu(self.plans, SimpleNamespace(today=lambda: past), past, (0, "lunch"), 0, "assign", dish.pk)
        content = recipe_content("Cou", [{"name": "Sal", "quantity": "4", "unit": "g"}], True)
        save_recipe(self.dishes, self.clock, dish.pk, 1, content, True)
        slot = MenuSlotRecord.objects.get(weekly_menu_id=past, day_index=0, meal="lunch")
        slot.dish_snapshot.pop("recipe_content")
        slot.save(update_fields=["dish_snapshot"])
        response = self.client.get(reverse("shopping_week", args=[past]))
        self.assertContains(response, "No es poden recuperar les dades històriques", status_code=503)
        self.assertNotContains(response, "4 g", status_code=503)
        self.assertEqual(MenuSlotRecord.objects.get(pk=slot.pk).dish_snapshot, slot.dish_snapshot)

    def test_read_query_count_is_constant_and_never_loads_catalogue_legacy_or_template(self):
        def reads():
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            return [query["sql"] for query in queries if query["sql"].startswith("SELECT")]

        dish = self.dish("Plat de prova")
        content = recipe_content("Cou", [{"name": "Sal", "quantity": "1", "unit": "g"}], True)
        save_recipe(self.dishes, self.clock, dish.pk, 1, content, True)
        version = self.change((0, "lunch"), 0, "assign", dish.pk)
        single = reads()
        for position in sorted(self.plans.get(self.week).slots):
            if position != (0, "lunch"):
                version = self.change(position, version, "assign", dish.pk)
        self.assertEqual(reads(), single)
        self.assertEqual(len(single), 2)
        self.assertIn('FROM "menus_weeklymenurecord"', single[0])
        self.assertIn('FROM "menus_menuslotrecord"', single[1])
        self.assertContains(self.client.get(self.url), "14 g")

    def test_supermarket_sections_are_ordered_and_unknown_names_fall_back(self):
        dish = self.dish("Plat de prova")
        content = recipe_content("Cou", [
            {"name": name, "quantity": "1", "unit": "g"}
            for name in ("Pollastre vegetal de prova", "Ceba", "Pollastre", "Salmó", "Llet", "Oli d'oliva", "Sal", "Pebre")
        ], True)
        save_recipe(self.dishes, self.clock, dish.pk, 1, content, True)
        self.change((0, "lunch"), 0, "assign", dish.pk)
        response = self.client.get(self.url)
        grouped = [(name, [row["name"] for row in rows]) for name, _, rows in response.context["sections"]]
        self.assertEqual(grouped, [
            ("Fruita i verdura", ["Ceba"]), ("Carn", ["Pollastre"]), ("Peix", ["Salmó"]),
            ("Lactis i ous", ["Llet"]), ("Rebost", ["Oli d'oliva", "Pebre", "Sal"]),
            ("Altres", ["Pollastre vegetal de prova"]),
        ])
