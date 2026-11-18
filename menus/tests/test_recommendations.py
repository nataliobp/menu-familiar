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
