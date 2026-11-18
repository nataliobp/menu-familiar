from django import template

register = template.Library()


@register.filter
def decimal_ca(value):
    if value is None:
        return ""
    return str(value).replace(".", ",")
