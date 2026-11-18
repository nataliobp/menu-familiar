from django.test import TestCase
from django.urls import reverse

from menus.models import TemplateSlotRecord, WeeklyTemplateRecord


class TemplateWebTests(TestCase):
    def test_seed_and_read_do_not_write(self):
        response = self.client.get(reverse("weekly_template"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lliure", count=14)
        self.assertEqual(TemplateSlotRecord.objects.count(), 14)
        self.assertEqual(WeeklyTemplateRecord.objects.get().version, 1)

    def test_set_change_clear_and_stale_guard(self):
        url = reverse("template_edit", args=[0, "lunch"])
        self.assertEqual(self.client.post(url, {"version": 1, "category": "cereals"}).status_code, 302)
        self.assertEqual(self.client.post(url, {"version": 1, "category": "eggs"}).status_code, 409)
        self.assertEqual(TemplateSlotRecord.objects.get(day_index=0, meal="lunch").suggested_category_id, "cereals")
        self.assertEqual(self.client.post(url, {"version": 2, "category": "cereals"}).status_code, 302)
        self.assertEqual(WeeklyTemplateRecord.objects.get().version, 2)
        self.assertEqual(self.client.post(url, {"version": 2, "category": "eggs"}).status_code, 302)
        self.assertEqual(self.client.post(url, {"version": 3, "category": ""}).status_code, 302)
        self.assertIsNone(TemplateSlotRecord.objects.get(day_index=0, meal="lunch").suggested_category_id)
        self.assertEqual(TemplateSlotRecord.objects.filter(suggested_category__isnull=False).count(), 0)

    def test_invalid_input_and_corrupt_template(self):
        url = reverse("template_edit", args=[0, "lunch"])
        self.assertEqual(self.client.post(url, {"version": 1, "category": "unknown"}).status_code, 400)
        TemplateSlotRecord.objects.first().delete()
        self.assertEqual(self.client.get(reverse("weekly_template")).status_code, 503)

    def test_invalid_submission_preserves_choice_and_token(self):
        url = reverse("template_edit", args=[0, "lunch"])
        response = self.client.post(url, {"version": "invalid", "category": "cereals"})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'value="invalid"', status_code=400)
        self.assertContains(response, 'value="cereals" selected', status_code=400)
        self.assertEqual(WeeklyTemplateRecord.objects.get().version, 1)
