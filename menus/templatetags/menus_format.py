from django import template

from menus.web.presentation import category_label

register = template.Library()

@register.filter
def decimal_ca(value):
    if value is None:
        return ""
    return str(value).replace(".", ",")


@register.filter
def weekday_ca(index):
    return ("dilluns", "dimarts", "dimecres", "dijous", "divendres", "dissabte", "diumenge")[index]


@register.filter
def weekday_short_ca(index):
    return ("dl.", "dt.", "dc.", "dj.", "dv.", "ds.", "dg.")[index]

@register.filter
def category_icon(key):
    return key or "free"

@register.filter
def category_display(name, key):
    return category_label(key, name)

@register.filter
def preparation_steps(text):
    return [line.strip() for line in (text or "").splitlines() if line.strip()]



@register.filter
def recipe_quantity_ca(value):
    quantity = decimal_ca(value)
    return quantity.rstrip("0").rstrip(",") if "," in quantity else quantity
