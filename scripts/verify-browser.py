"""Run synthetic browser checks with Playwright and Chromium installed for QA."""
import os
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import expect, sync_playwright


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
    other.get_by_role("button", name="Revisa la recepta actual").click()
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

    for width, height in [(800, 480), (1024, 600), (360, 800), (390, 844)]:
        page.set_viewport_size({"width": width, "height": height})
        page.goto(menu)
        slots = page.locator(".week a.slot")
        assert slots.count() == 14
        assert page.locator("body").evaluate("(body) => body.scrollWidth") <= width
        if screenshots := os.environ.get("MENU_BROWSER_SCREENSHOTS"):
            page.screenshot(path=Path(screenshots) / f"no-js-week-{width}.png")
        for card in slots.all():
            box = card.bounding_box()
            assert box["x"] >= 0 and box["x"] + box["width"] <= width
            assert box["height"] >= 44
            if width >= 800:
                assert box["y"] + box["height"] <= height, (width, card.inner_text(), box)
    slots.first.focus()
    page.keyboard.press("Enter")
    page.wait_for_url(slot)
    page.get_by_role("link", name="Llista de la compra", exact=True).click()
    assert page.url.endswith(f"/compra/{week}/")
    expect(page.get_by_role("heading", name="Llista de la compra")).to_be_visible()
    expect(page.get_by_role("heading", name="Receptes incompletes")).to_be_visible()
    expect(page.locator("main form")).to_have_count(0)
    page.get_by_role("link", name="Menú setmanal", exact=True).click()
    assert page.url == menu

    page.get_by_role("link", name="Plantilla setmanal", exact=True).click()
    cell = page.locator(".template-slot").first
    cell.click()
    page.get_by_label("Categoria suggerida").select_option("fish")
    page.get_by_role("button", name="Desa", exact=True).click()
    assert cell.get_attribute("data-category") == "fish"
    cell.click()
    page.get_by_label("Categoria suggerida").select_option("")
    page.get_by_role("button", name="Desa", exact=True).click()
    assert cell.get_attribute("data-category") == ""

    future = (date.fromisoformat(week) + timedelta(days=21)).isoformat()
    url = f"{origin}/menu/{future}/"
    page.goto(url)
    expect(page.locator(".week .slot")).to_have_count(14)
    page.locator(".slot").first.click()
    page.get_by_label("Cerca un plat", exact=True).fill("arros")
    page.get_by_role("button", name="Cerca", exact=True).click()
    expect(page.locator(".list-row")).to_have_count(1)
    page.locator(".list-row").first.click()
    page.wait_for_url(url)
    expect(page.locator(".slot").first).to_contain_text("Arròs de prova")


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

    for width, height in [(360, 800), (390, 844), (800, 480), (1024, 600)]:
        page.set_viewport_size({"width": width, "height": height})
        page.goto(menu)
        assert page.locator(".week .slot").count() == 14
        assert page.locator("[aria-current=date] time").get_attribute("datetime") == today
        assert page.locator(".slot-suggestion img").count() >= 5
        assert page.get_by_text(long_name, exact=True).count() >= 1
        no_overflow(width)
        if width >= 800:
            bottom = page.locator(".module-nav").bounding_box()["y"]
            for card in page.locator(".week .slot").all():
                box = card.bounding_box()
                assert box["height"] >= 44 and box["y"] + box["height"] <= bottom
        capture(f"week-{width}")
        page.locator(".slot").nth(2).click()
        expect(page.locator(".picker-context img")).to_have_attribute("src", "/static/menus/category-icons/legumes.svg")
        capture(f"picker-{width}")
        page.goto(f"{origin}/plats/?category=pork")
        expect(page.locator(".group-heading img")).to_have_attribute("src", "/static/menus/category-icons/pork.svg")
        capture(f"catalogue-{width}")
        page.locator(".list-row").first.click()
        expect(page.locator(".metadata img")).to_have_attribute("src", "/static/menus/category-icons/pork.svg")
        capture(f"detail-{width}")
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

    page.set_viewport_size({"width": 390, "height": 844})
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

    def disconnect_template(route):
        route.abort()

    page.route("**/plantilla/0/lunch/", disconnect_template)
    dialog.get_by_role("button", name="Amanides").click()
    expect(dialog.get_by_role("alert")).to_contain_text("No s’ha pogut confirmar")
    assert cell.get_attribute("data-category") == ""
    page.unroute("**/plantilla/0/lunch/", disconnect_template)
    with page.expect_response(lambda res: res.url.split("?")[0].endswith("/plantilla/0/lunch/") and res.status == 200):
        dialog.get_by_role("button", name="Amanides").click()
    dialog.wait_for(state="hidden")
    assert cell.get_attribute("data-category") == "salads"
    assert cell.evaluate("(el) => el === document.activeElement")
    assert second.get_attribute("data-category") == ""
    second.click()
    with page.expect_response(lambda res: res.url.split("?")[0].endswith("/plantilla/0/dinner/") and res.status == 200):
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
    other.get_by_role("link", name="Recarrega la plantilla").click()
    assert other_cell.get_attribute("data-category") == "salads"
    cell.click()
    with page.expect_response(lambda res: res.url.split("?")[0].endswith("/plantilla/0/lunch/") and res.status == 200):
        dialog.get_by_role("button", name="Lliure").click()
    dialog.wait_for(state="hidden")
    page.reload()
    assert cell.get_attribute("data-category") == ""

    page.goto(menu)
    expect(page.locator(".slot").nth(1)).to_have_accessible_name("Dilluns, Sopar, pendent. Suggeriment de la plantilla: Ous. Tria un plat")
    page.get_by_role("link", name="Setmana següent").click()
    assert page.locator("[aria-current=date]").count() == 0
    assert page.get_by_role("button", name="Crea el menú").count() == 0
    expect(page.locator(".slot").nth(1).locator(".slot-suggestion")).to_have_text("Ous")
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
    assert page.get_by_text("Setmana passada · només de consulta").is_visible()
    assert page.get_by_role("link", name="Edita la recepta compartida").count() == 0

    page.goto(menu)
    page.locator(".week .slot").first.click()
    meal_actions = page.get_by_role("dialog", name="Dilluns · Dinar")
    assert meal_actions.get_by_role("link", name="Mostra el plat").is_visible()
    capture("meal-actions")
    meal_actions.get_by_role("link", name="Mou o intercanvia").click()
    page.get_by_role("button", name=f"Diumenge · Sopar · {long_name}").click()
    expect(page.get_by_text("Plats intercanviats", exact=True)).to_be_visible()
    page.get_by_role("button", name="Desfés").click()
    assert page.get_by_text("Canvi desfet", exact=True).is_visible()
    page.locator(".week .slot").first.click()
    skip = meal_actions.get_by_role("link", name="Omet aquest àpat")
    skip.click()
    confirm = page.get_by_role("dialog", name="Ometre l’àpat?")
    expect(confirm.get_by_role("link", name="Cancel·la")).to_be_focused()
    capture("skip-confirmation")
    page.keyboard.press("Escape")
    expect(confirm).to_be_hidden()
    expect(skip).to_be_focused()
    skip.click()
    confirm.get_by_role("button", name="Sí, omet l’àpat").click()
    expect(page.locator(".week .slot").first).to_have_class("slot skipped")
    page.locator(".week .slot").first.click()
    meal_actions.get_by_role("button", name="Torna a planificar").click()
    expect(page.locator(".week .slot").first).to_have_class("slot pending")
    page.locator(".week .slot").first.click()
    candidates = page.locator(".list-row")
    expect(candidates).to_have_count(57)
    picker_url = page.url
    assert "Ocasió especial" in candidates.last.inner_text()
    capture("picker")
    page.get_by_label("Cerca un plat", exact=True).fill("arros")
    page.get_by_label("Categoria", exact=True).select_option("salads")
    expect(page.get_by_role("button", name="Cerca", exact=True)).to_have_count(0)
    expect(candidates).to_have_count(1)
    other.goto(picker_url + "?category=cereals")
    other.get_by_role("button", name=long_name).click()
    other.wait_for_url(menu)
    page.get_by_role("button", name="Arròs de prova").click()
    expect(page.get_by_role("alert").filter(has_text="El contingut ha canviat")).to_be_visible()
    page.get_by_role("link", name="Revisa l’estat de l’àpat").click()
    assert page.get_by_role("heading", name="Canvia el plat").is_visible()
    assert page.get_by_label("Cerca un plat", exact=True).input_value() == "arros"
    assert page.get_by_label("Categoria", exact=True).input_value() == "salads"
    page.goto(f"{menu}slots/0/lunch/")
    assert page.get_by_role("heading", name=long_name).is_visible()

    page.goto(f"{origin}/plats/")
    assert page.locator(".list-row").count() == 57
    page.get_by_label("Categoria", exact=True).select_option("pork")
    expect(page.locator(".list-row")).to_have_count(9)
    expect(page.locator("[data-filter-icon] img")).to_have_attribute("src", "/static/menus/category-icons/pork.svg")
    page.get_by_label("Cerca un plat", exact=True).fill("sintetic 1")
    expect(page.locator(".list-row")).to_have_count(3)
    page.goto(f"{origin}/plats/")
    assert page.get_by_role("heading", name="Cereals").count() == 1
    no_overflow(390)
    capture("catalogue")
    page.get_by_role("link", name="Plats arxivats", exact=True).click()
    assert page.locator(".list-row").count() == 1
    page.locator(".list-row").click()
    page.get_by_role("button", name="Restaura", exact=True).click()
    archive = page.get_by_role("link", name="Arxiva", exact=True)
    expect(archive).to_be_visible()
    archive.click()
    dialog = page.get_by_role("dialog", name="Arxivar aquest plat?")
    expect(dialog).to_be_visible()
    capture("archive-confirmation")
    page.mouse.click(3, 3)
    expect(dialog).to_be_hidden()
    expect(archive).to_be_focused()
    archive.click()
    affirm = dialog.get_by_role("button", name="Sí, arxiva el plat")
    archive_url = "**/plats/*/archive/"
    attempts = []

    def fail_archive(route):
        if route.request.method == "POST":
            attempts.append(route.request.post_data)
            route.fulfill(status=503, body="Synthetic failure")
        else:
            route.continue_()

    page.route(archive_url, fail_archive)
    affirm.dblclick()
    expect(dialog.get_by_role("alert")).to_contain_text("No s’ha pogut desar")
    assert len(attempts) == 1 and "csrfmiddlewaretoken" in attempts[0]
    page.unroute(archive_url, fail_archive)
    other.goto(page.url)
    other.get_by_role("link", name="Arxiva", exact=True).click()
    other.get_by_role("button", name="Sí, arxiva el plat").click()
    expect(other.get_by_role("button", name="Restaura", exact=True)).to_be_visible()
    affirm.click()
    expect(dialog.get_by_role("alert")).to_contain_text("El contingut ha canviat")
    expect(affirm).to_be_disabled()
    dialog.get_by_role("link", name="Revisa el contingut actual").click()
    expect(page.get_by_role("button", name="Restaura", exact=True)).to_be_visible()

    page.get_by_role("link", name="Edita el plat", exact=True).click()
    page.get_by_label("Nom", exact=True).fill("Canvi que no es desa")
    page.get_by_role("link", name="Cancel·la").click()
    discard = page.get_by_role("dialog", name="Descartar els canvis?")
    expect(discard.get_by_role("button", name="Continua editant")).to_be_focused()
    discard.get_by_role("button", name="Continua editant").click()
    expect(page.get_by_label("Nom", exact=True)).to_have_value("Canvi que no es desa")
    page.get_by_role("link", name="Cancel·la").click()
    discard.get_by_role("link", name="Descarta els canvis").click()
    expect(page.get_by_role("heading", name="Plat arxivat de prova")).to_be_visible()

    page.goto(f"{origin}/plats/{dish_id}/recepta/edit/")
    page.locator("#preparation").fill("Canvi de recepta que no es desa")
    page.get_by_role("button", name="Cancel·la").click()
    expect(discard).to_be_visible()
    discard.get_by_role("link", name="Descarta els canvis").click()
    page.wait_for_url(f"{origin}/plats/{dish_id}/")

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


def verify_virtual(page, other, origin, current_week):
    future = current_week + timedelta(days=28)
    menu = f"{origin}/menu/{future}/"
    requests = []

    def saved_version():
        with sqlite3.connect(os.environ["DJANGO_DB_PATH"]) as database:
            row = database.execute("SELECT version FROM menus_weeklymenurecord WHERE week_start = ?",
                                   (future.isoformat(),)).fetchone()
            return row[0] if row else None

    page.on("request", lambda request: requests.append(request.url))
    page.goto(menu)
    expect(page.locator(".slot")).to_have_count(14)
    slot = page.locator(".slot").nth(2)
    expect(slot.locator(".slot-suggestion")).to_have_text("Llegums")
    expect(slot.locator("img")).to_have_attribute("src", "/static/menus/category-icons/legumes.svg")
    expect(slot).to_contain_text("Tria un plat")
    slot.click()
    picker = page.url
    expect(page.get_by_label("Categoria", exact=True)).to_have_value("legumes")
    expect(page.locator(".list-row")).to_have_count(9)
    other.goto(picker + "?category=")
    page.get_by_label("Categoria", exact=True).select_option("")
    expect(page.locator(".list-row")).to_have_count(57)
    search = page.get_by_label("Cerca un plat", exact=True)
    search.dispatch_event("compositionstart")
    search.fill("Arros")
    expect(page.locator(".list-row")).to_have_count(57)
    search.dispatch_event("compositionend")
    expect(page.locator(".list-row")).to_have_count(1)
    assert saved_version() is None

    candidate = page.get_by_role("button", name="Arròs de prova")
    assignment = "**/slots/1/lunch/assign/"
    writes = []

    def fail(route):
        writes.append(route.request.post_data)
        route.fulfill(status=500, body="Synthetic failure")

    page.route(assignment, fail)
    candidate.dblclick()
    expect(page.get_by_role("alert").filter(has_text="No s’ha pogut desar")).to_be_visible()
    assert len(writes) == 1 and "csrfmiddlewaretoken" in writes[0]
    assert saved_version() is None
    page.unroute(assignment, fail)

    def disconnect(route):
        route.abort()

    page.route(assignment, disconnect)
    candidate.click()
    expect(page.get_by_role("alert").filter(has_text="No s’ha pogut confirmar")).to_be_visible()
    assert saved_version() is None
    page.unroute(assignment, disconnect)
    candidate.click()
    page.wait_for_url(menu)
    expect(slot).to_contain_text("Arròs de prova")
    expect(slot.locator(".slot-suggestion")).to_have_count(0)

    other.get_by_role("button", name="Plat de prova", exact=True).click()
    expect(other.get_by_role("alert").filter(has_text="El contingut ha canviat")).to_be_visible()
    assert saved_version() == 2

    page.get_by_role("link", name="Plantilla setmanal", exact=True).click()
    assert f"week={future}" in page.url
    for category, expected in (("Peix", "Peix"), ("Lliure", None), ("Llegums", "Llegums")):
        page.locator(".template-slot").nth(2).click()
        dialog = page.get_by_role("dialog", name="Dimarts · Dinar")
        dialog.get_by_role("button", name=category, exact=True).click()
        expect(dialog).to_be_hidden()
        page.get_by_role("link", name="Menú setmanal", exact=True).click()
        assert page.url == menu
        expect(slot).to_contain_text("Arròs de prova")
        expect(slot.locator(".slot-suggestion")).to_have_count(0)
        page.goto(f"{origin}/menu/{current_week}/")
        pending = page.locator(".slot").nth(2).locator(".slot-suggestion")
        if expected is None:
            expect(pending).to_have_count(0)
        else:
            expect(pending).to_have_text(expected)
        page.goto(menu)
        page.get_by_role("link", name="Plantilla setmanal", exact=True).click()
    page.get_by_role("link", name="Menú setmanal", exact=True).click()
    slot.click()
    page.get_by_role("link", name="Retira el plat").click()
    confirmation = page.get_by_role("dialog", name="Retirar el plat?")
    confirmation.get_by_role("button", name="Sí, retira el plat").click()
    expect(slot.locator(".slot-suggestion")).to_have_text("Llegums")
    assert all(url.startswith(origin + "/") for url in requests), requests


def reminder_fixture(repo, clock, week):
    from menus.application.planning import change_menu
    from menus.application.recipes import save_recipe
    from menus.domain.recipe import recipe_content
    from menus.infrastructure.django_dishes import DjangoDishRepository
    from menus.models import DishRecord

    def dish(name):
        return DishRecord.objects.create(name=name, primary_category_id="cereals", meal_preference="both", special_occasion=False)

    published = dish("Arròs amb verdures de prova")
    published_content = recipe_content("Cou l’arròs.", [
        {"name": "Arròs", "quantity": "0,080", "unit": "kg"},
        {"name": "Ceba", "quantity": "1", "unit": "unit"},
        {"name": "Pollastre", "quantity": "250", "unit": "g"},
        {"name": "Lluç", "quantity": "100", "unit": "g"},
        {"name": "Ous", "quantity": "1", "unit": "unit"},
        {"name": "Ingredient de prova amb un nom llarg per comprovar que la secció i el text s’ajusten bé", "taste": True},
        {"name": "Pebre negre", "taste": True},
        {"name": "Brou vegetal", "quantity": "125,125", "unit": "ml"},
    ], True)
    save_recipe(DjangoDishRepository(), clock, published.pk, 1, published_content, True)
    draft = dish("Sopa de prova en esborrany")
    draft_content = recipe_content("", [
        {"name": "Brou vegetal", "quantity": "250", "unit": "ml"}, {"name": "Ceba", "unit": "unit"},
    ])
    save_recipe(DjangoDishRepository(), clock, draft.pk, 1, draft_content)
    missing = dish("Plat de prova sense recepta")
    version = 0
    for day, dish_id in enumerate((published.pk, draft.pk, missing.pk, published.pk)):
        version = change_menu(repo, clock, week, (day, "lunch"), version, "assign", dish_id).version


def verify_reminder(page, origin, week, mode):
    url = f"{origin}/compra/{week}/"
    for width, height in ((360, 800), (390, 844), (800, 480), (1024, 600)):
        page.set_viewport_size({"width": width, "height": height})
        page.goto(url)
        expect(page.get_by_role("heading", name="Llista de la compra", exact=True)).to_be_visible()
        expect(page.get_by_text("Ingredients necessaris per al menú setmanal", exact=True)).to_be_visible()
        expect(page.get_by_role("heading", name="Receptes incompletes")).to_be_visible()
        expect(page.get_by_text("Quantitats provisionals de l’esborrany")).to_be_visible()
        expect(page.get_by_text("Recepta pendent", exact=True)).to_be_visible()
        expect(page.get_by_text("500,25 ml", exact=True)).to_be_visible()
        expect(page.get_by_text("160 g", exact=True)).to_be_visible()
        expect(page.get_by_role("region", name="Fruita i verdura").get_by_text("2 unitats", exact=True)).to_be_visible()
        expect(page.get_by_text("Subtotal conegut", exact=True)).to_be_visible()
        expect(page.get_by_text("Quantitat pendent", exact=True)).to_be_visible()
        assert [label.strip() for label in page.locator(".reminder-body h2").all_text_contents()] == [
            "Fruita i verdura", "Carn", "Peix", "Lactis i ous", "Rebost", "Altres",
        ]
        expect(page.get_by_role("region", name="Rebost").get_by_text("Al gust", exact=True)).to_be_visible()
        expect(page.locator("main form, main button, main input")).to_have_count(0)
        for locator in (page.locator("body"), page.locator("main")):
            assert locator.evaluate("el => el.scrollWidth <= el.clientWidth"), (mode, width)
        if width >= 800:
            first_amount = page.locator(".reminder-amount strong").first.bounding_box()
            navigation = page.locator(".module-nav").bounding_box()
            assert first_amount["y"] + first_amount["height"] <= navigation["y"], (mode, width)
        if screenshots := os.environ.get("MENU_BROWSER_SCREENSHOTS"):
            page.screenshot(path=Path(screenshots) / f"{mode}-reminder-{width}x{height}.png")
        page.get_by_role("link", name="Ves al menú setmanal").click()
        assert page.url == f"{origin}/menu/{week}/"
        page.get_by_role("link", name="Llista de la compra", exact=True).click()
        assert page.url == url
    page.get_by_role("link", name="Setmana següent").click()
    expect(page.get_by_text("No hi ha cap menú per a aquesta setmana.")).to_be_visible()
    page.get_by_role("link", name="Setmana anterior").click()
    assert page.url == url
    assert page.request.post(url + "manual/add/").status == 404
    page.goto(f"{origin}/menu/{week}/slots/3/lunch/")
    actions = page.get_by_role("link", name="Accions de l’àpat")
    if mode == "js":
        actions.click()
    page.get_by_role("link", name="Retira el plat").click()
    page.get_by_role("button", name="Sí, retira el plat").click()
    page.get_by_role("link", name="Llista de la compra", exact=True).click()
    expect(page.get_by_text("80 g", exact=True)).to_be_visible()
    expect(page.get_by_text("375,125 ml", exact=True)).to_be_visible()

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
        from menus.application.planning import change_menu
        from menus.domain.planning import monday
        from menus.infrastructure.django_planning import DjangoPlanningRepository, MadridClock
        from menus.models import DishRecord, SecondaryCategoryRecord, TemplateSlotRecord

        clock = MadridClock()
        week = monday(clock.today())
        repository = DjangoPlanningRepository()
        dish = DishRecord.objects.create(name="Plat de prova", primary_category_id="cereals", meal_preference="both", special_occasion=False)
        long_name = "Plat llarg " + "x" * 189
        long_dish = DishRecord.objects.create(name=long_name, primary_category_id="cereals", meal_preference="both", special_occasion=False)
        change_menu(repository, clock, week, (0, "lunch"), 0, "assign", dish.pk)
        change_menu(repository, clock, week, (6, "dinner"), 2, "assign", long_dish.pk)

        sample = DishRecord.objects.create(name="Arròs de prova", primary_category_id="eggs", meal_preference="both",
                                           special_occasion=False)
        SecondaryCategoryRecord.objects.create(dish=sample, category_id="salads")
        for index, category in enumerate(("legumes", "pork", "fish", "vegetables", "pasta")):
            TemplateSlotRecord.objects.filter(day_index=index + 1, meal="lunch").update(suggested_category_id=category)
        DishRecord.objects.bulk_create([
            DishRecord(name=f"Plat sintètic {index}",
                       primary_category_id=("legumes", "pork", "fish", "vegetables", "pasta", "salads")[index % 6],
                       meal_preference=("dinner" if index % 3 == 0 else "both"), special_occasion=index % 5 == 0)
            for index in range(54)
        ])
        DishRecord.objects.create(name="Plat arxivat de prova", primary_category_id="fish",
                                  meal_preference="both", special_occasion=False, archived=True)
        historic = week - timedelta(days=7)
        previous_clock = SimpleNamespace(today=lambda: historic)
        change_menu(repository, previous_clock, historic, (0, "lunch"), 0, "assign", dish.pk)

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
                verify_virtual(page, other, f"http://127.0.0.1:{server.port}", week)
                browser.close()

            reminder_week = week + timedelta(weeks=8)
            no_js_week = reminder_week + timedelta(weeks=2)
            reminder_fixture(repository, clock, reminder_week)
            reminder_fixture(repository, clock, no_js_week)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                for javascript, target in ((True, reminder_week), (False, no_js_week)):
                    page = browser.new_page(java_script_enabled=javascript)
                    page.set_default_timeout(5000)
                    verify_reminder(page, f"http://127.0.0.1:{server.port}", target, "js" if javascript else "no-js")
                browser.close()
        finally:
            server.terminate()
    print("V1 and V2 browser checks passed with and without JavaScript.")


if __name__ == "__main__":
    main()
