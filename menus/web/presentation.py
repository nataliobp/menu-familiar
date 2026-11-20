"""Presentation rules shared by the server-rendered screens."""

from datetime import date, timedelta

from menus.domain.planning import MAX_WEEK_START
from menus.domain.recipe import effective_recipe, validate_content


def category_label(key, name):
    if key == "salads":
        return "Amanides"
    return name or "Lliure"


def category_options(categories):
    return [(key, category_label(key, name)) for key, name in categories.items()]


def week_navigation(week, current_route, week_route):
    step = timedelta(days=7)
    return {
        "week_end": week + timedelta(days=6),
        "previous": week - step if week >= date.min + step else None,
        "next": week + step if week <= MAX_WEEK_START - step else None,
        "current_route": current_route,
        "week_route": week_route,
    }


def catalogue_groups(dishes):
    groups = {}
    for dish in dishes:
        category = dish.primary_category
        groups.setdefault((category.key, category_label(category.key, category.name_ca)), []).append(dish)
    return list(groups.items())


def picker_groups(dishes, meal, category):
    if category:
        return [("", [(None, dishes)])] if dishes else []
    tiers = {}
    for dish in dishes:
        compatible = dish["meal_preference"] in (meal, "both")
        if dish["special_occasion"]:
            heading = "Ocasions especials" if compatible else "Ocasions especials · Altres preferències"
        else:
            heading = "" if compatible else "Altres preferències"
        key = dish["primary_key"]
        label = category_label(key, dish["primary_name"])
        tiers.setdefault(heading, {}).setdefault((key, label), []).append(dish)
    return [(heading, list(groups.items())) for heading, groups in tiers.items()]


def recipe_read_context(recipe):
    published = recipe.published if recipe else None
    draft = recipe.draft if recipe else None
    if published is not None:
        validate_content(published, True)
    if draft is not None:
        validate_content(draft)
    status, content = effective_recipe(draft, published)
    return {
        "content": content,
        "recipe_status": status,
        "unpublished_changes": published is not None and draft is not None,
    }
