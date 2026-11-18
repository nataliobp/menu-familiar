from uuid import uuid4

from django.contrib import messages
from django.db import DatabaseError, transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from menus.application.planning import PastWeek, Rollover
from menus.application.shopping import ShoppingConflict, get_shopping, mutate_shopping
from menus.domain.planning import monday
from menus.infrastructure.django_planning import MadridClock
from menus.infrastructure.django_shopping import DjangoShoppingRepository
from menus.web.common import parse_week, unavailable


@require_http_methods(["GET"])
def current_shopping(request):
    return redirect("shopping_week", week=monday(MadridClock().today()).isoformat())


@require_http_methods(["GET"])
def shopping_view(request, week):
    week = parse_week(week)
    try:
        with transaction.atomic():
            view = get_shopping(DjangoShoppingRepository(), week)
            if view is None:
                return render(request, "menus/shopping.html", {"week": week})
            menu, state, rows, pending, incomplete, orphans = view
            manual = list(state.manual_items) if state else []
        return render(request, "menus/shopping.html", {"week": week, "menu": menu, "state": state, "rows": rows, "pending": pending, "incomplete": incomplete, "orphans": orphans, "manual": manual, "editable": week >= monday(MadridClock().today()), "token": str(uuid4())})
    except (DatabaseError, ValueError, KeyError, ArithmeticError):
        return unavailable()


@require_POST
def shopping_action(request, week, action):
    week = parse_week(week)
    if action == "checked":
        action = "manual_check" if request.POST.get("id") else "check"
    if action not in ("manual_add", "manual_edit", "manual_remove", "manual_check", "adjust", "reset", "check"):
        raise Http404()
    try:
        data = {key: request.POST.get(key, "") for key in ("name", "quantity", "unit", "token", "id", "key", "family", "checked")}
        if request.POST.get("action") == "review":
            with transaction.atomic():
                current_view = get_shopping(DjangoShoppingRepository(), week)
            if not current_view or week < monday(MadridClock().today()):
                raise PastWeek()
            menu, state, rows, _, _, orphans = current_view
            manual = state.manual_items if state else ()
            target_missing = (
                action in {"manual_edit", "manual_remove", "manual_check"}
                and not any(str(item.id) == data["id"] for item in manual)
            ) or (
                action in {"adjust", "check", "reset"}
                and not any(row["key"] == (data["key"], data["family"]) for row in rows)
                and not (action == "reset" and any(
                    (orphan.ingredient_key, orphan.family) == (data["key"], data["family"])
                    for orphan in orphans
                ))
            )
            return render(request, "menus/shopping_error.html", {
                "week": week, "action": action, "data": data, "reviewed": True,
                "current_rows": rows, "current_manual": manual, "target_missing": target_missing,
                "orphans": orphans, "menu_version": menu.version,
                "overlay_version": state.version if state else 0,
                "error": "Compara les dades i confirma el canvi que vols fer.",
            })
        if action == "manual_remove" and request.POST.get("confirm") != "yes":
            with transaction.atomic():
                view = get_shopping(DjangoShoppingRepository(), week)
                if view is None or not view[1]:
                    raise ValueError("Missing item")
                if view[0].version != int(request.POST.get("menu_version", "")) or view[1].version != int(request.POST.get("overlay_version", "")):
                    raise ShoppingConflict()
                item = next ( (item for item in view[1].manual_items if str(item.id) == data["id"]), None )
                if not item:
                    raise ValueError("Missing item")
                if week < monday(MadridClock().today()):
                    raise PastWeek()
                return render(request, "menus/manual_confirm.html", {"week": week, "item": item, "menu_version": view[0].version, "overlay_version": view[1].version})
        result = mutate_shopping(
            DjangoShoppingRepository(), MadridClock(), week,
            int(request.POST.get("menu_version", "")), int(request.POST.get("overlay_version", "")),
            action, data, receipt=True,
        )
        if result and result.replayed:
            if result.exists:
                messages.info(request, "Aquest producte ja s’havia afegit a la llista.")
            else:
                messages.info(request, "Aquest producte s’havia afegit, però ja no és a la llista.")
        elif result:
            messages.success(request, "Producte afegit a la llista.")
        return redirect("shopping_week", week=week.isoformat())
    except PastWeek:
        return HttpResponse("Aquesta setmana és només de consulta.", status=403)
    except ShoppingConflict:
        try:
            with transaction.atomic():
                current_view = get_shopping(DjangoShoppingRepository(), week)
                current_rows = current_view[2] if current_view else []
                current_manual = list(current_view[1].manual_items) if current_view and current_view[1] else []
        except (DatabaseError, ValueError):
            return unavailable()
        return render(request, "menus/shopping_error.html", {"week": week, "action": action, "data": data,
                      "error": "El contingut ha canviat. Revisa les dades abans de tornar-ho a provar.", "conflict": True,
                      "current_rows": current_rows, "current_manual": current_manual, "orphans": current_view[-1] if current_view else ()}, status=409)
    except (ValueError, TypeError, KeyError):
        return render(request, "menus/shopping_error.html", {"week": week, "action": action, "data": data,
                      "error": "Revisa les dades del producte.", "menu_version": request.POST.get("menu_version", ""),
                      "overlay_version": request.POST.get("overlay_version", "")}, status=400)
    except (DatabaseError, Rollover):
        return render(request, "menus/shopping_error.html", {"week": week, "action": action, "data": data,
                      "error": "No s’ha pogut completar l’acció. Revisa la llista abans de tornar-ho a provar.",
                      "menu_version": request.POST.get("menu_version", ""),
                      "overlay_version": request.POST.get("overlay_version", "")}, status=503)


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
            view = get_shopping(DjangoShoppingRepository(), week)
            if not view:
                raise Http404()
            menu, state, rows, _, _, _ = view
            if week < monday(MadridClock().today()):
                return HttpResponse("Aquesta setmana és només de consulta.", status=403)
            item = next((item for item in state.manual_items if item.id == item_id), None) if state and item_id is not None else None
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
