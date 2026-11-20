from django.contrib import messages
from django.db import DatabaseError, transaction
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from menus.application.template import TemplateConflict, get_template, set_template_category
from menus.infrastructure.django_template import DjangoTemplateRepository
from menus.web.common import DAYS, MEALS, unavailable
from menus.web.presentation import category_label, category_options


@require_http_methods(["GET"])
def template_view(request):
    try:
        template, categories = get_template(DjangoTemplateRepository())
        days = []
        for day, label in enumerate(DAYS):
            meals = []
            for meal, meal_label in MEALS.items():
                key = template.slots[day, meal] or ""
                meals.append((meal, meal_label, key, category_label(key, categories.get(key))))
            days.append((day, label, meals))
        return render(request, "menus/template.html", {
            "days": days, "version": template.version, "categories": category_options(categories),
        })
    except (DatabaseError, ValueError, KeyError):
        return unavailable()


@require_http_methods(["GET", "POST"])
def template_edit(request, day, meal):
    if day not in range(7) or meal not in MEALS:
        raise Http404()
    enhanced = request.method == "POST" and request.headers.get("Accept") == "application/json"
    repo = DjangoTemplateRepository()
    try:
        with transaction.atomic():
            template, categories = get_template(repo)
        current_key = template.slots[day, meal]
        current_label = category_label(current_key, categories.get(current_key))
        selected = current_key or ""
        version_value = str(template.version)
        error = None
        status = 200
        if request.method == "POST":
            version_value = request.POST.get("version", "")
            choices = request.POST.getlist("category")
            selected = choices[0] if len(choices) == 1 else ""
            try:
                if len(choices) != 1:
                    raise ValueError()
                version = int(request.POST.get("version", ""))
                if not enhanced and request.POST.get("action") == "review":
                    return render(request, "menus/template_edit.html", {
                        "day": DAYS[day], "meal": MEALS[meal], "categories": category_options(categories),
                        "selected": selected, "version": template.version,
                        "current_label": current_label,
                    })
                saved = set_template_category(repo, (day, meal), selected or None, version)
                if enhanced:
                    return JsonResponse({"version": saved.version, "category": selected,
                                         "label": category_label(selected, categories.get(selected))})
                messages.success(request, "Plantilla actualitzada")
                return redirect("weekly_template")
            except (ValueError, TypeError):
                error, status = "Selecciona una categoria vàlida.", 400
            except TemplateConflict:
                error, status = "La plantilla ha canviat. Revisa la selecció i torna-ho a provar.", 409
        if enhanced:
            if status == 409:
                error = "La plantilla ha canviat. Actualitza-la i revisa la selecció."
            return JsonResponse({"error": error}, status=status)
        return render(request, "menus/template_edit.html", {
            "day": DAYS[day], "meal": MEALS[meal], "categories": category_options(categories),
            "selected": selected, "selected_label": category_label(selected, categories.get(selected)),
            "current_label": current_label,
            "version": version_value, "error": error, "conflict": status == 409,
        }, status=status)
    except (DatabaseError, ValueError, KeyError):
        return unavailable()
