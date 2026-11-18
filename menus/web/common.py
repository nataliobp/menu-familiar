from datetime import date

from django.http import Http404, HttpResponse
from django.template.loader import render_to_string

from menus.domain.planning import MAX_WEEK_START


DAYS = ("Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres", "Dissabte", "Diumenge")
MEALS = {"lunch": "Dinar", "dinner": "Sopar"}


def unavailable():
    return HttpResponse(render_to_string("503.html"), status=503)

def parse_week(value):
    try:
        week = date.fromisoformat(value)
        if week.isoformat() != value or week.weekday() != 0 or week > MAX_WEEK_START:
            raise ValueError()
        return week
    except ValueError:
        raise Http404()


def filter_error(query, category, categories):
    if len(query) > 200:
        return "La cerca admet fins a 200 caràcters."
    if category and category not in categories:
        return "Selecciona una categoria vàlida."
    return None
