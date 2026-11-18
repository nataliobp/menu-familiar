from contextlib import nullcontext
from unittest import TestCase

from menus.application.template import TemplateConflict, set_template_category
from menus.domain.template import POSITIONS, WeeklyTemplate


class TemplateFake:
    def __init__(self):
        self.value = WeeklyTemplate(1, {position: None for position in POSITIONS})
        self.writes = 0
    def atomic(self):
        return nullcontext()
    def get(self):
        return WeeklyTemplate(self.value.version, self.value.slots.copy())
    def categories(self):
        return {"cereals": "Cereals"}
    def save(self, value, expected_version):
        self.writes += 1
        value.version += 1
        self.value = value
    def guard(self, expected_version):
        if expected_version != self.value.version:
            raise TemplateConflict()


class TemplateApplicationTests(TestCase):
    def test_change_noop_and_stale_token(self):
        repo = TemplateFake()
        set_template_category(repo, (0, "lunch"), "cereals", 1)
        set_template_category(repo, (0, "lunch"), "cereals", 2)
        self.assertEqual(repo.writes, 1)
        with self.assertRaises(TemplateConflict):
            set_template_category(repo, (0, "lunch"), None, 1)
        self.assertEqual(repo.value.slots[(0, "lunch")], "cereals")
