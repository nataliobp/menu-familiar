from django.test import SimpleTestCase

from menus.domain.recommendations import rank_candidates
from menus.web.presentation import picker_groups


class PickerPresentationTests(SimpleTestCase):
    def test_only_unfiltered_view_regroups_ranked_results_within_each_tier(self):
        candidates = [
            {"id": number, "name": str(number), "primary_key": category, "primary_name": category,
             "categories": {category, "vegetables"}, "meal_preference": preference, "special_occasion": special}
            for number, category, preference, special in [
                (1, "eggs", "both", False), (2, "salads", "lunch", False), (3, "eggs", "lunch", False),
                (4, "eggs", "dinner", False), (5, "salads", "lunch", True), (6, "eggs", "dinner", True),
            ]
        ]
        ranked = rank_candidates(candidates, "lunch", {})
        groups = picker_groups(ranked, "lunch", None)
        self.assertEqual(
            [[(category, [dish["id"] for dish in members]) for category, members in tier] for _, tier in groups],
            [[(("eggs", "eggs"), [1, 3]), (("salads", "Amanides"), [2])],
             [(("eggs", "eggs"), [4])], [(("salads", "Amanides"), [5])], [(("eggs", "eggs"), [6])]],
        )
        filtered = rank_candidates(candidates, "lunch", {}, "vegetables")
        self.assertEqual(picker_groups(filtered, "lunch", "vegetables"), [("", [(None, filtered)])])
