from datetime import date
from unittest import TestCase
from menus.domain.planning import monday


class WeekTests(TestCase):
    def test_monday_identity_across_year_and_dst_weekends(self):
        self.assertEqual(monday(date(2027, 1, 1)), date(2026, 12, 28))
        self.assertEqual(monday(date(2026, 3, 29)), date(2026, 3, 23))
        self.assertEqual(monday(date(2026, 3, 30)), date(2026, 3, 30))
        self.assertEqual(monday(date(2026, 10, 25)), date(2026, 10, 19))
