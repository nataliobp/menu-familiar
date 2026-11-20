from django.contrib import messages
from django.db import DatabaseError, transaction
from django.http import Http404, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from menus.application.catalogue_queries import get_dish, get_recipe
from menus.application.dishes import DishConflict
from menus.application.errors import DataIntegrityError
from menus.application.planning import PastWeek, PlanningConflict, Rollover, get_menu
from menus.application.recipes import save_recipe
from menus.domain.planning import monday
from menus.domain.recipe import MAX_INGREDIENTS, MAX_PREPARATION_LENGTH, recipe_content, validate_content
from menus.infrastructure.django_catalogue_queries import DjangoCatalogueQueries
from menus.infrastructure.django_dishes import DjangoDishRepository
from menus.infrastructure.django_planning import DjangoPlanningRepository, MadridClock
from menus.web.common import MEALS, parse_week, unavailable
from menus.web.presentation import recipe_read_context


@require_http_methods(["GET"])
def recipe_view(request, dish_id):
    try:
        with transaction.atomic():
            dish = get_dish(DjangoCatalogueQueries(), dish_id)
            if not dish:
                raise Http404()
            recipe = get_recipe(DjangoCatalogueQueries(), dish_id)
        context = recipe_read_context(recipe)
    except (DatabaseError, ValueError):
        return unavailable()
    return render(request, "menus/recipe.html", {"dish": dish, **context})


def posted_recipe(request):
    fields = {name: request.POST.getlist(name) for name in ("name", "quantity", "unit", "note")}
    tastes = set(request.POST.getlist("taste"))
    lines = []
    for index, name in enumerate(fields["name"]):
        line = {key: fields[key][index] if index < len(fields[key]) else "" for key in ("quantity", "unit", "note")}
        lines.append({**line, "name": name, "taste": str(index) in tastes})
    return {"preparation": request.POST.get("preparation", ""), "lines": lines, "version": request.POST.get("version", "")}


def editor_content(dish_id, context, submitted_dish_id):
    with transaction.atomic():
        if context is not None:
            week, position = context
            menu = get_menu(DjangoPlanningRepository(), week)
            slot = menu.slots[position] if menu else None
            dish_id = slot.dish["dish_id"] if slot and slot.state == "selected" else None
            if submitted_dish_id is not None and (dish_id is None or submitted_dish_id != str(dish_id)):
                raise PlanningConflict()
            if dish_id is None:
                raise Http404()
            if week < monday(MadridClock().today()):
                raise PastWeek()
        queries = DjangoCatalogueQueries()
        dish = get_dish(queries, dish_id)
        if dish is None:
            raise Http404()
        recipe = get_recipe(queries, dish_id)
    try:
        if recipe and recipe.published is not None:
            validate_content(recipe.published, True)
        if recipe and recipe.draft is not None:
            validate_content(recipe.draft)
    except ValueError as exc:
        raise DataIntegrityError("Invalid stored recipe") from exc
    return dish, (recipe.draft or recipe.published) if recipe else None


@require_http_methods(["GET", "POST"])
def recipe_editor(request, dish_id, week=None, day=None, meal=None, intent=None):
    submitted = request.method == "POST"
    if intent and not submitted:
        return HttpResponseNotAllowed(["POST"])
    context = None
    if week is not None:
        week = parse_week(week)
        if day not in range(7) or meal not in MEALS:
            raise Http404()
        context = (week, (day, meal))
    submitted_dish_id = request.POST.get("dish_id", "") if submitted else None
    values = posted_recipe(request) if submitted else None
    fields = {"week": week, "day": day, "meal": meal, "values": values,
              "editor_dish_id": submitted_dish_id if context else dish_id}
    try:
        return edit_recipe(request, fields, context, dish_id, submitted_dish_id, intent)
    except (DatabaseError, DataIntegrityError):
        if not submitted:
            return unavailable()
        return render(request, "menus/recipe_edit.html", {
            **fields, "retry_read": True,
            "error": "No s’ha pogut llegir la recepta. Torna-la a obrir per continuar editant."
        }, status=503)
    except (PlanningConflict, PastWeek, Http404) as exc:
        if not submitted:
            if isinstance(exc, PastWeek):
                return HttpResponse("Aquesta setmana és només de consulta.", status=403)
            raise
        if isinstance(exc, PastWeek):
            error, status = "Aquesta setmana és només de consulta.", 403
        elif isinstance(exc, Http404):
            error, status = "Aquest plat ja no està disponible.", 404
        else:
            error, status = "El plat de l’àpat ha canviat.", 409
        return render(request, "menus/recipe_edit.html", {
            **fields, "target_unavailable": True, "target_changed": status == 409, "error": error,
        }, status=status)


def edit_recipe(request, fields, context, dish_id, submitted_dish_id, intent):
    dish, saved_content = editor_content(dish_id, context, submitted_dish_id)
    fields.update(dish=dish, editor_dish_id=dish.id)
    dish_id = dish.id
    week, day, meal = fields["week"], fields["day"], fields["meal"]
    values = fields["values"]
    error, status, reviewed = None, 200, False
    if request.method == "POST":
        lines = values["lines"]
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
        elif action == "retry_read":
            if values["version"] != str(dish.version):
                error, status = "El contingut ha canviat. Revisa la recepta abans de tornar-ho a provar.", 409
        elif action == "continue":
            pass
        elif action == "add_row":
            if len(lines) >= MAX_INGREDIENTS:
                values["ingredients_error"] = f"La recepta admet fins a {MAX_INGREDIENTS} ingredients."
                error, status = "Revisa els ingredients.", 400
            else:
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
                publish = action == "publish"
                cleaned = [line for line in lines if any((line["name"].strip(), line["quantity"].strip(), line["unit"], line["note"].strip(), line["taste"]))]
                preparation = values["preparation"]
                if len(preparation) > MAX_PREPARATION_LENGTH:
                    values["preparation_error"] = f"La preparació admet fins a {MAX_PREPARATION_LENGTH} caràcters."
                elif publish and not preparation.strip():
                    values["preparation_error"] = "Escriu la preparació per publicar la recepta."
                if len(cleaned) > MAX_INGREDIENTS:
                    values["ingredients_error"] = f"La recepta admet fins a {MAX_INGREDIENTS} ingredients."
                elif publish and not cleaned:
                    values["ingredients_error"] = "Afegeix un ingredient per publicar la recepta."
                for line in cleaned:
                    try:
                        recipe_content("Preparació", [line], publish)
                    except ValueError:
                        line["error"] = "Revisa el nom, la quantitat, la unitat i l’opció «Al gust»."
                if values.get("preparation_error") or values.get("ingredients_error") or any(line.get("error") for line in lines):
                    raise ValueError()
                content = recipe_content(preparation, cleaned, publish)
                save_recipe(DjangoDishRepository(), MadridClock(), dish_id, int(values["version"]), content, publish, context)
                messages.success(request, "Recepta publicada" if publish else "Esborrany desat")
                if context:
                    return redirect("slot_detail", week=week.isoformat(), day=day, meal=meal)
                return redirect("dish_detail", dish_id=dish_id)
            except (ValueError, TypeError):
                error, status = "Revisa la preparació i els ingredients. Per publicar, completa totes les quantitats o marca «Al gust».", 400
            except (DishConflict, PlanningConflict):
                _, saved_content = editor_content(dish_id, context, submitted_dish_id)
                error, status = "El contingut ha canviat. Revisa la recepta abans de tornar-ho a provar.", 409
            except (DatabaseError, Rollover):
                error, status = "No s’ha pogut desar. Revisa les dades abans de tornar-ho a provar.", 503
        else:
            error, status = "Acció invàlida.", 400
    else:
        lines = [{**line, "quantity": (line["quantity"] or "").replace(".", ",")}
                 for line in saved_content["ingredients"]] if saved_content else []
        values = {"preparation": saved_content["preparation"] if saved_content else "",
                  "lines": lines or [{}], "version": dish.version}
    return render(request, "menus/recipe_edit.html", {
        **fields, "values": values, "error": error, "conflict": status == 409,
        "reviewed": reviewed, "current_content": saved_content,
    }, status=status)
