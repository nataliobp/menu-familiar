from django.db import DatabaseError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_safe

from menus.application.errors import DataIntegrityError
from menus.application.shopping import get_ingredient_reminder
from menus.domain.planning import monday
from menus.infrastructure.django_planning import DjangoPlanningRepository, MadridClock
from menus.web.common import parse_week, unavailable
from menus.web.presentation import week_navigation
from menus.web.reminder_sections import reminder_sections


@require_safe
def current_shopping(request):
    return redirect("shopping_week", week=monday(MadridClock().today()).isoformat())


@require_safe
def shopping_view(request, week):
    week = parse_week(week)
    context = {"week": week, "past_week": week < monday(MadridClock().today()),
               **week_navigation(week, "current_shopping", "shopping_week")}
    try:
        reminder = get_ingredient_reminder(DjangoPlanningRepository(), week)
    except DataIntegrityError:
        if context["past_week"]:
            return render(request, "menus/shopping.html", {**context, "historical_unavailable": True}, status=503)
        return unavailable()
    except (DatabaseError, ValueError, KeyError, ArithmeticError):
        return unavailable()
    return render(request, "menus/shopping.html", {
        **context, "reminder": reminder, "sections": reminder_sections(reminder.rows) if reminder else (),
    })
