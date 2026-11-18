from datetime import date, timedelta

from django.contrib import messages
from django.db import DatabaseError, transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from menus.application.catalogue_queries import picker_dishes
from menus.application.planning import PastWeek, PlanningConflict, Rollover, change_menu, create_menu, get_menu, move_or_undo
from menus.domain.planning import MAX_WEEK_START, monday
from menus.infrastructure.django_catalogue_queries import DjangoCatalogueQueries
from menus.infrastructure.django_planning import DjangoPlanningRepository, MadridClock
from menus.web.common import DAYS, MEALS, filter_error, parse_week, unavailable


@require_http_methods(["GET"])
def current_menu(request):
    return redirect("menu_week", week=monday(MadridClock().today()).isoformat())


@require_http_methods(["GET"])
def menu_view(request, week):
    week = parse_week(week)
    repo, clock = DjangoPlanningRepository(), MadridClock()
    try:
        with transaction.atomic():
            menu = get_menu(repo, week)
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
                      "editable": editable, "week_end": week + timedelta(days=6), "previous": week - timedelta(days=7) if week >= date.min + timedelta(days=7) else None, "next": week + timedelta(days=7) if week <= MAX_WEEK_START - timedelta(days=7) else None})
    except (DatabaseError, ValueError, KeyError):
        return unavailable()


@require_POST
def menu_create(request, week):
    week = parse_week(week)
    try:
        create_menu(DjangoPlanningRepository(), MadridClock(), week)
        messages.success(request, "Menú setmanal creat")
        return redirect("menu_week", week=week.isoformat())
    except PastWeek:
        return HttpResponse("Aquesta setmana és només de consulta.", status=403)
    except (DatabaseError, Rollover, ValueError, KeyError):
        return unavailable()


@require_http_methods(["GET"])
def menu_picker(request, week, day, meal):
    week = parse_week(week)
    if day not in range(7) or meal not in MEALS:
        raise Http404()
    repo = DjangoPlanningRepository()
    try:
        with transaction.atomic():
            menu = get_menu(repo, week)
            if not menu or week < monday(MadridClock().today()):
                raise Http404()
            slot = menu.slots[(day, meal)]
            action = request.GET.get("action", "assign")
            if action not in ("assign", "replace") or slot.state != ("pending" if action == "assign" else "selected"):
                raise Http404()
            categories = repo.template()[1]
            category = request.GET.get("category")
            mode = request.GET.get("mode")
            if mode == "all":
                category = ""
            if category is None and slot.suggestion:
                category = slot.suggestion[0]
            query = request.GET.get("q", "")
            error = filter_error(query, category, categories)
            dishes = [] if error else picker_dishes(DjangoCatalogueQueries(), meal, category, query)
        return render(request, "menus/picker.html", {"week": week, "day": day, "meal": meal, "action": action, "menu": menu, "dishes": dishes, "categories": categories.items(), "category": category, "query": query, "slot": slot, "day_label": DAYS[day], "meal_label": MEALS[meal], "error": error}, status=400 if error else 200)
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
        if action in ("assign", "replace") and not 1 <= dish_id <= 9223372036854775807:
            raise ValueError("Invalid dish identifier")
        change_menu(DjangoPlanningRepository(), MadridClock(), week, (day, meal), version, action, dish_id, request.POST.get("confirm") == "yes")
        messages.success(request, "Canvi desat")
        return redirect("menu_week", week=week.isoformat())
    except PastWeek:
        return HttpResponse("Aquesta setmana és només de consulta.", status=403)
    except PlanningConflict:
        return render(request, "menus/action_error.html", {"week": week}, status=409)
    except (ValueError, TypeError, KeyError):
        return render(request, "menus/action_error.html", {"week": week, "invalid": True}, status=400)
    except (DatabaseError, Rollover):
        return unavailable()


@require_http_methods(["GET"])
def slot_detail(request, week, day, meal):
    week = parse_week(week)
    if day not in range(7) or meal not in MEALS:
        raise Http404()
    try:
        with transaction.atomic():
            menu = get_menu(DjangoPlanningRepository(), week)
            if menu is None:
                raise Http404()
            slot = menu.slots[(day, meal)]
        return render(request, "menus/slot.html", {"week": week, "day": day, "meal": meal, "slot": slot, "day_label": DAYS[day], "meal_label": MEALS[meal], "menu": menu, "editable": week >= monday(MadridClock().today())})
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
        menu = get_menu(DjangoPlanningRepository(), week)
        if not menu:
            raise Http404()
        if week < monday(MadridClock().today()):
            return HttpResponse("Aquesta setmana és només de consulta.", status=403)
        if request.method == "POST":
            try:
                if int(request.POST.get("version", "")) != menu.version:
                    return render(request, "menus/action_error.html", {"week": week}, status=409)
            except ValueError:
                return HttpResponse("Versió invàlida.", status=400)
            if action == "skip" and menu.slots[(day, meal)].state in ("pending", "skipped"):
                return menu_action(request, week.isoformat(), day, meal, action)
        slot = menu.slots[(day, meal)]
        if request.method == "GET":
            observed = request.GET.get("version")
            if observed is not None and observed != str(menu.version):
                return render(request, "menus/action_error.html", {"week": week}, status=409)
        if slot.state != "selected":
            raise Http404()
        return render(request, "menus/confirm.html", {
            "week": week, "day": day, "meal": meal, "action": action, "menu": menu,
            "dish": slot.dish, "day_label": DAYS[day], "meal_label": MEALS[meal],
        })
    except (DatabaseError, ValueError, KeyError):
        return unavailable()



@require_http_methods(["GET"])
def move_choice(request, week, day, meal):
    week = parse_week(week)
    if day not in range(7) or meal not in MEALS:
        raise Http404()
    try:
        menu = get_menu(DjangoPlanningRepository(), week)
        if not menu or menu.slots[(day, meal)].state != "selected":
            raise Http404()
        if week < monday(MadridClock().today()):
            return HttpResponse("Aquesta setmana és només de consulta.", status=403)
        context = {"week": week, "day": day, "meal": meal, "menu": menu}
        if "destination_day" not in request.GET and "destination_meal" not in request.GET:
            context["choices"] = [(d, DAYS[d], m, MEALS[m], menu.slots[(d, m)])
                                  for d in range(7) for m in MEALS if (d, m) != (day, meal)]
            return render(request, "menus/move.html", context)
        try:
            target_day = int(request.GET.get("destination_day", ""))
            target_meal = request.GET["destination_meal"]
            version = int(request.GET.get("version", ""))
        except (KeyError, ValueError):
            return HttpResponse("Destinació o versió invàlida.", status=400)
        if target_day not in range(7) or target_meal not in MEALS or (target_day, target_meal) == (day, meal):
            return HttpResponse("Destinació invàlida.", status=400)
        if version != menu.version:
            return render(request, "menus/action_error.html", {"week": week}, status=409)
        target = menu.slots[target_day, target_meal]
        context.update(target=target, target_day=target_day, target_meal=target_meal,
                       target_label=DAYS[target_day], target_meal_label=MEALS[target_meal],
                       action="exchange" if target.state == "selected" else "move")
        return render(request, "menus/move.html", context)
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
        menu = move_or_undo(DjangoPlanningRepository(), MadridClock(), week, version, source, destination, request.POST.get("confirm") == "yes", action)
        if menu.version == version:
            messages.info(request, "No s’ha fet cap canvi")
        else:
            messages.success(request, {"move": "Plat mogut", "exchange": "Plats intercanviats", "undo": "Canvi desfet"}[action])
        return redirect("menu_week", week=week.isoformat())
    except PastWeek:
        return HttpResponse("Aquesta setmana és només de consulta.", status=403)
    except PlanningConflict:
        return render(request, "menus/action_error.html", {"week": week}, status=409)
    except (ValueError, TypeError, KeyError):
        return render(request, "menus/action_error.html", {"week": week, "invalid": True}, status=400)
    except (DatabaseError, Rollover):
        return unavailable()
