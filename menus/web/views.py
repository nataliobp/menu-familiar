from django.db import DatabaseError
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from menus.application.template import TemplateConflict, get_template, set_template_category
from menus.infrastructure.django_template import DjangoTemplateRepository

DAYS = ("Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres", "Dissabte", "Diumenge")
MEALS = {"lunch": "Dinar", "dinner": "Sopar"}


def unavailable():
    return HttpResponse("El servei no està disponible. Torna-ho a provar.", status=503)


@require_http_methods(["GET"])
def template_view(request):
    try:
        template, categories = get_template(DjangoTemplateRepository())
        days = [(day, label, [(meal, MEALS[meal], categories.get(template.slots[(day, meal)], "Lliure"))
                              for meal in ("lunch", "dinner")]) for day, label in enumerate(DAYS)]
        return render(request, "menus/template.html", {"days": days})
    except (DatabaseError, ValueError, KeyError):
        return unavailable()


@require_http_methods(["GET", "POST"])
def template_edit(request, day, meal):
    if day not in range(7) or meal not in MEALS:
        raise Http404()
    repo = DjangoTemplateRepository()
    try:
        template, categories = get_template(repo)
        selected = template.slots[(day, meal)] or ""
        error = None
        status = 200
        if request.method == "POST":
            choices = request.POST.getlist("category")
            selected = choices[0] if len(choices) == 1 else ""
            try:
                if len(choices) != 1:
                    raise ValueError()
                version = int(request.POST.get("version", ""))
                set_template_category(repo, (day, meal), selected or None, version)
                messages.success(request, "Plantilla actualitzada")
                return redirect("weekly_template")
            except (ValueError, TypeError):
                error, status = "Selecciona una categoria vàlida.", 400
            except TemplateConflict:
                error, status = "La plantilla ha canviat. Revisa la selecció i torna-ho a provar.", 409
        return render(request, "menus/template_edit.html", {"day": DAYS[day], "meal": MEALS[meal], "categories": categories.items(), "selected": selected, "selected_label": categories.get(selected, "Lliure"), "current_label": categories.get(template.slots[(day, meal)], "Lliure"), "version": template.version, "error": error}, status=status)
    except (DatabaseError, ValueError, KeyError):
        return unavailable()

from datetime import date, timedelta
from django.db import IntegrityError, transaction
from django.views.decorators.http import require_POST
from menus.application.planning import PastWeek, PlanningConflict, Rollover, change_menu, create_menu
from menus.domain.planning import monday
from menus.infrastructure.django_planning import DjangoPlanningRepository, MadridClock
from menus.models import DishRecord, MenuSlotRecord
from menus.domain.recommendations import rank_candidates


def parse_week(value):
    try:
        week = date.fromisoformat(value)
        if week.isoformat() != value or week.weekday() != 0:
            raise ValueError()
        return week
    except ValueError:
        raise Http404()


@require_http_methods(["GET"])
def current_menu(request):
    return redirect("menu_week", week=monday(MadridClock().today()).isoformat())


@require_http_methods(["GET"])
def menu_view(request, week):
    week = parse_week(week)
    repo, clock = DjangoPlanningRepository(), MadridClock()
    try:
        with transaction.atomic():
            menu = repo.get(week)
            editable = week >= monday(clock.today())
            if menu is None:
                if editable:
                    template, categories = repo.template()
                    slots = {position: (categories.get(category, "Lliure") if category else "Lliure") for position, category in template.slots.items()}
                else:
                    slots = {(day, meal): "" for day in range(7) for meal in MEALS}
            else:
                slots = menu.slots
        days = []
        for day, label in enumerate(DAYS):
            meals = []
            for meal in ("lunch", "dinner"):
                slot = slots[(day, meal)]
                meals.append((meal, MEALS[meal], slot))
            days.append((day, label, meals))
        return render(request, "menus/menu.html", {"week": week, "days": days, "menu": menu,
                      "editable": editable, "week_end": week + timedelta(days=6), "previous": week - timedelta(days=7), "next": week + timedelta(days=7)})
    except (DatabaseError, ValueError, KeyError):
        return unavailable()


@require_POST
def menu_create(request, week):
    week = parse_week(week)
    try:
        create_menu(DjangoPlanningRepository(), MadridClock(), week)
        return redirect("menu_week", week=week.isoformat())
    except PastWeek:
        return HttpResponse("Aquesta setmana és només de consulta.", status=403)
    except (DatabaseError, Rollover, ValueError):
        return unavailable()


@require_http_methods(["GET"])
def menu_picker(request, week, day, meal):
    week = parse_week(week)
    if day not in range(7) or meal not in MEALS:
        raise Http404()
    repo = DjangoPlanningRepository()
    try:
        with transaction.atomic():
            menu = repo.get(week)
            if not menu or week < monday(MadridClock().today()):
                raise Http404()
            slot = menu.slots[(day, meal)]
            action = request.GET.get("action", "assign")
            if action not in ("assign", "replace") or slot.state != ("pending" if action == "assign" else "selected"):
                raise Http404()
            records = DishRecord.objects.filter(archived=False).select_related("primary_category").prefetch_related("secondary_categories")
            candidates = [{"id": d.pk, "name": d.name, "primary_name": d.primary_category.name_ca,
                           "categories": {d.primary_category_id} | {c.category_id for c in d.secondary_categories.all()},
                           "meal_preference": d.meal_preference, "special_occasion": d.special_occasion} for d in records]
            latest = {}
            for dish_id, week_start, day_index in MenuSlotRecord.objects.filter(dish__isnull=False).values_list("dish_id", "weekly_menu_id", "day_index"):
                occurrence = week_start + timedelta(days=day_index)
                if dish_id not in latest or occurrence > latest[dish_id]:
                    latest[dish_id] = occurrence
            categories = repo.template()[1]
            category = request.GET.get("category")
            if category is None and request.GET.get("mode") != "all" and slot.suggestion:
                category = slot.suggestion[0]
            if category and category not in categories:
                raise ValueError("Unknown category")
            query = request.GET.get("q", "")
            dishes = rank_candidates(candidates, meal, latest, category, query)
        return render(request, "menus/picker.html", {"week": week, "day": day, "meal": meal, "action": action, "menu": menu, "dishes": dishes, "categories": categories.items(), "category": category, "query": query, "slot": slot})
    except (DatabaseError, ValueError, KeyError):
        return unavailable()


@require_POST
def menu_action(request, week, day, meal, action):
    week = parse_week(week)
    if day not in range(7) or meal not in MEALS or action not in ("assign", "replace", "remove", "skip", "reactivate"):
        raise Http404()
    try:
        version = int(request.POST.get("version", ""))
        dish_id = int(request.POST.get("dish", "0"))
        if action in ("assign", "replace") and not 1 <= dish_id < 9223372036854775807:
            raise ValueError("Invalid dish identifier")
        change_menu(DjangoPlanningRepository(), MadridClock(), week, (day, meal), version, action, dish_id, request.POST.get("confirm") == "yes")
        messages.success(request, "Canvi desat")
        return redirect("menu_week", week=week.isoformat())
    except PastWeek:
        return HttpResponse("Aquesta setmana és només de consulta.", status=403)
    except PlanningConflict:
        return HttpResponse("El contingut ha canviat. Actualitza la pàgina abans de tornar-ho a provar.", status=409)
    except (ValueError, TypeError, KeyError):
        return HttpResponse("No s’ha pogut completar l’acció.", status=400)
    except (DatabaseError, Rollover):
        return unavailable()


@require_http_methods(["GET"])
def slot_detail(request, week, day, meal):
    week = parse_week(week)
    if day not in range(7) or meal not in MEALS:
        raise Http404()
    try:
        with transaction.atomic():
            menu = DjangoPlanningRepository().get(week)
            if menu is None:
                raise Http404()
            slot = menu.slots[(day, meal)]
        return render(request, "menus/slot.html", {"week": week, "day": day, "meal": meal, "slot": slot, "menu": menu, "editable": week >= monday(MadridClock().today())})
    except (DatabaseError, ValueError, KeyError):
        return unavailable()


@require_http_methods(["GET", "POST"])
def menu_confirm(request, week, day, meal, action):
    if request.method == "POST" and request.POST.get("confirm") == "yes":
        return menu_action(request, week, day, meal, action)
    week = parse_week(week)
    if day not in range(7) or meal not in MEALS or action not in ("remove", "skip"):
        raise Http404()
    try:
        menu = DjangoPlanningRepository().get(week)
        if not menu:
            raise Http404()
        if week < monday(MadridClock().today()):
            return HttpResponse("Aquesta setmana és només de consulta.", status=403)
        if request.method == "POST":
            try:
                if int(request.POST.get("version", "")) != menu.version:
                    return HttpResponse("El contingut ha canviat. Actualitza la pàgina abans de tornar-ho a provar.", status=409)
            except ValueError:
                return HttpResponse("Versió invàlida.", status=400)
        return render(request, "menus/confirm.html", {"week": week, "day": day, "meal": meal, "action": action, "menu": menu})
    except (DatabaseError, ValueError, KeyError):
        return unavailable()

from menus.application.planning import move_or_undo


@require_http_methods(["GET"])
def move_choice(request, week, day, meal):
    week = parse_week(week)
    if day not in range(7) or meal not in MEALS:
        raise Http404()
    try:
        menu = DjangoPlanningRepository().get(week)
        if not menu or menu.slots[(day, meal)].state != "selected":
            raise Http404()
        if week < monday(MadridClock().today()):
            return HttpResponse("Aquesta setmana és només de consulta.", status=403)
        choices = [(d, DAYS[d], m, MEALS[m], menu.slots[(d, m)]) for d in range(7) for m in MEALS if (d, m) != (day, meal)]
        return render(request, "menus/move.html", {"week": week, "day": day, "meal": meal, "menu": menu, "choices": choices})
    except (DatabaseError, ValueError, KeyError):
        return unavailable()


@require_POST
def move_action(request, week, action):
    week = parse_week(week)
    if action not in ("move", "exchange", "undo"):
        raise Http404()
    try:
        version = int(request.POST.get("version", ""))
        source = destination = None
        if action in ("move", "exchange"):
            source = (int(request.POST.get("source_day", "")), request.POST.get("source_meal"))
            destination = (int(request.POST.get("destination_day", "")), request.POST.get("destination_meal"))
        move_or_undo(DjangoPlanningRepository(), MadridClock(), week, version, source, destination, request.POST.get("confirm") == "yes", action)
        messages.success(request, "Canvi desat")
        return redirect("menu_week", week=week.isoformat())
    except PastWeek:
        return HttpResponse("Aquesta setmana és només de consulta.", status=403)
    except PlanningConflict:
        return HttpResponse("El contingut ha canviat. Actualitza la pàgina abans de tornar-ho a provar.", status=409)
    except (ValueError, TypeError, KeyError):
        return HttpResponse("No s’ha pogut completar l’acció.", status=400)
    except (DatabaseError, Rollover):
        return unavailable()

from uuid import uuid4
from menus.application.dishes import DishConflict, create_dish, update_dish
from menus.domain.dish_edit import DishInput
from menus.infrastructure.django_dishes import DjangoDishRepository


@require_http_methods(["GET"])
def catalogue(request):
    archived = request.GET.get("archived") == "1"
    query = request.GET.get("q", "")
    category = request.GET.get("category", "")
    try:
        records = DishRecord.objects.filter(archived=archived).select_related("primary_category").prefetch_related("secondary_categories")
        from menus.domain.recommendations import search_key
        dishes = [d for d in records if search_key(query) in search_key(d.name) and
                  (not category or category == d.primary_category_id or category in {c.category_id for c in d.secondary_categories.all()})]
        return render(request, "menus/catalogue.html", {"dishes": dishes, "archived": archived, "query": query, "category": category, "categories": DjangoTemplateRepository().categories().items()})
    except DatabaseError:
        return unavailable()


@require_http_methods(["GET"])
def dish_detail(request, dish_id):
    dish = DishRecord.objects.filter(pk=dish_id).select_related("primary_category").first()
    if dish is None:
        raise Http404()
    return render(request, "menus/dish.html", {"dish": dish})


@require_http_methods(["GET", "POST"])
def dish_edit(request, dish_id=None):
    dish = DishRecord.objects.filter(pk=dish_id).first() if dish_id else None
    if dish_id and dish is None:
        raise Http404()
    categories = DjangoTemplateRepository().categories()
    initial = {"name": dish.name, "primary": dish.primary_category_id,
               "secondary": list(dish.secondary_categories.values_list("category_id", flat=True)),
               "preference": dish.meal_preference, "special": dish.special_occasion,
               "version": dish.version} if dish else {"preference": "both", "secondary": [], "token": str(uuid4())}
    values, error, status = initial, None, 200
    if request.method == "POST":
        values = {"name": request.POST.get("name", ""), "primary": request.POST.get("primary", ""),
                  "secondary": request.POST.getlist("secondary"), "preference": request.POST.get("preference", ""),
                  "special": request.POST.get("special") == "on", "version": request.POST.get("version", ""),
                  "token": request.POST.get("token", "")}
        try:
            if len(values["secondary"]) != len(set(values["secondary"])):
                raise ValueError()
            data = DishInput(values["name"], values["primary"], frozenset(values["secondary"]), values["preference"], values["special"])
            repo = DjangoDishRepository()
            if dish:
                update_dish(repo, MadridClock(), dish.pk, data, int(values["version"]))
                result_id = dish.pk
            else:
                result_id = create_dish(repo, data, values["token"])
            return redirect("dish_detail", dish_id=result_id)
        except (ValueError, TypeError):
            error, status = "Revisa les dades del plat.", 400
        except DishConflict:
            error, status = "El contingut ha canviat. Revisa les dades abans de tornar-ho a provar.", 409
        except (DatabaseError, Rollover):
            return unavailable()
    return render(request, "menus/dish_edit.html", {"dish": dish, "categories": categories.items(), "values": values, "error": error, "conflict": status == 409}, status=status)

from menus.application.dishes import set_archived


@require_http_methods(["GET", "POST"])
def dish_archive(request, dish_id, action):
    if action not in ("archive", "restore"):
        raise Http404()
    dish = DishRecord.objects.filter(pk=dish_id).first()
    if not dish:
        raise Http404()
    if request.method == "POST":
        try:
            version = int(request.POST.get("version", ""))
            if request.POST.get("confirm") == "yes":
                set_archived(DjangoDishRepository(), dish_id, version, action == "archive")
                return redirect("dish_detail", dish_id=dish_id)
            if version != dish.version:
                raise DishConflict()
        except (ValueError, TypeError):
            return HttpResponse("Versió invàlida.", status=400)
        except DishConflict:
            return HttpResponse("El contingut ha canviat. Actualitza la pàgina abans de tornar-ho a provar.", status=409)
        except DatabaseError:
            return unavailable()
    return render(request, "menus/dish_archive.html", {"dish": dish, "action": action})

from menus.application.recipes import save_recipe
from menus.domain.recipe import recipe_content, validate_content
from menus.models import RecipeRecord


@require_http_methods(["GET"])
def recipe_view(request, dish_id):
    try:
        with transaction.atomic():
            dish = DishRecord.objects.filter(pk=dish_id).first()
            if not dish:
                raise Http404()
            recipe = RecipeRecord.objects.filter(dish_id=dish_id).first()
    except DatabaseError:
        return unavailable()
    content = (recipe.published or recipe.draft) if recipe else None
    try:
        if recipe and recipe.published is not None:
            validate_content(recipe.published, True)
        if recipe and recipe.draft is not None:
            validate_content(recipe.draft)
    except ValueError:
        return unavailable()
    return render(request, "menus/recipe.html", {"dish": dish, "recipe": recipe, "content": content})


@require_http_methods(["GET", "POST"])
def recipe_editor(request, dish_id, week=None, day=None, meal=None, intent=None):
    if intent and request.method != "POST":
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(["POST"])
    context = None
    if week is not None:
        week = parse_week(week)
        if day not in range(7) or meal not in MEALS:
            raise Http404()
        menu = DjangoPlanningRepository().get(week)
        if not menu or menu.slots[(day, meal)].state != "selected":
            raise Http404()
        dish_id = menu.slots[(day, meal)].dish["dish_id"]
        if week < monday(MadridClock().today()):
            return HttpResponse("Aquesta setmana és només de consulta.", status=403)
        context = (week, (day, meal))
    dish = DishRecord.objects.filter(pk=dish_id).first()
    if not dish:
        raise Http404()
    recipe = RecipeRecord.objects.filter(dish_id=dish_id).first()
    content = (recipe.draft or recipe.published) if recipe else None
    try:
        if recipe and recipe.published is not None:
            validate_content(recipe.published, True)
        if recipe and recipe.draft is not None:
            validate_content(recipe.draft)
    except ValueError:
        return unavailable()
    lines = content["ingredients"] if content else []
    values = {"preparation": content["preparation"] if content else "", "lines": lines or [{}], "version": dish.version}
    error, status = None, 200
    if request.method == "POST":
        names = request.POST.getlist("name")
        quantities = request.POST.getlist("quantity")
        units = request.POST.getlist("unit")
        notes = request.POST.getlist("note")
        tastes = set(request.POST.getlist("taste"))
        lines = [{"name": name, "quantity": quantities[i] if i < len(quantities) else "", "unit": units[i] if i < len(units) else "", "note": notes[i] if i < len(notes) else "", "taste": str(i) in tastes} for i, name in enumerate(names)]
        values = {"preparation": request.POST.get("preparation", ""), "lines": lines, "version": request.POST.get("version", "")}
        action = intent or request.POST.get("action")
        if action == "review_discard":
            return render(request, "menus/recipe_discard.html", {"dish": dish, "values": values, "week": week, "day": day, "meal": meal})
        if action == "continue":
            pass
        elif action == "add_row":
            lines.append({})
        elif action and action.startswith("remove_row:"):
            try:
                lines.pop(int(action.split(":", 1)[1]))
            except (ValueError, IndexError):
                error, status = "Fila invàlida.", 400
        elif action in ("draft", "publish"):
            try:
                if context and int(request.POST.get("dish_id", "0")) != dish_id:
                    raise PlanningConflict()
                cleaned = [line for line in lines if any((line["name"].strip(), line["quantity"].strip(), line["unit"], line["note"].strip(), line["taste"]))]
                content = recipe_content(values["preparation"], cleaned, action == "publish")
                save_recipe(DjangoDishRepository(), MadridClock(), dish_id, int(values["version"]), content, action == "publish", context)
                messages.success(request, "Recepta publicada" if action == "publish" else "Esborrany desat")
                if context:
                    return redirect("slot_detail", week=week.isoformat(), day=day, meal=meal)
                return redirect("recipe_view", dish_id=dish_id)
            except (ValueError, TypeError):
                error, status = "Revisa la preparació i els ingredients. Per publicar, completa totes les quantitats o marca «Al gust».", 400
            except (DishConflict, PlanningConflict):
                error, status = "El contingut ha canviat. Revisa la recepta abans de tornar-ho a provar.", 409
            except PastWeek:
                return HttpResponse("Aquesta setmana és només de consulta.", status=403)
            except (DatabaseError, Rollover):
                error, status = "No s’ha pogut desar. Revisa les dades abans de tornar-ho a provar.", 503
        else:
            error, status = "Acció invàlida.", 400
    return render(request, "menus/recipe_edit.html", {"dish": dish, "values": values, "error": error, "conflict": status == 409, "week": week, "day": day, "meal": meal}, status=status)

from menus.application.shopping import mutate_shopping
from menus.infrastructure.django_shopping import DjangoShoppingRepository, ShoppingConflict


@require_http_methods(["GET"])
def current_shopping(request):
    return redirect("shopping_week", week=monday(MadridClock().today()).isoformat())


@require_http_methods(["GET"])
def shopping_view(request, week):
    week = parse_week(week)
    try:
        with transaction.atomic():
            view = DjangoShoppingRepository().read(week)
            if view is None:
                return render(request, "menus/shopping.html", {"week": week})
            menu, state, rows, pending, incomplete, orphans = view
            manual = list(state.manual_items.all()) if state else []
        return render(request, "menus/shopping.html", {"week": week, "menu": menu, "state": state, "rows": rows, "pending": pending, "incomplete": incomplete, "orphans": orphans, "manual": manual, "editable": week >= monday(MadridClock().today()), "token": str(uuid4())})
    except (DatabaseError, ValueError, KeyError, ArithmeticError):
        return unavailable()


@require_POST
def shopping_action(request, week, action):
    week = parse_week(week)
    if action not in ("manual_add", "manual_edit", "manual_remove", "manual_check", "adjust", "reset", "check"):
        raise Http404()
    try:
        data = {key: request.POST.get(key, "") for key in ("name", "quantity", "unit", "token", "id", "key", "family", "checked")}
        if action == "manual_remove" and request.POST.get("confirm") != "yes":
            with transaction.atomic():
                view = DjangoShoppingRepository().read(week)
                if view is None or not view[1]:
                    raise ValueError("Missing item")
                if view[0].version != int(request.POST.get("menu_version", "")) or view[1].version != int(request.POST.get("overlay_version", "")):
                    raise ShoppingConflict()
                item = view[1].manual_items.filter(pk=data["id"]).first()
                if not item:
                    raise ValueError("Missing item")
                if week < monday(MadridClock().today()):
                    raise PastWeek()
                return render(request, "menus/manual_confirm.html", {"week": week, "item": item, "menu_version": view[0].version, "overlay_version": view[1].version})
        mutate_shopping(DjangoShoppingRepository(), MadridClock(), week, int(request.POST.get("menu_version", "")), int(request.POST.get("overlay_version", "")), action, data)
        return redirect("shopping_week", week=week.isoformat())
    except PastWeek:
        return HttpResponse("Aquesta setmana és només de consulta.", status=403)
    except ShoppingConflict:
        try:
            with transaction.atomic():
                current_view = DjangoShoppingRepository().read(week)
                current_rows = current_view[2] if current_view else []
                current_manual = list(current_view[1].manual_items.all()) if current_view and current_view[1] else []
        except (DatabaseError, ValueError):
            return unavailable()
        return render(request, "menus/shopping_error.html", {"week": week, "action": action, "data": data,
                      "error": "El contingut ha canviat. Revisa les dades abans de tornar-ho a provar.", "conflict": True,
                      "current_rows": current_rows, "current_manual": current_manual}, status=409)
    except (ValueError, TypeError, KeyError):
        return render(request, "menus/shopping_error.html", {"week": week, "action": action, "data": data,
                      "error": "Revisa les dades del producte.", "menu_version": request.POST.get("menu_version", ""),
                      "overlay_version": request.POST.get("overlay_version", "")}, status=400)
    except (DatabaseError, Rollover):
        return render(request, "menus/shopping_error.html", {"week": week, "action": action, "data": data,
                      "error": "No s’ha pogut completar l’acció. Revisa la llista abans de tornar-ho a provar.",
                      "menu_version": request.POST.get("menu_version", ""),
                      "overlay_version": request.POST.get("overlay_version", "")}, status=503)


@require_http_methods(["GET"])
def healthz(request):
    from django.db import connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM django_migrations LIMIT 1")
            cursor.fetchone()
        return HttpResponse("OK", content_type="text/plain")
    except DatabaseError:
        return HttpResponse("No disponible", status=503, content_type="text/plain")


@require_http_methods(["GET", "POST"])
def shopping_form(request, week, action, item_id=None):
    week = parse_week(week)
    if action not in ("manual_add", "manual_edit", "manual_remove", "adjust"):
        raise Http404()
    if request.method == "POST":
        if item_id is not None and request.POST.get("id") != str(item_id):
            return HttpResponse("Producte invàlid.", status=400)
        return shopping_action(request, week.isoformat(), action)
    try:
        with transaction.atomic():
            view = DjangoShoppingRepository().read(week)
            if not view:
                raise Http404()
            menu, state, rows, _, _, _ = view
            if week < monday(MadridClock().today()):
                return HttpResponse("Aquesta setmana és només de consulta.", status=403)
            item = state.manual_items.filter(pk=item_id).first() if state and item_id is not None else None
            if item_id is not None and item is None:
                raise Http404()
            key, family = request.GET.get("key", ""), request.GET.get("family", "")
            row = next((candidate for candidate in rows if candidate["key"] == (key, family)), None)
            if action == "adjust" and (not row or family == "taste"):
                raise Http404()
        return render(request, "menus/shopping_form.html", {"week": week, "menu": menu, "state": state,
                      "action": action, "item": item, "row": row, "token": str(uuid4())})
    except (DatabaseError, ValueError, KeyError):
        return unavailable()
