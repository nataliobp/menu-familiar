from django import template

register = template.Library()


@register.filter
def decimal_ca(value):
    if value is None:
        return ""
    return str(value).replace(".", ",")



@register.filter
def weekday_ca(index):
    return ("dilluns", "dimarts", "dimecres", "dijous", "divendres", "dissabte", "diumenge")[index]
