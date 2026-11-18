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

    def test_maximum_total_and_override_boundaries(self):
        from menus.domain.recipe import parse_amount
        line = {"name": "Farina", "quantity": "999999999.999", "unit": "kg"}
        content = recipe_content("Cou", [line] * 100, True)
        slots = {(day, meal): Slot(None, "selected", {"name": "Plat", "recipe_status": "published", "recipe_content": content})
                 for day in range(7) for meal in ("lunch", "dinner")}
        rows, _, _ = aggregate(slots)
        self.assertEqual(rows[0]["quantity"], Decimal("1399999999998600.000"))
        self.assertEqual(parse_amount("1399999999998600.000", Decimal("1399999999998600.000")), "1399999999998600.000")
        with self.assertRaises(ValueError):
            parse_amount("1399999999998600.001", Decimal("1399999999998600.000"))
        with self.assertRaises(ValueError):
            recipe_content("Cou", [line] * 101, True)
