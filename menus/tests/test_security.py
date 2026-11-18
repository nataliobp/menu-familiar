from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(ALLOWED_HOSTS=["localhost"])
class SecurityTests(TestCase):
    def test_csrf_and_host_enforced(self):
        client = Client(enforce_csrf_checks=True, HTTP_HOST="localhost")
        self.assertEqual(client.post(reverse("template_edit", args=[0, "lunch"]), {"version": 1, "category": "cereals"}).status_code, 403)
        self.assertEqual(client.get(reverse("weekly_template"), HTTP_HOST="untrusted.invalid").status_code, 400)

    def test_health_does_not_expose_data(self):
        response = self.client.get(reverse("healthz"), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"OK")
