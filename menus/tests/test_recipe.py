from unittest import TestCase
from menus.domain.recipe import recipe_content


class RecipeTests(TestCase):
    def test_draft_allows_unknown_and_normalizes_identity(self):
        recipe = recipe_content("", [{"name": "  SUCRE   MORENO ", "unit": "g", "quantity": "", "note": "", "taste": False}])
        self.assertEqual(recipe["ingredients"][0]["key"], "sucre moreno")
        self.assertIsNone(recipe["ingredients"][0]["quantity"])
        with self.assertRaises(ValueError):
            recipe_content("Preparació", [{"name": "Sucre", "quantity": "", "unit": "g"}], publish=True)

    def test_publish_exact_quantity_and_taste(self):
        recipe = recipe_content("Barreja", [{"name": "Oli", "quantity": "0,125", "unit": "l"}, {"name": "Sal", "taste": True}], publish=True)
        self.assertEqual(recipe["ingredients"][0]["quantity"], "0.125")
        with self.assertRaises(ValueError):
            recipe_content("Barreja", [{"name": "Oli", "quantity": "1.2345", "unit": "l"}], publish=True)

    def test_ingredient_label_is_not_limited_by_manual_product_name_rule(self):
        name = "Ingredient sintètic " + "llarg " * 25
        content = recipe_content("Cou", [{"name": name, "quantity": "1", "unit": "g"}], True)
        self.assertEqual(content["ingredients"][0]["name"], name.strip())
