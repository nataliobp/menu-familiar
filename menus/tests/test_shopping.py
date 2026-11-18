from unittest import TestCase
from decimal import Decimal
from menus.domain.planning import Slot
from menus.domain.recipe import recipe_content
from menus.domain.shopping import aggregate


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
