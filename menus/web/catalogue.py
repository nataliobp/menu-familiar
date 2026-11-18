from uuid import uuid4

from django.db import DatabaseError, transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from menus.application.catalogue_queries import browse_dishes, get_dish
from menus.application.dishes import DishConflict, create_dish, set_archived, update_dish
from menus.application.planning import Rollover
from menus.domain.dish_edit import DishInput
from menus.infrastructure.django_catalogue_queries import DjangoCatalogueQueries
from menus.infrastructure.django_dishes import DjangoDishRepository
from menus.infrastructure.django_planning import MadridClock
from menus.infrastructure.django_template import DjangoTemplateRepository
from menus.web.common import MEALS, filter_error, unavailable


@require_http_methods(["GET"])
def catalogue(request):
    archive_filter = request.GET.get("archived", "0")
    archived = archive_filter == "1"
    query = request.GET.get("q", "")
    category = request.GET.get("category", "")
    try:
        with transaction.atomic():
            categories = DjangoTemplateRepository().categories()
            error = filter_error(query, category, categories)
            if archive_filter not in {"0", "1"}:
                error = "Selecciona plats actius o arxivats."
            dishes = [] if error else browse_dishes(DjangoCatalogueQueries(), archived, category, query)
        return render(request, "menus/catalogue.html", {
            "dishes": dishes, "archived": archived, "query": query, "category": category,
            "categories": categories.items(), "error": error,
        }, status=400 if error else 200)
    except DatabaseError:
        return unavailable()


@require_http_methods(["GET"])
def dish_detail(request, dish_id):
    try:
        with transaction.atomic():
            dish = get_dish(DjangoCatalogueQueries(), dish_id)
            if dish is None:
                raise Http404()
            categories = DjangoTemplateRepository().categories()
            secondary_labels = [categories[key] for key in dish.secondary_categories]
        return render(request, "menus/dish.html", {"dish": dish, "secondary_labels": secondary_labels})
    except (DatabaseError, ValueError, KeyError):
        return unavailable()


@require_http_methods(["GET", "POST"])
def dish_edit(request, dish_id=None):
    with transaction.atomic():
        dish = get_dish(DjangoCatalogueQueries(), dish_id) if dish_id is not None else None
        if dish_id is not None and dish is None:
            raise Http404()
        categories = DjangoTemplateRepository().categories()
    initial = {"name": dish.name, "primary": dish.primary_category_id,
               "secondary": list(dish.secondary_categories),
               "preference": dish.meal_preference, "special": dish.special_occasion,
               "version": dish.version} if dish else {"preference": "both", "secondary": [], "token": str(uuid4())}
    values, error, status = initial, None, 200
    if request.method == "POST":
        values = {"name": request.POST.get("name", ""), "primary": request.POST.get("primary", ""),
                  "secondary": request.POST.getlist("secondary"), "preference": request.POST.get("preference", ""),
                  "special": request.POST.get("special") == "on", "version": request.POST.get("version", ""),
                  "token": request.POST.get("token", "")}
        try:
            if dish and request.POST.get("action") == "review":
                values["version"] = dish.version
                return render(request, "menus/dish_edit.html", {
                    "dish": dish, "categories": categories.items(), "values": values,
                    "reviewed": True,
                })
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
            error, status = "No s’ha pogut desar. Revisa les dades abans de tornar-ho a provar.", 503
    field_errors = {}
    if status == 400:
        if not values["name"].strip() or len(values["name"].strip()) > 200:
            field_errors["name"] = "Escriu un nom de fins a 200 caràcters."
        if values["primary"] not in categories:
            field_errors["primary"] = "Selecciona una categoria principal."
        secondary = values["secondary"]
        if set(secondary) - categories.keys() or len(set(secondary)) != len(secondary) or values["primary"] in secondary:
            field_errors["secondary"] = "Selecciona categories secundàries diferents de la principal."
        if values["preference"] not in {"both", *MEALS}:
            field_errors["preference"] = "Selecciona un àpat preferent vàlid."
    return render(request, "menus/dish_edit.html", {
        "dish": dish, "categories": categories.items(), "values": values, "error": error,
        "conflict": status == 409, "field_errors": field_errors,
    }, status=status)



@require_http_methods(["GET", "POST"])
def dish_archive(request, dish_id, action):
    if action not in ("archive", "restore"):
        raise Http404()
    dish = get_dish(DjangoCatalogueQueries(), dish_id)
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
            return render(request, "menus/action_error.html", {}, status=409)
        except DatabaseError:
            return unavailable()
    return render(request, "menus/dish_archive.html", {"dish": dish, "action": action})
