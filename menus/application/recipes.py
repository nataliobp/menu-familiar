from menus.application.planning import Rollover
from menus.domain.planning import monday
from menus.domain.recipe import validate_content


def save_recipe(repo, clock, dish_id, version, content, publish=False, context=None):
    validate_content(content, publish)
    with repo.atomic():
        current = monday(clock.today())
        if context is not None:
            repo.validate_context(context, dish_id, current)
        effective_changed = repo.save_recipe(dish_id, version, content, publish)
        if effective_changed:
            repo.refresh_dish(dish_id, current)
        if monday(clock.today()) != current:
            raise Rollover()
