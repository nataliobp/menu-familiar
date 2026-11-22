from copy import deepcopy
from datetime import date, timedelta
from unittest.mock import patch
from uuid import uuid4

from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse

from menus.application.planning import change_menu, move_or_undo
from menus.tests.planning_fixtures import create_legacy_menu
from menus.application.recipes import save_recipe
from menus.domain.recipe import recipe_content
from menus.infrastructure.django_dishes import DjangoDishRepository
from menus.infrastructure.django_planning import DjangoPlanningRepository
from menus.models import (
    CreationReceipt, DishRecord, GeneratedOverlayRecord, MenuSlotRecord,
    RecipeRecord, WeeklyMenuRecord,
)
from menus.tests.test_planning import Clock


class ReviewRegressions(TestCase):
    def setUp(self):
        self.week = date(2026, 11, 16)
        self.clock = Clock(self.week)
        self.repo = DjangoPlanningRepository()
        self.dish = self.make_dish("Plat sintètic")
        self.other = self.make_dish("Altre plat")
        create_legacy_menu(self.repo, self.week)
        change_menu(self.repo, self.clock, self.week, (0, "lunch"), 1, "assign", self.dish.pk)
        fake = patch("menus.infrastructure.django_planning.MadridClock.today", return_value=self.week)
        fake.start()
        self.addCleanup(fake.stop)

    def make_dish(self, name, **fields):
        return DishRecord.objects.create(name=name, primary_category_id="cereals",
                                         meal_preference="both", special_occasion=False, **fields)

    def state(self):
        return tuple(list(model.objects.order_by("pk").values()) for model in (
            DishRecord, RecipeRecord, WeeklyMenuRecord, MenuSlotRecord, GeneratedOverlayRecord,
        ))

    def url(self, name, *extra):
        return reverse(name, args=[self.week.isoformat(), *extra])

    def test_contextual_preview_and_save_reject_replaced_target(self):
        editor = self.url("slot_recipe_edit", 0, "lunch")
        self.assertContains(self.client.get(editor), self.dish.name)
        change_menu(self.repo, self.clock, self.week, (0, "lunch"), 2, "replace", self.other.pk)
        before = self.state()
        for action in ("add_row", "remove_row:0", "continue", "review_discard", "review", "draft", "publish"):
            with self.subTest(action=action):
                url = self.url(f"slot_recipe_{action}", 0, "lunch") if action in {"draft", "publish"} else editor
                response = self.client.post(url, {"dish_id": self.dish.pk, "version": 1,
                                                  "preparation": "Text de prova", "action": action})
                self.assertContains(response, "Torna al menú setmanal", status_code=409)
                self.assertContains(response, "Text de prova", status_code=409)
                self.assertNotContains(response, "<form", status_code=409)
                self.assertEqual(self.state(), before)

    def test_failed_recipe_save_retains_preview_intent_and_input(self):
        for routes in (("recipe_edit", "recipe_draft", "recipe_publish"),
                       ("slot_recipe_edit", "slot_recipe_draft", "slot_recipe_publish")):
            args = [self.week.isoformat(), 0, "lunch"] if routes[0].startswith("slot_") else [self.dish.pk]
            editor, draft, publish = (reverse(name, args=args) for name in routes)
            data = {"dish_id": self.dish.pk, "version": 1, "name": "Arròs", "quantity": "1.2.3",
                    "unit": "g", "preparation": "Text de prova", "action": "publish"}
            before = self.state()
            response = self.client.post(publish, data)
            self.assertContains(response, "1.2.3", status_code=400)
            self.assertContains(response, 'href="#ingredient-1"', status_code=400)
            self.assertContains(response, f'action="{editor}"', status_code=400)
            data.update(quantity="160", action="draft")
            with patch("menus.web.recipes.save_recipe", side_effect=OperationalError):
                response = self.client.post(draft, data)
            self.assertContains(response, f'action="{editor}"', status_code=503)
            for action in ("review_discard", "continue", "add_row", "remove_row:0"):
                with self.subTest(routes=routes, action=action):
                    self.assertEqual(self.client.post(editor, {**data, "action": action}).status_code, 200)
                    self.assertEqual(self.client.post(draft, {**data, "action": action}).status_code, 400)
                    self.assertEqual(self.state(), before)

    def test_confirm_links_keep_the_observed_menu_version(self):
        detail = self.client.get(self.url("slot_detail", 0, "lunch"))
        links = [self.url(f"confirm_{action}", 0, "lunch") + "?version=2" for action in ("remove", "skip")]
        for link in links:
            self.assertContains(detail, link)
            self.assertContains(self.client.get(link), self.dish.name)
        change_menu(self.repo, self.clock, self.week, (0, "lunch"), 2, "replace", self.other.pk)
        before = self.state()
        for link in links:
            self.assertEqual(self.client.get(link).status_code, 409)
            self.assertEqual(self.client.post(link, {"version": 2, "confirm": "yes"}).status_code, 409)
        self.assertEqual(self.state(), before)

    def test_invalid_undo_never_changes_slots_or_versions(self):
        move_or_undo(self.repo, self.clock, self.week, 2, (0, "lunch"), (1, "lunch"))
        root = WeeklyMenuRecord.objects.get(pk=self.week)
        payload = root.undo_payload
        boolean_schema = deepcopy(payload)
        boolean_schema["before"][0][1]["schema_version"] = True
        decimal_schema = deepcopy(payload)
        decimal_schema["after"][1][1]["schema_version"] = 1.0
        corruptions = (
            {**payload, "before": payload["before"][:1]},
            {**payload, "after": payload["after"][:1]},
            {**payload, "positions": payload["positions"][:1] * 2},
            {**payload, "eligible_version": 1},
            boolean_schema,
            decimal_schema,
        )
        for malformed in corruptions:
            WeeklyMenuRecord.objects.filter(pk=self.week).update(undo_payload=malformed)
            before = self.state()
            self.assertEqual(self.client.get(self.url("menu_week")).status_code, 503)
            self.assertEqual(self.client.get(self.url("shopping_week")).status_code, 503)
            self.assertEqual(self.client.post(self.url("move_action", "undo"), {"version": 3}).status_code, 503)
            self.assertEqual(self.state(), before)

    def test_menu_shopping_navigation_preserves_each_week(self):
        historic = self.week - timedelta(days=7)
        create_legacy_menu(self.repo, historic)
        for week in (historic, self.week, self.week + timedelta(days=7)):
            plan = reverse("menu_week", args=[week.isoformat()])
            shopping = reverse("shopping_week", args=[week.isoformat()])
            self.assertContains(self.client.get(plan), f'href="{shopping}"')
            self.assertContains(self.client.get(shopping), f'href="{plan}"')
        self.assertNotContains(self.client.get(reverse("shopping_week", args=[historic])), "Afegeix un producte")

    def test_catalogue_validation_sorting_metadata_and_missing_edit(self):
        listing = reverse("catalogue")
        response = self.client.get(listing)
        self.assertLess(response.content.index(b"Altre plat"), response.content.index(b"Plat sint"))
        self.assertContains(response, "Recepta pendent")
        for data in ({"archived": "invalid"}, {"category": "invalid"}, {"q": "p" * 201}):
            self.assertEqual(self.client.get(listing, data).status_code, 400)
        picker = self.url("menu_picker", 1, "lunch")
        self.assertEqual(self.client.get(picker, {"category": "invalid"}).status_code, 400)
        self.assertContains(self.client.get(picker, {"mode": "all", "category": "eggs"}), self.dish.name)
        before = self.state()
        with self.settings(DEBUG=False):
            url = reverse("dish_edit", args=[0])
            self.assertContains(self.client.get(url), "Torna al catàleg", status_code=404)
            self.assertEqual(self.client.post(url, {"name": "Plat", "primary": "cereals", "preference": "both",
                                                    "token": str(uuid4())}).status_code, 404)
        self.assertEqual(self.state(), before)
        self.assertFalse(CreationReceipt.objects.exists())

    def test_slot_recipe_and_shopping_explain_provisional_data(self):
        content = recipe_content("Barregeu-ho", [{"name": "Arròs", "quantity": "160", "unit": "g", "note": "Nota sintètica"}])
        save_recipe(DjangoDishRepository(), self.clock, self.dish.pk, 1, content)
        slot = self.client.get(self.url("slot_detail", 0, "lunch"))
        self.assertContains(slot, "Nota sintètica")
        self.assertContains(slot, "Recepta en esborrany")
        shop = self.client.get(self.url("shopping_week"))
        self.assertContains(shop, "Quantitats provisionals")
        self.assertContains(shop, "dilluns, dinar")

    def test_recipe_application_rejects_invalid_content_without_writing(self):
        repository = DjangoDishRepository()
        publication = recipe_content("Coeu-ho", [{"name": "Arròs", "quantity": "160", "unit": "g"}], True)
        save_recipe(repository, self.clock, self.dish.pk, 1, publication, True)
        before = self.state()
        draft = recipe_content("Cuina", [{"name": "Sal", "taste": True}])
        bad_note = deepcopy(draft)
        bad_note["ingredients"][0]["note"] = ["Nota"]
        for content in (
            {"preparation": "Incompleta"}, {**draft, "preparation": ["Text"]}, bad_note,
            {**draft, "schema_version": True}, {**draft, "schema_version": 1.0},
        ):
            with self.subTest(content=content):
                with self.assertRaises(ValueError):
                    save_recipe(repository, self.clock, self.dish.pk, 2, content)
                self.assertEqual(self.state(), before)

    def test_move_to_same_position_and_largest_dish_identifier(self):
        response = self.client.post(self.url("move_action", "move"), {
            "version": 2, "source_day": 0, "source_meal": "lunch",
            "destination_day": 0, "destination_meal": "lunch",
        }, follow=True)
        self.assertContains(response, "No s’ha fet cap canvi")
        self.assertNotContains(response, "Plat mogut")
        self.assertEqual(self.repo.get(self.week).version, 2)
        largest = self.make_dish("Darrer plat", id=9223372036854775807)
        self.assertEqual(self.client.post(self.url("menu_action", 1, "lunch", "assign"),
                         {"version": 2, "dish": largest.pk}).status_code, 302)
        self.assertEqual(self.repo.get(self.week).slots[1, "lunch"].dish["dish_id"], largest.pk)

    def test_conflict_review_preserves_typed_dish_and_free_template_choice(self):
        dish_url = reverse("dish_edit", args=[self.dish.pk])
        data = {"name": "Nom actual", "primary": "cereals", "preference": "both", "version": 1}
        self.assertEqual(self.client.post(dish_url, data).status_code, 302)
        data["name"] = "Nom enviat"
        self.assertContains(self.client.post(dish_url, data), data["name"], status_code=409)
        review = self.client.post(dish_url, {**data, "action": "review"})
        self.assertContains(review, 'name="version" value="2"')
        self.assertContains(review, 'value="Nom enviat"')
        self.dish.refresh_from_db()
        self.assertEqual(self.dish.name, "Nom actual")
        self.assertEqual(self.client.post(dish_url, {**data, "version": 2}).status_code, 302)

        template = reverse("template_edit", args=[0, "lunch"])
        self.assertEqual(self.client.post(template, {"category": "eggs", "version": 1}).status_code, 302)
        data = {"category": "", "version": 1}
        self.assertContains(self.client.post(template, data), "La teva selecció: Lliure", status_code=409)
        review = self.client.post(template, {**data, "action": "review"})
        self.assertContains(review, 'name="version" value="2"')
        self.assertContains(review, "Categoria actual: Ous")
        self.assertEqual(self.client.post(template, {**data, "version": 2}).status_code, 302)

    def test_first_assignment_reports_success_and_identifies_active_destination(self):
        future = (self.week + timedelta(days=7)).isoformat()
        response = self.client.post(reverse("menu_action", args=[future, 0, "lunch", "assign"]),
                                    {"version": 0, "dish": self.dish.pk}, follow=True)
        self.assertContains(response, "Canvi desat")
        self.assertContains(response, 'aria-current="page"')

    def test_recipe_read_failure_keeps_input_and_retry_cannot_save_or_rebase(self):
        for contextual in (False, True):
            with self.subTest(contextual=contextual):
                if contextual:
                    editor = self.url("slot_recipe_edit", 0, "lunch")
                    publish = self.url("slot_recipe_publish", 0, "lunch")
                else:
                    editor = reverse("recipe_edit", args=[self.dish.pk])
                    publish = reverse("recipe_publish", args=[self.dish.pk])
                data = {"dish_id": self.dish.pk, "version": 1, "preparation": "Text per conservar",
                        "name": ["Arròs", "Sal"], "quantity": ["160,5", ""], "unit": ["g", ""],
                        "note": ["Nota", ""], "taste": ["1"], "action": "publish"}
                before = self.state()
                with patch("menus.web.recipes.get_dish", side_effect=OperationalError("synthetic")):
                    failed = self.client.post(publish, data)
                self.assertContains(failed, "Text per conservar", status_code=503)
                self.assertContains(failed, f'action="{editor}"', status_code=503)
                self.assertContains(failed, 'value="160,5"', status_code=503)
                self.assertNotContains(failed, "Publica la recepta", status_code=503)
                retried = self.client.post(editor, {**data, "action": "retry_read"})
                self.assertContains(retried, "Text per conservar")
                self.assertContains(retried, 'name="version" value="1"')
                self.assertEqual(self.state(), before)

        save_recipe(DjangoDishRepository(), self.clock, self.dish.pk, 1,
                    recipe_content("Recepta nova", [{"name": "Sal", "taste": True}]))
        before = self.state()
        retried = self.client.post(editor, {**data, "action": "retry_read"})
        self.assertContains(retried, "Revisa la recepta actual", status_code=409)
        self.assertContains(retried, 'name="version" value="1"', status_code=409)
        self.assertEqual(self.state(), before)

    def test_recipe_conflict_compares_current_taste_and_unknown_quantity(self):
        draft = recipe_content("Cuina", [{"name": "Sal", "taste": True}, {"name": "Farina", "unit": "g"}])
        save_recipe(DjangoDishRepository(), self.clock, self.dish.pk, 1, draft)
        data = {"version": 1, "preparation": "Cuina", "name": "Sal"}
        url = reverse("recipe_draft", args=[self.dish.pk])
        response = self.client.post(url, data)
        self.assertContains(response, "Sal · Al gust", status_code=409)
        self.assertContains(response, "Farina · Quantitat pendent g", status_code=409)

    def test_recipe_validation_links_preparation_and_ingredient_count_errors(self):
        publish = reverse("recipe_publish", args=[self.dish.pk])
        before = self.state()
        response = self.client.post(publish, {"version": 1, "name": ["Sal"] * 101})
        self.assertContains(response, 'href="#preparation"', status_code=400)
        self.assertContains(response, 'aria-describedby="preparation-error"', status_code=400)
        self.assertContains(response, 'href="#ingredients-error"', status_code=400)
        self.assertContains(response, 'id="ingredients-error"', status_code=400)
        self.assertEqual(self.state(), before)

    def test_dish_read_failure_retains_fields_and_retry_is_read_only(self):
        editor = reverse("dish_edit", args=[self.dish.pk])
        data = {"name": "Nom per conservar", "primary": "eggs", "secondary": ["cereals", "vegetables"],
                "preference": "dinner", "version": 1, "special": "on"}
        before = self.state()
        with patch("menus.web.catalogue.get_dish", side_effect=OperationalError("synthetic")):
            failed = self.client.post(editor, data)
        self.assertContains(failed, 'value="Nom per conservar"', status_code=503)
        self.assertContains(failed, 'name="secondary" value="vegetables"', status_code=503)
        self.assertContains(failed, 'value="retry_read"', status_code=503)
        retried = self.client.post(editor, {**data, "action": "retry_read"})
        self.assertContains(retried, 'value="Nom per conservar"')
        self.assertContains(retried, 'value="cereals" checked')
        self.assertContains(retried, 'value="vegetables" checked')
        self.assertEqual(self.state(), before)

    def test_changed_dish_receipt_can_be_reviewed_without_writing(self):
        url = reverse("dish_create")
        data = {"name": "Primer plat", "primary": "cereals", "preference": "both", "token": str(uuid4())}
        self.assertEqual(self.client.post(url, data).status_code, 302)
        changed = {**data, "name": "Segon plat"}
        self.assertContains(self.client.post(url, changed), "Segon plat", status_code=409)
        reviewed = self.client.post(url, {**changed, "action": "review"})
        self.assertContains(reviewed, "Crea un plat nou")
        self.assertFalse(DishRecord.objects.filter(name="Segon plat").exists())
        new_token = reviewed.context["values"]["token"]
        self.assertNotEqual(new_token, data["token"])
        confirmed = self.client.post(url, {**changed, "token": new_token})
        self.assertEqual(confirmed.status_code, 302)
        self.assertEqual(DishRecord.objects.filter(name="Segon plat").count(), 1)
