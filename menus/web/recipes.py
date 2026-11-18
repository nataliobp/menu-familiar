from django.contrib import messages
from django.db import DatabaseError, transaction
from django.http import Http404, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from menus.application.catalogue_queries import get_dish, get_recipe
from menus.application.dishes import DishConflict
from menus.application.planning import PastWeek, PlanningConflict, Rollover, get_menu
from menus.application.recipes import save_recipe
from menus.domain.planning import monday
from menus.domain.recipe import recipe_content, validate_content
from menus.infrastructure.django_catalogue_queries import DjangoCatalogueQueries
from menus.infrastructure.django_dishes import DjangoDishRepository
from menus.infrastructure.django_planning import DjangoPlanningRepository, MadridClock
from menus.web.common import MEALS, parse_week, unavailable


@require_http_methods(["GET"])
def recipe_view(request, dish_id):
    try:
        with transaction.atomic():
            dish = get_dish(DjangoCatalogueQueries(), dish_id)
            if not dish:
                raise Http404()
            recipe = get_recipe(DjangoCatalogueQueries(), dish_id)
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
        return HttpResponseNotAllowed(["POST"])
    with transaction.atomic():
        context = None
        if week is not None:
            week = parse_week(week)
            if day not in range(7) or meal not in MEALS:
                raise Http404()
            menu = get_menu(DjangoPlanningRepository(), week)
            slot = menu.slots[(day, meal)] if menu else None
            dish_id = slot.dish["dish_id"] if slot and slot.state == "selected" else None
            if request.method == "POST" and (dish_id is None or request.POST.get("dish_id") != str(dish_id)):
                return render(request, "menus/action_error.html", {"week": week}, status=409)
            if dish_id is None:
                raise Http404()
            if week < monday(MadridClock().today()):
                return HttpResponse("Aquesta setmana és només de consulta.", status=403)
            context = (week, (day, meal))
        dish = get_dish(DjangoCatalogueQueries(), dish_id)
        if not dish:
            raise Http404()
        recipe = get_recipe(DjangoCatalogueQueries(), dish_id)
    content = (recipe.draft or recipe.published) if recipe else None
    try:
        if recipe and recipe.published is not None:
            validate_content(recipe.published, True)
        if recipe and recipe.draft is not None:
            validate_content(recipe.draft)
    except ValueError:
        return unavailable()
    saved_content = content
    lines = [{**line, "quantity": (line["quantity"] or "").replace(".", ",")}
             for line in content["ingredients"]] if content else []
    values = {"preparation": content["preparation"] if content else "", "lines": lines or [{}], "version": dish.version}
    error, status, reviewed = None, 200, False
    if request.method == "POST":
        names = request.POST.getlist("name")
        quantities = request.POST.getlist("quantity")
        units = request.POST.getlist("unit")
        notes = request.POST.getlist("note")
        tastes = set(request.POST.getlist("taste"))
        lines = [{"name": name, "quantity": quantities[i] if i < len(quantities) else "", "unit": units[i] if i < len(units) else "", "note": notes[i] if i < len(notes) else "", "taste": str(i) in tastes} for i, name in enumerate(names)]
        values = {"preparation": request.POST.get("preparation", ""), "lines": lines, "version": request.POST.get("version", "")}
        actions = request.POST.getlist("action")
        if len(actions) > 1:
            return HttpResponse("Acció invàlida.", status=400)
        posted_action = actions[0] if actions else None
        if intent and posted_action is not None and posted_action != intent:
            return HttpResponse("Acció invàlida.", status=400)
        action = intent or posted_action
        if action in ("draft", "publish") and intent is None:
            return HttpResponse("Acció invàlida.", status=400)
        if action == "review_discard":
            return render(request, "menus/recipe_discard.html", {"dish": dish, "values": values, "week": week, "day": day, "meal": meal})
        if action == "review":
            reviewed = True
            values["version"] = dish.version
        elif action == "continue":
            pass
        elif action == "add_row":
            lines.append({})
        elif action and action.startswith("remove_row:"):
            try:
                index = int(action.split(":", 1)[1])
                if not 0 <= index < len(lines):
                    raise ValueError()
                lines.pop(index)
            except (ValueError, IndexError):
                error, status = "Fila invàlida.", 400
        elif action in ("draft", "publish"):
            try:
                cleaned = [line for line in lines if any((line["name"].strip(), line["quantity"].strip(), line["unit"], line["note"].strip(), line["taste"]))]
                for line in cleaned:
                    try:
                        recipe_content("Preparació", [line], action == "publish")
                    except ValueError:
                        line["error"] = "Revisa el nom, la quantitat, la unitat i l’opció «Al gust»."
                if any(line.get("error") for line in lines):
                    raise ValueError()
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
    return render(request, "menus/recipe_edit.html", {"dish": dish, "values": values, "error": error, "conflict": status == 409, "reviewed": reviewed, "current_content": saved_content, "week": week, "day": day, "meal": meal}, status=status)
