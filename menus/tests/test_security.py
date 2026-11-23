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


TAILSCALE_HOST = "homeserver.tail02b38e.ts.net"
TAILSCALE_AUTHORITY = f"{TAILSCALE_HOST}:8443"
TAILSCALE_ORIGIN = f"https://{TAILSCALE_AUTHORITY}"
LAN_AUTHORITY = "192.168.1.22:18766"
GATEWAY = "172.24.0.1"


@override_settings(
    ALLOWED_HOSTS=["192.168.1.22", TAILSCALE_HOST],
    TAILSCALE_HOST=TAILSCALE_HOST,
    TAILSCALE_PROXY_IP=GATEWAY,
)
class ProxySecurityTests(TestCase):
    def proxy_client(self, **overrides):
        meta = {
            "REMOTE_ADDR": GATEWAY, "HTTP_HOST": TAILSCALE_AUTHORITY,
            "HTTP_X_FORWARDED_HOST": TAILSCALE_AUTHORITY, "HTTP_X_FORWARDED_PROTO": "https",
        }
        return Client(enforce_csrf_checks=True, **(meta | overrides))

    def test_proxy_listener_checks_peer_and_exact_headers(self):
        health = reverse("healthz")
        self.assertEqual(self.proxy_client().get(health, SERVER_PORT="8001").status_code, 200)
        for meta in (
            {"REMOTE_ADDR": "192.168.1.55", "HTTP_X_FORWARDED_FOR": GATEWAY},
            {"HTTP_HOST": "untrusted.invalid:8443"},
            {"HTTP_X_FORWARDED_HOST": "untrusted.invalid:8443"},
            {"HTTP_HOST": TAILSCALE_HOST},
            {"HTTP_X_FORWARDED_PROTO": "https,http"},
            {"HTTP_X_FORWARDED_PROTO": "http"},
            {"HTTP_TAILSCALE_FUNNEL_REQUEST": "?1"},
        ):
            with self.subTest(meta=meta):
                self.assertEqual(self.proxy_client(**meta).get(health, SERVER_PORT="8001").status_code, 403)
        with override_settings(TAILSCALE_PROXY_IP=""):
            self.assertEqual(self.proxy_client().get(health, SERVER_PORT="8001").status_code, 403)

    def test_proxy_preserves_django_https_origin_and_referer_checks(self):
        client = self.proxy_client()
        edit_url = reverse("template_edit", args=[0, "lunch"])
        port = {"SERVER_PORT": "8001"}
        self.assertTrue(client.get(edit_url, **port).wsgi_request.is_secure())
        self.assertTrue(client.cookies["csrftoken"]["secure"])
        data = {"version": 1, "category": "cereals", "csrfmiddlewaretoken": client.cookies["csrftoken"].value}
        self.assertEqual(client.post(edit_url, data, **port).status_code, 403)
        self.assertEqual(client.post(edit_url, data, HTTP_ORIGIN=f"http://{LAN_AUTHORITY}", **port).status_code, 403)
        self.assertEqual(client.post(edit_url, data, HTTP_ORIGIN=f"https://{TAILSCALE_HOST}", **port).status_code, 403)
        self.assertEqual(client.post(edit_url, data, HTTP_REFERER=f"{TAILSCALE_ORIGIN}{edit_url}", **port).status_code, 302)
        data["version"] = 2
        self.assertEqual(client.post(edit_url, data, HTTP_ORIGIN=TAILSCALE_ORIGIN, **port).status_code, 302)

    def test_lan_ignores_spoofed_forwarded_headers_even_from_the_gateway(self):
        client = self.proxy_client(HTTP_HOST=LAN_AUTHORITY,
                                   HTTP_FORWARDED=f"proto=https;host={TAILSCALE_AUTHORITY}")
        edit_url = reverse("template_edit", args=[0, "lunch"])
        port = {"SERVER_PORT": "8000"}
        response = client.get(edit_url, **port)
        self.assertFalse(response.wsgi_request.is_secure())
        self.assertEqual(response.wsgi_request.get_host(), LAN_AUTHORITY)
        self.assertFalse(client.cookies["csrftoken"]["secure"])
        data = {"version": 1, "category": "cereals", "csrfmiddlewaretoken": client.cookies["csrftoken"].value}
        self.assertEqual(client.post(edit_url, data, HTTP_ORIGIN=TAILSCALE_ORIGIN, **port).status_code, 403)
        self.assertEqual(client.post(edit_url, data, HTTP_ORIGIN=f"http://{LAN_AUTHORITY}", **port).status_code, 302)
