"""Read the weekly ingredient reminder from the stored menu snapshots."""

from dataclasses import dataclass

from menus.domain.shopping import aggregate


@dataclass(frozen=True)
class IngredientReminder:
    rows: list
    pending: int
    incomplete: list
    selected: int
    skipped: int


def get_ingredient_reminder(planning, week):
    with planning.atomic():
        menu = planning.get(week)
    if menu is None:
        return None
    rows, pending, incomplete = aggregate(menu.slots)
    skipped = sum(slot.state == "skipped" for slot in menu.slots.values())
    return IngredientReminder(rows, pending, incomplete, len(menu.slots) - pending - skipped, skipped)
