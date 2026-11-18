"""Run synthetic browser checks with Playwright and Chromium installed for QA."""
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright


def verify(page, other, origin, week, dish_id, long_id, long_name):
    menu = f"{origin}/menu/{week}/"
    editor = f"{origin}/plats/{dish_id}/recepta/edit/"
    page.goto(editor)
    page.locator("#preparation").fill("Preparació de prova")
    page.locator('[name="name"]').fill("Arròs")
    page.get_by_role("button", name="Publica la recepta").click()
    assert page.url.endswith("/publish/")
    page.locator('[name="quantity"]').fill("160")
    page.locator('[name="unit"]').select_option("g")
    page.get_by_role("button", name="Cancel·la").click()
    assert page.url == editor
    page.get_by_role("button", name="Continua editant").click()
    assert page.locator('[name="quantity"]').input_value() == "160"
    page.get_by_role("button", name="Afegeix un ingredient").click()
    assert page.locator("fieldset").count() == 2
    page.get_by_role("button", name="Elimina la fila").last.click()
    assert page.locator("fieldset").count() == 1

    other.goto(editor)
    page.get_by_role("button", name="Publica la recepta").click()
    assert page.get_by_text("Recepta publicada", exact=True).count() > 0
    other.locator("#preparation").fill("Canvi de la segona pestanya")
    other.get_by_role("button", name="Desa l’esborrany").click()
    other.get_by_role("button", name="Revisa el valor actual").click()
    assert other.url == editor
    assert other.locator("#preparation").input_value() == "Canvi de la segona pestanya"
    other.get_by_role("button", name="Desa l’esborrany").click()
    assert other.get_by_text("Esborrany desat", exact=True).count() == 1

    slot = f"{menu}slots/0/lunch/"
    page.goto(slot)
    stale_editor = page.context.new_page()
    stale_editor.goto(slot + "recepta/edit/")
    stale_editor.locator("#preparation").fill("Canvis contextuals sense desar")
    other.goto(slot)
    other.get_by_role("link", name="Canvia el plat").click()
    other.get_by_role("button", name=long_name, exact=False).click()
    stale_editor.get_by_role("button", name="Afegeix un ingredient").click()
    assert stale_editor.get_by_role("heading", name="El contingut ha canviat").count() == 1
    stale_editor.close()
    page.get_by_role("link", name="Retira el plat").click()
    assert page.get_by_role("heading", name="El contingut ha canviat").count() == 1
    page.goto(slot)
    assert page.get_by_role("heading", name=long_name).count() == 1
    assert long_id != dish_id

    for width, height in [(800, 480), (1024, 600), (360, 740), (430, 850)]:
        page.set_viewport_size({"width": width, "height": height})
        page.goto(menu)
        slots = page.locator(".week a.slot")
        assert slots.count() == 14
        assert page.locator("body").evaluate("(body) => body.scrollWidth") <= width
        for card in slots.all():
            box = card.bounding_box()
            assert box["x"] >= 0 and box["x"] + box["width"] <= width
            assert box["height"] >= 44
            if width >= 800:
                assert box["y"] + box["height"] <= height
    slots.first.focus()
    page.keyboard.press("Enter")
    page.wait_for_url(slot)
    page.get_by_role("link", name="Llista de la compra").click()
    assert page.url.endswith(f"/compra/{week}/")
    page.get_by_role("link", name="Afegeix un producte").click()
    page.locator('[name="name"]').fill("Pa de prova")
    page.get_by_role("button", name="Desa").click()
    page.get_by_role("button", name="Marca com a comprat: Pa de prova").click()
    assert page.get_by_role("button", name="Desmarca: Pa de prova").count() == 1
    page.get_by_role("link", name="Menú setmanal").click()
    assert page.url == menu


def main():
    with TemporaryDirectory(prefix="menu-browser-") as directory:
        os.environ.update(DJANGO_ENV="development", DJANGO_DEBUG="1",
                          DJANGO_DB_PATH=str(Path(directory) / "browser.sqlite3"),
                          DJANGO_SETTINGS_MODULE="config.settings")
        subprocess.run([sys.executable, str(ROOT / "manage.py"), "migrate", "--noinput", "--verbosity", "0"], check=True)

        import django
        django.setup()
        from django.contrib.staticfiles.handlers import StaticFilesHandler
        from django.test.testcases import LiveServerThread
        from menus.application.planning import change_menu, create_menu
        from menus.domain.planning import monday
        from menus.infrastructure.django_planning import DjangoPlanningRepository, MadridClock
        from menus.models import DishRecord

        clock = MadridClock()
        week = monday(clock.today())
        repository = DjangoPlanningRepository()
        dish = DishRecord.objects.create(name="Plat de prova", primary_category_id="cereals", meal_preference="both", special_occasion=False)
        long_name = "Plat llarg " + "x" * 189
        long_dish = DishRecord.objects.create(name=long_name, primary_category_id="cereals", meal_preference="both", special_occasion=False)
        create_menu(repository, clock, week)
        change_menu(repository, clock, week, (0, "lunch"), 1, "assign", dish.pk)
        change_menu(repository, clock, week, (6, "dinner"), 2, "assign", long_dish.pk)

        server = LiveServerThread("127.0.0.1", StaticFilesHandler)
        server.start()
        server.is_ready.wait(10)
        try:
            if server.error:
                raise server.error
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                first = browser.new_context(java_script_enabled=False)
                second = browser.new_context(java_script_enabled=False)
                for context in (first, second):
                    context.set_default_timeout(5000)
                verify(first.new_page(), second.new_page(), f"http://127.0.0.1:{server.port}",
                       week.isoformat(), dish.pk, long_dish.pk, long_name)
                browser.close()
        finally:
            server.terminate()
    print("Browser checks passed with JavaScript disabled.")


if __name__ == "__main__":
    main()
