from datetime import date
from unittest import TestCase
from menus.domain.recommendations import rank_candidates


class RecommendationTests(TestCase):
    def test_ranking_filter_and_accent_insensitive_search(self):
        def dish(id, name, preference="both", special=False):
            return {"id": id, "name": name, "categories": {"cereals"}, "meal_preference": preference, "special_occasion": special}
        dishes = [dish(1, "Cafè"), dish(2, "Cafe", "dinner"), dish(3, "CAFÈ", special=True), dish(4, "Cafè")]
        result = rank_candidates(dishes, "lunch", {1: date(2026, 1, 1)}, "cereals", "cafe")
        self.assertEqual([dish["id"] for dish in result], [4, 1, 2, 3])

    def test_all_precedence_tiers_and_tie_breaks(self):
        def dish(id, preference, special=False, categories=None):
            return {"id": id, "name": "Plat", "categories": categories or {"cereals"}, "meal_preference": preference, "special_occasion": special}
        dishes = [dish(1, "dinner"), dish(2, "lunch", True), dish(3, "both"), dish(4, "lunch"),
                  dish(5, "lunch"), dish(6, "dinner", True), dish(7, "both"), dish(8, "both", categories={"eggs", "cereals"})]
        latest = {3: date(2026, 12, 1), 4: date(2026, 11, 1), 5: date(2026, 11, 1)}
        result = rank_candidates(dishes, "lunch", latest, "cereals")
        self.assertEqual([item["id"] for item in result], [7, 8, 4, 5, 3, 1, 2, 6])
        self.assertEqual([item["id"] for item in rank_candidates(dishes, "lunch", latest, "eggs")], [8])
