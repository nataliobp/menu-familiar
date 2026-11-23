from struct import unpack
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(ALLOWED_HOSTS=["localhost"])
class PwaTests(TestCase):
    def test_start_url_and_primary_navigation_share_the_manifest(self):
        browser = Client(HTTP_HOST="localhost")
        manifest_url = reverse("web_app_manifest")
        response = browser.get(manifest_url)
        self.assertEqual(response.headers["Content-Type"], "application/manifest+json")
        manifest = response.json()
        self.assertEqual(manifest["id"], "/")
        self.assertEqual(manifest["name"], "Menú Familiar")
        self.assertEqual(manifest["lang"], "ca")
        self.assertEqual(manifest["start_url"], "/menu/")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["theme_color"], "#286044")
        self.assertEqual(manifest["background_color"], "#f7f7ef")
        self.assertEqual(browser.head(manifest_url).status_code, 200)
        self.assertEqual(browser.post(manifest_url).status_code, 405)

        for url in (manifest["start_url"], "/plantilla/", "/plats/", "/compra/"):
            with self.subTest(url=url):
                page = browser.get(url, follow=True)
                self.assertContains(page, f'<link rel="manifest" href="{manifest_url}">')
                self.assertIn("no-store", page.headers["Cache-Control"])
                self.assertIn("private", page.headers["Cache-Control"])
                self.assertTrue(page.request["PATH_INFO"].startswith(manifest["scope"]))

    def test_production_static_collection_and_icon_delivery(self):
        storages = {
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
        }
        with TemporaryDirectory() as static_root, override_settings(
            DEBUG=False, STATIC_ROOT=static_root, STORAGES=storages, WHITENOISE_USE_FINDERS=False
        ):
            call_command("collectstatic", interactive=False, verbosity=0)
            browser = Client(HTTP_HOST="localhost")
            icons = browser.get(reverse("web_app_manifest")).json()["icons"]
            self.assertEqual({icon["sizes"] for icon in icons}, {"192x192", "512x512"})
            self.assertTrue(any("maskable" in icon["purpose"].split() for icon in icons))
            for icon in icons:
                with self.subTest(icon=icon["sizes"]):
                    self.assertRegex(icon["src"], r"^/static/menus/pwa/icon-\d+\.[a-f0-9]+\.png$")
                    response = browser.get(icon["src"])
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.headers["Content-Type"], "image/png")
                    content = b"".join(response.streaming_content)
                    self.assertEqual(content[:8], b"\x89PNG\r\n\x1a\n")
                    self.assertEqual("x".join(map(str, unpack(">II", content[16:24]))), icon["sizes"])
                    self.assertNotIn("no-store", response.headers["Cache-Control"])
                    self.assertEqual(browser.head(icon["src"]).status_code, 200)
