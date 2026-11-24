from hashlib import sha256
from uuid import uuid4

from django.contrib import messages
from django.core import signing
from django.db import DatabaseError
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from menus.application.dishes import DishConflict, create_dish_with_recipe
from menus.application.errors import DataIntegrityError
from menus.application.planning import PastWeek, PlanningConflict, Rollover
from menus.application.recipes import save_recipe
from menus.domain.categories import CATEGORIES
from menus.infrastructure.django_dishes import DjangoDishRepository
from menus.infrastructure.django_planning import MadridClock
from menus.web.presentation import category_label
from menus.web.recipe_import_format import RecipeImportError, import_prompt, parse_recipe_import
from menus.web.recipes import editor_content, recipe_slot_context


PREVIEW_SALT = "menus.recipe-import.preview"
CATEGORY_NAMES = dict(CATEGORIES)


def _preview(request, fields, dish, saved_content, action):
    raw = fields["raw"].replace("\r\n", "\n").replace("\r", "\n")
    imported_dish, content = parse_recipe_import(raw)
    binding = [request.path, dish.id if dish else None, dish.version if dish else None, sha256(raw.encode()).hexdigest()]

    token = request.POST.get("preview_token", "")
    if action == "preview":
        receipt = None
        try:
            previous = signing.loads(token, salt=PREVIEW_SALT)
        except signing.BadSignature:
            previous = None
        # Rechecking an unchanged new dish should keep its creation receipt.
        if dish is None:
            receipt = previous[4] if previous and previous[:4] == binding else str(uuid4())
        token = signing.dumps([*binding, receipt], salt=PREVIEW_SALT)
    elif action == "save":
        reviewed = signing.loads(token, salt=PREVIEW_SALT)
        if reviewed[:4] != binding:
            raise DishConflict()
        receipt = reviewed[4]
    else:
        raise RecipeImportError("Tria una acció vàlida.")

    primary = dish.primary_category_id if dish else imported_dish.primary_category
    secondary = dish.secondary_categories if dish else imported_dish.secondary_categories
    fields.update(
        preview_token=token, content=content, requires_confirmation=saved_content is not None,
        preview_name=dish.name if dish else imported_dish.name,
        primary_label=category_label(primary, CATEGORY_NAMES[primary]),
        secondary_labels=[label for key, label in CATEGORIES if key in secondary],
    )
    return imported_dish, content, receipt


@require_http_methods(["GET", "POST"])
def recipe_import(request, dish_id=None, week=None, day=None, meal=None):
    slot_context = recipe_slot_context(week, day, meal) if week is not None else None
    slot_args = (week, day, meal)
    if slot_context:
        back_url = reverse("slot_recipe_edit", args=slot_args)
    elif dish_id is not None:
        back_url = reverse("recipe_edit", args=[dish_id])
    else:
        back_url = reverse("dish_create")
    fields = {"back_url": back_url, "week": slot_context[0] if slot_context else None,
              "raw": request.POST.get("recipe_json", "")}
    status = 200
    try:
        dish, saved_content = (None, None)
        if dish_id is not None or slot_context:
            dish, saved_content = editor_content(dish_id, slot_context, None)
        fields.update(dish=dish, prompt=import_prompt(dish))
        if request.method == "POST":
            action = request.POST.get("action")
            imported_dish, content, receipt = _preview(request, fields, dish, saved_content, action)
            if action == "save":
                if saved_content is not None and request.POST.get("confirm_replace") != "yes":
                    raise RecipeImportError("Confirma que vols substituir el contingut de treball de la recepta.")
                repo, clock = DjangoDishRepository(), MadridClock()
                if dish:
                    save_recipe(repo, clock, dish.id, dish.version, content, context=slot_context)
                    result_id = dish.id
                else:
                    result_id = create_dish_with_recipe(repo, clock, imported_dish, receipt, content)
                messages.success(request, "Esborrany desat")
                if slot_context:
                    return redirect("slot_recipe_edit", *slot_args)
                return redirect("recipe_edit", dish_id=result_id)
    except signing.BadSignature:
        fields["error"], status = "Fes una previsualització abans de desar la recepta.", 400
    except RecipeImportError as exc:
        fields["error"], status = str(exc), 400
    except (DishConflict, PlanningConflict):
        fields.pop("preview_token", None)
        fields["error"], status = "El JSON o el plat ha canviat. Torna a previsualitzar la recepta abans de desar-la.", 409
    except PastWeek:
        fields["error"], status = "Aquesta setmana és només de consulta.", 403
        fields["target_unavailable"] = True
        fields["back_url"] = reverse("slot_detail", args=slot_args)
    except Http404:
        if request.method == "GET":
            raise
        fields["error"], status = "Aquest plat ja no està disponible.", 404
        fields["target_unavailable"] = True
        fields["back_url"] = reverse("catalogue")
    except (DatabaseError, DataIntegrityError, Rollover, ValueError):
        fields["error"], status = "No s’ha pogut completar l’operació. Torna-ho a provar.", 503
        if "prompt" not in fields:
            fields["prompt"] = import_prompt()
    return render(request, "menus/recipe_import.html", fields, status=status)
