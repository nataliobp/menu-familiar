"""Check a disposable copy of the private V2.3/V2.4 catalogue in Chromium."""

import argparse
import os
from pathlib import Path
import sqlite3
import sys

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = ((360, 800), (390, 844), (800, 480), (1024, 600))
sys.path.insert(0, str(ROOT))


def verify_catalogue(page, origin, sources):
    page.goto(f"{origin}/plats/")
    expect(page.locator("html")).to_have_attribute("lang", "ca")
    expect(page.locator(".catalogue-groups .list-row")).to_have_count(57)
    expect(page.locator(".catalogue-groups .list-row").filter(has_text="Recepta proposada")).to_have_count(57)
    expect(page.locator(".recipe-photo")).to_have_count(0)
    for source_id, (dish_id, has_photo) in sources.items():
        response = page.goto(f"{origin}/plats/{dish_id}/")
        assert response.ok, source_id
        assert page.locator(".ingredient-list li").count() > 0, source_id
        assert page.locator(".steps li").count() > 0, source_id
        if has_photo:
            expect(page.locator(".recipe-photo img")).to_have_js_property("naturalWidth", 800)
        else:
            expect(page.locator(".recipe-photo")).to_have_count(0)


def verify_sizes(page, origin, sources, mode, screenshots):
    photo_id, _ = sources[1]
    no_photo_id, _ = sources[43]
    for width, height in VIEWPORTS:
        page.set_viewport_size({"width": width, "height": height})
        for dish_id, photo in ((photo_id, True), (no_photo_id, False)):
            page.goto(f"{origin}/plats/{dish_id}/")
            ingredients = page.get_by_role("heading", name="Ingredients · 2 adults", exact=True)
            preparation = page.get_by_role("heading", name="Preparació", exact=True)
            expect(ingredients).to_be_visible()
            expect(preparation).to_be_visible()
            expect(page.locator("ol.steps")).to_be_visible()
            if photo:
                image = page.locator(".recipe-photo img")
                expect(image).to_have_js_property("naturalWidth", 800)
                expect(image).to_have_js_property("naturalHeight", 600)
                expect(page.get_by_text("Imatge generada", exact=True)).to_be_visible()
                if width >= 800:
                    assert abs(ingredients.bounding_box()["y"] - preparation.bounding_box()["y"]) < 2
                    assert image.bounding_box()["x"] > preparation.bounding_box()["x"]
                    assert ingredients.bounding_box()["y"] < height
            else:
                expect(page.get_by_text("Recepta proposada a partir d’una preparació de casa", exact=False)).to_be_visible()
                expect(page.locator(".recipe-photo")).to_have_count(0)
            for locator in (page.locator("body"), page.locator("main")):
                assert locator.evaluate("el => el.scrollWidth <= el.clientWidth"), (mode, width, dish_id)
            if screenshots:
                filename = f"{mode}-{width}x{height}-{'photo' if photo else 'no-photo'}.png"
                page.screenshot(path=screenshots / filename)
        page.goto(f"{origin}/menu/")
        expect(page.locator(".week .slot")).to_have_count(14)
        expect(page.locator(".recipe-photo")).to_have_count(0)
        page.get_by_role("link", name="Plantilla setmanal", exact=True).click()
        expect(page.get_by_role("heading", name="Plantilla setmanal")).to_be_visible()
        expect(page.locator(".template-slot")).to_have_count(14)
        assert page.locator("main").evaluate("el => el.scrollWidth <= el.clientWidth")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    database = args.database.absolute()
    if args.screenshots:
        args.screenshots.mkdir(mode=0o700)
    with sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True) as connection:
        sources = {source_id: (dish_id, bool(digest)) for source_id, dish_id, digest in connection.execute(
            "SELECT source_id, dish_id, photo_digest FROM menus_cataloguesourcerecord ORDER BY source_id")}
    connection.close()
    assert set(sources) == set(range(1, 58))
    assert sum(photo for _, photo in sources.values()) == 9
    os.environ.update(DJANGO_ENV="development", DJANGO_DEBUG="0", DJANGO_SETTINGS_MODULE="config.settings",
                      DJANGO_ALLOWED_HOSTS="127.0.0.1", DJANGO_DB_PATH=str(database),
                      DJANGO_RECIPE_PHOTO_ROOT=str(database.parent / "recipe-photos"))
    import django
    django.setup()
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    from django.db import connections
    from django.test.testcases import LiveServerThread

    connections["default"].settings_dict["NAME"] = f"{database.as_uri()}?mode=ro"
    server = LiveServerThread("127.0.0.1", StaticFilesHandler)
    server.start()
    if not server.is_ready.wait(10):
        raise RuntimeError("Browser QA server did not start")
    try:
        if server.error:
            raise server.error
        origin = f"http://127.0.0.1:{server.port}"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            for javascript in (False, True):
                context = browser.new_context(java_script_enabled=javascript)
                page = context.new_page()
                requests = []
                page.on("request", lambda request: requests.append(request.url))
                verify_catalogue(page, origin, sources)
                verify_sizes(page, origin, sources, "js" if javascript else "no-js", args.screenshots)
                response = page.goto(f"{origin}/plats/0/recepta/foto/")
                assert response.status == 404
                expect(page.get_by_role("heading", name="No s’ha trobat la pàgina")).to_be_visible()
                assert all(url.startswith(f"{origin}/") for url in requests)
                context.close()
            browser.close()
    finally:
        server.terminate()
    print("Private catalogue, inline recipes, local photo coverage and four viewports verified with and without JavaScript.")


if __name__ == "__main__":
    main()
