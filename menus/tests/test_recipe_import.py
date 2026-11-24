from datetime import date, timedelta
import json
from unittest.mock import patch
from uuid import uuid4

from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse

from menus.application.dishes import create_dish
from menus.application.planning import change_menu
from menus.application.recipes import save_recipe
from menus.domain.dish_edit import DishInput
from menus.domain.recipe import recipe_content
from menus.infrastructure.django_dishes import DjangoDishRepository
from menus.infrastructure.django_planning import DjangoPlanningRepository
from menus.models import CreationReceipt, DishRecord, RecipeRecord
from menus.tests.test_planning import Clock


class RecipeImportTests(TestCase):
    def setUp(self):
        self.new = reverse("new_recipe_import")
        self.sample = self.client.get(self.new).context["prompt"].split("Exemple complet:\n", 1)[1]

    def dish(self, name="Plat de prova"):
        return create_dish(DjangoDishRepository(), DishInput(name, "pasta", frozenset({"fish"}), "both", False), uuid4())

    def preview(self, url, raw=None):
        return self.client.post(url, {"action": "preview", "recipe_json": self.sample if raw is None else raw})

    def save(self, url, preview, **extra):
        return self.client.post(url, {
            "action": "save", "recipe_json": preview.context["raw"],
            "preview_token": preview.context["preview_token"], **extra,
        })

    def test_prompt_example_previews_saves_and_reopens_in_manual_editor(self):
        self.assertContains(self.client.get(reverse("dish_create")), self.new)
        prompt = self.client.get(self.new).context["prompt"]
        self.assertIn("2 adults en català normatiu", prompt)
        self.assertIn("sense blocs Markdown ni cap text addicional", prompt)
        response = self.preview(self.new)
        self.assertContains(response, "Previsualització · Truita de carbassó")
        for detail in ("Ous", "Verdures", "300 g", "A rodanxes fines", "Al gust", "Salta el carbassó"):
            self.assertContains(response, detail)
        self.assertFalse(DishRecord.objects.exists())

        # Browsers submit textarea newlines as CRLF.
        saved = self.save(self.new, response, recipe_json=self.sample.replace("\n", "\r\n"))
        dish = DishRecord.objects.get()
        editor = reverse("recipe_edit", args=[dish.id])
        self.assertRedirects(saved, editor)
        self.assertEqual(dish.name, "Truita de carbassó")
        self.assertEqual(dish.primary_category_id, "eggs")
        self.assertEqual(list(dish.secondary_categories.values_list("category_id", flat=True)), ["vegetables"])
        recipe = RecipeRecord.objects.get(dish=dish)
        self.assertIsNone(recipe.published)
        self.assertEqual(recipe.draft["ingredients"][1]["quantity"], "300.000")
        self.assertContains(self.client.get(editor), "Carbassó")
        self.assertContains(self.client.get(editor), reverse("recipe_import", args=[dish.id]))

        publish = self.client.post(reverse("recipe_publish", args=[dish.id]), {
            "action": "publish", "version": dish.version, "preparation": "Cou la truita.",
            "name": ["Ous"], "quantity": ["4"], "unit": ["unit"], "note": [""],
        })
        self.assertRedirects(publish, reverse("dish_detail", args=[dish.id]))
        self.assertRedirects(self.save(self.new, response), editor)
        recipe.refresh_from_db()
        self.assertIsNone(recipe.draft)
        self.assertEqual(recipe.published["preparation"], "Cou la truita.")
        self.assertEqual(DishRecord.objects.count(), 1)

    def test_invalid_json_preserves_including_leading_newlines(self):
        for raw, expected in (
            ('\n```json\n{"name":"Plat"}\n```', "línia 2, columna 1"),
            ('{"name":"Plat","name":"Altre"}', "apareix més d’una vegada"),
            ('{"name":"\\ud800"}', "valors que no es poden llegir"),
            ('{"name":"<script>prova</script>"}', "Afegeix els camps obligatoris"),
        ):
            with self.subTest(raw=raw):
                response = self.preview(self.new, raw)
                self.assertContains(response, expected, status_code=400)
                self.assertEqual(response.context["raw"], raw)
                self.assertNotContains(response, "<script>prova</script>", status_code=400)
        self.assertFalse(DishRecord.objects.exists())

    def test_schema_rejects_invalid_fields_with_actionable_errors(self):
        for changes, error in (
            ({"primary_category": "unknown"}, "Tria a «primary_category»"),
            ({"secondary_categories": ["eggs"]}, "la categoria principal i els codis duplicats"),
            ({"secondary_categories": ["fish", "fish"]}, "la categoria principal i els codis duplicats"),
            ({"secondary_categories": ["pizza"]}, "La categoria Pizza"),
            ({"primary_category": "pizza"}, "La categoria Pizza"),
            ({"secondary_categories": [1]}, "una llista de codis de categoria vàlids"),
            ({"servings": True}, "Posa el nombre 2"),
            ({"preparation": " "}, "la preparació completa"),
            ({"ingredients": []}, "una llista d’entre"),
            ({"id": 100}, "Elimina els camps no admesos: id"),
        ):
            with self.subTest(changes=changes):
                response = self.preview(self.new, json.dumps({**json.loads(self.sample), **changes}))
                self.assertContains(response, error, status_code=400)
        for changes, error in (
            ({"unit": "tassa"}, "Tria a «unit»"),
            ({"quantity": 12}, "una quantitat positiva entre cometes"),
            ({"quantity": "1.2345"}, "una quantitat positiva entre cometes"),
            ({"quantity": "0"}, "una quantitat positiva entre cometes"),
            ({"quantity": "1000000000"}, "una quantitat positiva entre cometes"),
            ({"quantity": None}, "una quantitat positiva entre cometes"),
            ({"taste": True}, "posa null a «quantity» i «unit»"),
            ({"taste": "false"}, "Posa true o false"),
        ):
            with self.subTest(changes=changes):
                data = json.loads(self.sample)
                data["ingredients"][0].update(changes)
                self.assertContains(self.preview(self.new, json.dumps(data)), error, status_code=400)
        data = json.loads(self.sample)
        del data["ingredients"][0]["unit"]
        self.assertContains(self.preview(self.new, json.dumps(data)), "Afegeix els camps obligatoris: unit", status_code=400)

    def test_new_pizza_can_be_imported_with_no_secondary_categories(self):
        data = {**json.loads(self.sample), "name": "Pizza de prova", "primary_category": "pizza",
                "secondary_categories": []}
        self.assertEqual(self.save(self.new, self.preview(self.new, json.dumps(data))).status_code, 302)
        dish = DishRecord.objects.get()
        self.assertEqual(dish.primary_category_id, "pizza")
        self.assertFalse(dish.secondary_categories.exists())

    def test_selected_dish_is_authoritative_and_missing_recipe_needs_no_confirmation(self):
        dish_id = self.dish()
        url = reverse("recipe_import", args=[dish_id])
        response = self.preview(url)
        self.assertContains(response, "Previsualització · Plat de prova")
        self.assertContains(response, "· Pasta")
        self.assertContains(response, "· Peix")
        self.assertNotContains(response, "Previsualització · Truita de carbassó")
        self.assertNotContains(response, "confirm_replace")
        self.assertRedirects(self.save(url, response), reverse("recipe_edit", args=[dish_id]))
        self.assertEqual(DishRecord.objects.count(), 1)
        dish = DishRecord.objects.get(pk=dish_id)
        self.assertEqual((dish.name, dish.primary_category_id), ("Plat de prova", "pasta"))
        self.assertEqual(list(dish.secondary_categories.values_list("category_id", flat=True)), ["fish"])
        self.assertIsNotNone(RecipeRecord.objects.get(dish_id=dish_id).draft)

    def test_confirmation_preserves_each_revision_until_explicit_save(self):
        dish_id = self.dish()
        repo, clock = DjangoDishRepository(), Clock(date(2026, 11, 23))
        published = recipe_content("Recepta publicada de prova.", [{"name": "Sal", "taste": True}], True)
        draft = recipe_content("Esborrany de prova.", [])
        save_recipe(repo, clock, dish_id, 1, published, publish=True)
        save_recipe(repo, clock, dish_id, 2, draft)
        url = reverse("recipe_import", args=[dish_id])
        preview = self.preview(url)
        self.assertContains(preview, 'name="confirm_replace"')
        rejected = self.save(url, preview)
        self.assertContains(rejected, "Confirma que vols substituir", status_code=400)
        self.assertEqual(rejected.context["raw"], self.sample)
        recipe = RecipeRecord.objects.get(dish_id=dish_id)
        self.assertEqual((recipe.draft, recipe.published), (draft, published))
        self.assertEqual(self.save(url, rejected, confirm_replace="yes").status_code, 302)
        recipe.refresh_from_db()
        self.assertEqual(recipe.published, published)
        self.assertNotEqual(recipe.draft, draft)

    def test_save_requires_preview_and_rejects_changes_after_preview(self):
        response = self.client.post(self.new, {"action": "save", "recipe_json": self.sample})
        self.assertContains(response, "Fes una previsualització", status_code=400)
        preview = self.preview(self.new)
        edited = self.sample.replace("Truita de carbassó", "Plat canviat")
        response = self.save(self.new, preview, recipe_json=edited)
        self.assertContains(response, "Torna a previsualitzar", status_code=409)
        self.assertEqual(response.context["raw"], edited)
        self.assertFalse(DishRecord.objects.exists())

        dish_id = self.dish()
        url = reverse("recipe_import", args=[dish_id])
        preview = self.preview(url)
        draft = recipe_content("Canvi fet després de previsualitzar.", [])
        save_recipe(DjangoDishRepository(), Clock(date(2026, 11, 23)), dish_id, 1, draft)
        self.assertContains(self.save(url, preview, confirm_replace="yes"), "Torna a previsualitzar", status_code=409)
        self.assertEqual(RecipeRecord.objects.get(dish_id=dish_id).draft, draft)

    def test_database_error_rolls_back_creation_and_preserves_pasted_text_for_retry(self):
        preview = self.preview(self.new)
        with patch.object(DjangoDishRepository, "save_recipe", side_effect=DatabaseError):
            response = self.save(self.new, preview)
        self.assertContains(response, "No s’ha pogut completar", status_code=503)
        self.assertEqual(response.context["raw"], self.sample)
        self.assertFalse(DishRecord.objects.exists())
        self.assertFalse(RecipeRecord.objects.exists())
        self.assertFalse(CreationReceipt.objects.exists())
        self.assertEqual(self.save(self.new, response).status_code, 302)

    def test_slot_import_keeps_historical_snapshots_and_context(self):
        dish_id = self.dish()
        plans = DjangoPlanningRepository()
        current = date(2026, 11, 23)
        past, future = current - timedelta(weeks=1), current + timedelta(weeks=1)
        for week in (past, current, future):
            change_menu(plans, Clock(past), week, (0, "lunch"), 0, "assign", dish_id)
        past_menu = plans.get(past)
        args = [current.isoformat(), 0, "lunch"]
        url = reverse("slot_recipe_import", args=args)
        editor = reverse("slot_recipe_edit", args=args)
        with patch("menus.web.recipes.MadridClock", return_value=Clock(current)), patch(
            "menus.web.recipe_import.MadridClock", return_value=Clock(current),
        ):
            self.assertContains(self.client.get(editor), url)
            self.assertRedirects(self.save(url, self.preview(url)), editor)
            past_url = reverse("slot_recipe_import", args=[past.isoformat(), 0, "lunch"])
            response = self.preview(past_url)
            self.assertContains(response, "Aquesta setmana és només de consulta", status_code=403)
            self.assertEqual(response.context["raw"], self.sample)
        self.assertEqual(plans.get(past), past_menu)
        draft = RecipeRecord.objects.get(dish_id=dish_id).draft
        for week in (current, future):
            self.assertEqual(plans.get(week).slots[(0, "lunch")].dish["recipe_content"], draft)

    def test_slot_import_rejects_a_different_dish_after_preview(self):
        dish_id, other_id = self.dish(), self.dish("Altre plat")
        current = date(2026, 11, 23)
        plans, clock = DjangoPlanningRepository(), Clock(current)
        change_menu(plans, clock, current, (0, "lunch"), 0, "assign", dish_id)
        url = reverse("slot_recipe_import", args=[current.isoformat(), 0, "lunch"])
        with patch("menus.web.recipes.MadridClock", return_value=clock):
            preview = self.preview(url)
            change_menu(plans, clock, current, (0, "lunch"), plans.get(current).version, "replace", other_id)
            response = self.save(url, preview)
        self.assertContains(response, "Torna a previsualitzar", status_code=409)
        self.assertEqual(response.context["raw"], self.sample)
        self.assertFalse(RecipeRecord.objects.exists())
