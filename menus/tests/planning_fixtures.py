from menus.domain.planning import Slot, WeeklyMenu


def create_legacy_menu(repo, week):
    """Build a V1 snapshot with automatically copied category suggestions."""
    with repo.atomic():
        template, categories = repo.template()
        slots = {position: Slot((key, categories[key]) if key else None)
                 for position, key in template.slots.items()}
        menu = WeeklyMenu(week, 1, slots)
        repo.create(menu)
    return menu
