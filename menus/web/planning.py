from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.db import DatabaseError, transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from menus.application.catalogue_queries import picker_dishes
from menus.application.planning import PastWeek, PlanningConflict, Rollover, change_menu, get_menu, move_or_undo, read_plan
from menus.domain.planning import monday
from menus.infrastructure.django_catalogue_queries import DjangoCatalogueQueries
from menus.infrastructure.django_planning import DjangoPlanningRepository, MadridClock
from menus.web.common import DAYS, MEALS, command_done, filter_error, parse_week, unavailable
from menus.web.presentation import category_options, picker_groups, week_navigation


@require_http_methods(["GET"])
def current_menu(request):
    return redirect("menu_week", week=monday(MadridClock().today()).isoformat())


@require_http_methods(["GET"])
def menu_view(request, week):
    week = parse_week(week)
    repo, clock = DjangoPlanningRepository(), MadridClock()
    try:
        with transaction.atomic():
            today = clock.today()
            editable = week >= monday(today)
            menu, version, suggestions, _ = read_plan(repo, week, editable)
        days = []
        for day, label in enumerate(DAYS) if menu else ():
            meals = []
            for meal, meal_label in MEALS.items():
                slot = menu.slots[day, meal]
                key, category = suggestions.get((day, meal), ("", ""))
                meals.append((meal, meal_label, slot, key, category))
            day_date = week + timedelta(days=day)
            days.append((day, label, day_date, day_date == today, meals))
        return render(request, "menus/menu.html", {"week": week, "days": days, "menu": menu,
                      "version": version, "editable": editable, **week_navigation(week, "current_menu", "menu_week")})
    except (DatabaseError, ValueError, KeyError):
        return unavailable()


@require_http_methods(["GET"])
def menu_picker(request, week, day, meal):
    week = parse_week(week)
    if day not in range(7) or meal not in MEALS:
        raise Http404()
    repo = DjangoPlanningRepository()
    try:
        with transaction.atomic():
            if week < monday(MadridClock().today()):
                raise Http404()
            menu, version, suggestions, categories = read_plan(repo, week, True)
            suggestion = suggestions.get((day, meal))
            slot = menu.slots[(day, meal)]
            action = request.GET.get("action", "assign")
            if action not in ("assign", "replace") or slot.state != ("pending" if action == "assign" else "selected"):
                raise Http404()
            category = request.GET.get("category")
            mode = request.GET.get("mode")
            if mode == "all":
                category = ""
            if category is None and suggestion:
                category = suggestion[0]
            query = request.GET.get("q", "")
            error = filter_error(query, category, categories)
            dishes = [] if error else picker_dishes(DjangoCatalogueQueries(), meal, category, query)
        return render(request, "menus/picker.html", {
            "week": week, "day": day, "meal": meal, "action": action, "version": version,
            "suggestion": suggestion, "dishes": dishes, "tiers": picker_groups(dishes, meal, category),
            "categories": category_options(categories), "category": category, "query": query,
            "day_label": DAYS[day], "meal_label": MEALS[meal], "error": error,
        }, status=400 if error else 200)
    except (DatabaseError, ValueError, KeyError):
        return unavailable()


@require_POST
def menu_action(request, week, day, meal, action):
    week = parse_week(week)
    if day not in range(7) or meal not in MEALS or action not in ("assign", "replace", "remove", "skip", "reactivate"):
        raise Http404()
    recovery = {"week": week}
    picker_filters = None
    if action in ("assign", "replace") and request.POST.get("from_picker") == "yes":
        picker_filters = {"action": action, "category": request.POST.get("category", ""),
                          "q": request.POST.get("q", "")}
        path = reverse("menu_picker", args=[week.isoformat(), day, meal])
        recovery.update(picker_url=f"{path}?{urlencode(picker_filters)}",
                        slot_url=reverse("slot_detail", args=[week.isoformat(), day, meal]))
    try:
        version = int(request.POST.get("version", ""))
        if action == "remove" and request.POST.get("confirm") != "yes":
            raise ValueError("Confirmation required")
        dish_id = int(request.POST.get("dish", "0"))
        if action in ("assign", "replace") and not 1 <= dish_id <= 9223372036854775807:
            raise ValueError("Invalid dish identifier")
        change_menu(DjangoPlanningRepository(), MadridClock(), week, (day, meal), version, action, dish_id, request.POST.get("confirm") == "yes")
        messages.success(request, "Canvi desat")
        return command_done(request, "menu_week", week=week.isoformat())
    except PastWeek:
        return HttpResponse("Aquesta setmana és només de consulta.", status=403)
    except PlanningConflict:
        if picker_filters is not None:
            recovery.pop("picker_url")
            try:
                current = get_menu(DjangoPlanningRepository(), week)
                state = current.slots[day, meal].state if current else "pending"
                next_action = {"pending": "assign", "selected": "replace"}.get(state)
                if next_action:
                    picker_filters["action"] = next_action
                    recovery["picker_url"] = f"{path}?{urlencode(picker_filters)}"
            except (DatabaseError, ValueError, KeyError):
                pass
        return render(request, "menus/action_error.html", recovery, status=409)
    except (ValueError, TypeError, KeyError):
        return render(request, "menus/action_error.html", {**recovery, "invalid": True}, status=400)
    except Rollover:
        return unavailable()
    except DatabaseError:
        if "picker_url" in recovery:
            return render(request, "menus/action_error.html", {**recovery, "busy": True}, status=503)
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
        return render(request, "menus/slot.html", {"week": week, "day": day, "meal": meal, "slot": slot, "day_label": DAYS[day], "meal_label": MEALS[meal], "menu": menu, "editable": week >= monday(MadridClock().today()), "version": menu.version})
    except (DatabaseError, ValueError, KeyError):
        return unavailable()


@require_http_methods(["GET", "POST"])
def menu_confirm(request, week, day, meal, action):
    week = parse_week(week)
    if day not in range(7) or meal not in MEALS or action not in ("remove", "skip"):
        raise Http404()
    if request.method == "POST" and request.POST.get("confirm") == "yes":
        return menu_action(request, week.isoformat(), day, meal, action)
    try:
        if week < monday(MadridClock().today()):
            return HttpResponse("Aquesta setmana és només de consulta.", status=403)
        if request.method == "POST" and action == "skip" and request.POST.get("version") == "0":
            return menu_action(request, week.isoformat(), day, meal, action)
        menu = get_menu(DjangoPlanningRepository(), week)
        if not menu:
            raise Http404()
        slot = menu.slots[(day, meal)]
        observed = request.POST.get("version", "") if request.method == "POST" else request.GET.get("version")
        if observed is not None and observed != str(menu.version):
            return render(request, "menus/action_error.html", {"week": week}, status=409)
        if request.method == "POST" and action == "skip" and slot.state != "selected":
            return menu_action(request, week.isoformat(), day, meal, action)
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
            context["choices"] = [(d, DAYS[d], m, MEALS[m], menu.slots[d, m],
                                   "exchange" if menu.slots[d, m].state == "selected" else "move")
                                  for d in range(7) for m in MEALS if (d, m) != (day, meal)]
            return render(request, "menus/move.html", context)
        try:
            target_day = int(request.GET.get("destination_day", ""))
            target_meal = request.GET["destination_meal"]
            version = int(request.GET.get("version", ""))
        except (KeyError, ValueError):
            return HttpResponse("La destinació o la versió no és vàlida.", status=400)
        if target_day not in range(7) or target_meal not in MEALS or (target_day, target_meal) == (day, meal):
            return HttpResponse("La destinació no és vàlida.", status=400)
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
        return command_done(request, "menu_week", week=week.isoformat())
    except PastWeek:
        return HttpResponse("Aquesta setmana és només de consulta.", status=403)
    except PlanningConflict:
        return render(request, "menus/action_error.html", {"week": week}, status=409)
    except (ValueError, TypeError, KeyError):
        return render(request, "menus/action_error.html", {"week": week, "invalid": True}, status=400)
    except (DatabaseError, Rollover):
        return unavailable()
