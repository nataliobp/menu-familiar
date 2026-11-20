"""Run synthetic browser checks with Playwright and Chromium installed for QA."""
import os
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
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
                assert box["y"] + box["height"] <= height, (width, card.inner_text(), box)
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

    page.get_by_role("link", name="Plantilla", exact=True).click()
    cell = page.locator(".template-slot").first
    cell.click()
    page.get_by_label("Categoria suggerida").select_option("fish")
    page.get_by_role("button", name="Desa", exact=True).click()
    assert cell.get_attribute("data-category") == "fish"
    cell.click()
    page.get_by_label("Categoria suggerida").select_option("")
    page.get_by_role("button", name="Desa", exact=True).click()
    assert cell.get_attribute("data-category") == ""


def verify_v2(page, other, origin, week, today, dish_id, long_id, long_name):
    menu = f"{origin}/menu/{week}/"
    template = f"{origin}/plantilla/"
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    snapshots = os.environ.get("MENU_BROWSER_SCREENSHOTS")
    if snapshots:
        Path(snapshots).mkdir(parents=True, exist_ok=True)

    def capture(name):
        if snapshots:
            page.screenshot(path=Path(snapshots) / f"{name}.png")

    def no_overflow(width):
        assert page.locator("main").evaluate("(el) => el.scrollWidth <= el.clientWidth")
        assert page.locator("body").evaluate("(el) => el.scrollWidth") <= width

    for width, height in [(360, 780), (390, 780), (800, 480), (1024, 600)]:
        page.set_viewport_size({"width": width, "height": height})
        page.goto(menu)
        assert page.locator(".week .slot").count() == 14
        assert page.locator("[aria-current=date] time").get_attribute("datetime") == today
        assert page.get_by_text(long_name, exact=True).count() >= 1
        no_overflow(width)
        if width >= 800:
            bottom = page.locator(".module-nav").bounding_box()["y"]
            for card in page.locator(".week .slot").all():
                box = card.bounding_box()
                assert box["height"] >= 44 and box["y"] + box["height"] <= bottom
        capture(f"week-{width}")
        page.goto(template)
        page.locator("[data-category-trigger]").first.click()
        dialog = page.get_by_role("dialog", name="Dilluns · Dinar")
        assert dialog.get_by_role("button", name="Lliure").get_attribute("aria-pressed") == "true"
        assert dialog.locator(".category-choice").count() == 14
        no_overflow(width)
        capture(f"template-{width}")
        page.keyboard.press("Escape")
        assert not dialog.is_visible()
        assert page.locator("[data-category-trigger]").first.evaluate("(el) => el === document.activeElement")
        page.locator("[data-category-trigger]").first.press("Enter")
        assert dialog.get_by_role("button", name="Tanca").evaluate("(el) => el === document.activeElement")
        page.mouse.click(4, 4)
        dialog.wait_for(state="hidden")

    page.set_viewport_size({"width": 390, "height": 780})
    page.goto(template)
    other.goto(template)
    cells = page.locator("[data-category-trigger]")
    cell = cells.first
    second = cells.nth(1)
    cell.click()
    requests = []

    def fail_save(route):
        requests.append(route.request)
        route.fulfill(status=503, body="Unavailable")

    page.route("**/plantilla/0/lunch/", fail_save)
    with page.expect_response(lambda res: res.status == 503):
        dialog.get_by_role("button", name="Amanides").dblclick()
    assert dialog.get_by_role("alert").is_visible()
    assert len(requests) == 1 and "csrfmiddlewaretoken" in requests[0].post_data
    assert cell.get_attribute("data-category") == ""
    page.unroute("**/plantilla/0/lunch/", fail_save)
    with page.expect_response(lambda res: res.url.endswith("/plantilla/0/lunch/") and res.status == 200):
        dialog.get_by_role("button", name="Amanides").click()
    dialog.wait_for(state="hidden")
    assert cell.get_attribute("data-category") == "salads"
    assert cell.evaluate("(el) => el === document.activeElement")
    assert second.get_attribute("data-category") == ""
    second.click()
    with page.expect_response(lambda res: res.url.endswith("/plantilla/0/dinner/") and res.status == 200):
        page.get_by_role("dialog").get_by_role("button", name="Ous").click()
    page.get_by_role("dialog").wait_for(state="hidden")
    page.reload()
    assert cell.get_attribute("data-category") == "salads"
    assert second.get_attribute("data-category") == "eggs"

    other_cell = other.locator("[data-category-trigger]").first
    other_cell.click()
    with other.expect_response(lambda res: res.status == 409):
        other.get_by_role("dialog").get_by_role("button", name="Peix").click()
    assert other.get_by_role("alert").is_visible()
    assert other.get_by_role("dialog").get_by_role("button", name="Peix").is_disabled()
    other.get_by_role("link", name="Actualitza la plantilla").click()
    assert other_cell.get_attribute("data-category") == "salads"
    cell.click()
    with page.expect_response(lambda res: res.url.endswith("/plantilla/0/lunch/") and res.status == 200):
        dialog.get_by_role("button", name="Lliure").click()
    dialog.wait_for(state="hidden")
    page.reload()
    assert cell.get_attribute("data-category") == ""

    page.goto(menu)
    assert page.locator(".slot").nth(1).get_attribute("aria-label").endswith("Lliure")
    page.get_by_role("link", name="Setmana següent").click()
    assert page.locator("[aria-current=date]").count() == 0
    page.get_by_role("button", name="Crea el menú").click()
    assert page.locator(".slot").nth(1).get_attribute("aria-label").endswith("Ous")
    page.get_by_role("link", name="Avui").click()
    assert page.url == menu
    page.goto(f"{origin}/menu/2025-12-29/")
    assert "29/12/2025 – 4/1/2026" in page.locator(".week-nav").inner_text()
    page.get_by_role("link", name="Setmana següent").click()
    assert page.url.endswith("/2026-01-05/")
    historic = (week - timedelta(days=7)).isoformat()
    page.goto(f"{origin}/menu/{historic}/")
    assert page.locator(".week .slot").count() == 14
    page.locator(".week .slot").first.click()
    assert page.get_by_text("Setmana passada · només consulta").is_visible()
    assert page.get_by_role("link", name="Edita la recepta compartida").count() == 0

    page.goto(menu)
    page.locator(".week .slot").first.click()
    meal_actions = page.get_by_role("dialog", name="Dilluns · Dinar")
    assert meal_actions.get_by_role("link", name="Veure el plat").is_visible()
    capture("meal-actions")
    meal_actions.get_by_role("link", name="Mou o intercanvia").click()
    page.get_by_role("link", name=f"Diumenge · Sopar · {long_name}").click()
    page.get_by_role("button", name="Intercanvia els plats").click()
    assert page.get_by_text("Plats intercanviats", exact=True).is_visible()
    page.get_by_role("button", name="Desfés").click()
    assert page.get_by_text("Canvi desfet", exact=True).is_visible()
    page.locator(".week .slot").first.click()
    meal_actions.get_by_role("link", name="Omet aquest àpat").click()
    page.get_by_role("button", name="Confirma").click()
    page.locator(".week .slot").first.click()
    meal_actions.get_by_role("button", name="Torna a planificar").click()
    page.locator(".week .slot").first.click()
    picker_url = page.url
    candidates = page.locator(".list-row")
    assert candidates.count() == 57
    assert "Ocasió especial" in candidates.last.inner_text()
    capture("picker")
    page.get_by_label("Cerca un plat", exact=True).fill("arros")
    page.get_by_label("Categoria", exact=True).select_option("salads")
    page.get_by_role("button", name="Cerca", exact=True).click()
    assert candidates.count() == 1
    other.goto(picker_url + "?category=cereals")
    other.get_by_role("button", name=long_name).click()
    page.get_by_role("button", name="Arròs de prova").click()
    assert page.get_by_role("heading", name="El contingut ha canviat").is_visible()
    review_url = page.get_by_role("link", name="Revisa l’àpat").get_attribute("href")
    page.get_by_role("link", name="Torna a la tria de plats").click()
    assert page.get_by_role("heading", name="Canvia el plat").is_visible()
    assert page.get_by_label("Cerca un plat", exact=True).input_value() == "arros"
    assert page.get_by_label("Categoria", exact=True).input_value() == "salads"
    page.goto(origin + review_url)
    assert page.get_by_role("heading", name=long_name).is_visible()

    page.goto(f"{origin}/plats/")
    assert page.locator(".list-row").count() == 57
    assert page.get_by_role("heading", name="Cereals").count() == 1
    no_overflow(390)
    capture("catalogue")
    page.get_by_role("link", name="Arxivats", exact=True).click()
    assert page.locator(".list-row").count() == 1
    page.locator(".list-row").click()
    page.get_by_role("link", name="Restaura", exact=True).click()
    page.get_by_role("button", name="Confirma").click()
    assert page.get_by_role("link", name="Arxiva", exact=True).is_visible()

    page.goto(f"{origin}/plats/{dish_id}/")
    assert page.get_by_role("heading", name="Ingredients", exact=False).is_visible()
    assert page.get_by_role("heading", name="Preparació", exact=True).is_visible()
    assert "160 g" in page.locator(".ingredient").inner_text()
    assert page.locator(".steps").get_by_text("Preparació de prova", exact=True).is_visible()
    assert page.get_by_text("Hi ha canvis sense publicar", exact=False).is_visible()
    capture("cooking")
    page.goto(f"{origin}/plats/{long_id}/")
    assert page.get_by_text("Recepta pendent", exact=True).is_visible()
    no_overflow(390)
    assert not errors, errors


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
        from menus.models import DishRecord, SecondaryCategoryRecord

        clock = MadridClock()
        week = monday(clock.today())
        repository = DjangoPlanningRepository()
        dish = DishRecord.objects.create(name="Plat de prova", primary_category_id="cereals", meal_preference="both", special_occasion=False)
        long_name = "Plat llarg " + "x" * 189
        long_dish = DishRecord.objects.create(name=long_name, primary_category_id="cereals", meal_preference="both", special_occasion=False)
        create_menu(repository, clock, week)
        change_menu(repository, clock, week, (0, "lunch"), 1, "assign", dish.pk)
        change_menu(repository, clock, week, (6, "dinner"), 2, "assign", long_dish.pk)

        sample = DishRecord.objects.create(name="Arròs de prova", primary_category_id="eggs", meal_preference="both",
                                           special_occasion=False)
        SecondaryCategoryRecord.objects.create(dish=sample, category_id="salads")
        DishRecord.objects.bulk_create([
            DishRecord(name=f"Plat sintètic {index}", primary_category_id=("vegetables" if index % 2 else "salads"),
                       meal_preference=("dinner" if index % 3 == 0 else "both"), special_occasion=index % 5 == 0)
            for index in range(54)
        ])
        DishRecord.objects.create(name="Plat arxivat de prova", primary_category_id="fish",
                                  meal_preference="both", special_occasion=False, archived=True)
        historic = week - timedelta(days=7)
        previous_clock = SimpleNamespace(today=lambda: historic)
        create_menu(repository, previous_clock, historic)
        change_menu(repository, previous_clock, historic, (0, "lunch"), 1, "assign", dish.pk)

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
                page = browser.new_page()
                other = browser.new_page()
                for tab in (page, other):
                    tab.set_default_timeout(5000)
                # Restore a distinct first dish for the exchange scenario.
                page.goto(f"http://127.0.0.1:{server.port}/menu/{week}/slots/0/lunch/triar/?action=replace")
                page.get_by_role("button", name="Plat de prova", exact=True).click()
                page.wait_for_url(f"**/menu/{week}/")
                verify_v2(page, other, f"http://127.0.0.1:{server.port}", week, clock.today().isoformat(),
                          dish.pk, long_dish.pk, long_name)
                browser.close()
        finally:
            server.terminate()
    print("V1 and V2 browser checks passed with and without JavaScript.")


if __name__ == "__main__":
    main()
