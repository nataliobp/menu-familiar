from django.contrib import messages
from django.db import DatabaseError, transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from menus.application.template import TemplateConflict, get_template, set_template_category
from menus.infrastructure.django_template import DjangoTemplateRepository
from menus.web.common import DAYS, MEALS, unavailable


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
        with transaction.atomic():
            template, categories = get_template(repo)
        selected = template.slots[(day, meal)] or ""
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
                if request.POST.get("action") == "review":
                    return render(request, "menus/template_edit.html", {
                        "day": DAYS[day], "meal": MEALS[meal], "categories": categories.items(),
                        "selected": selected, "version": template.version,
                        "current_label": categories.get(template.slots[(day, meal)], "Lliure"),
                    })
                set_template_category(repo, (day, meal), selected or None, version)
                messages.success(request, "Plantilla actualitzada")
                return redirect("weekly_template")
            except (ValueError, TypeError):
                error, status = "Selecciona una categoria vàlida.", 400
            except TemplateConflict:
                error, status = "La plantilla ha canviat. Revisa la selecció i torna-ho a provar.", 409
        return render(request, "menus/template_edit.html", {"day": DAYS[day], "meal": MEALS[meal], "categories": categories.items(), "selected": selected, "selected_label": categories.get(selected, "Lliure"), "current_label": categories.get(template.slots[(day, meal)], "Lliure"), "version": version_value, "error": error, "conflict": status == 409}, status=status)
    except (DatabaseError, ValueError, KeyError):
        return unavailable()
