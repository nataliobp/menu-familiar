from menus.domain.planning import WeeklyMenu, monday


class PastWeek(Exception):
    pass


class PlanningConflict(Exception):
    pass


class Rollover(Exception):
    pass


class DuplicateWeek(Exception):
    pass


def change_menu(repo, clock, week, position, version, operation, dish_id=None, confirmed=False):
    try:
        return _change_menu(repo, clock, week, position, version, operation, dish_id, confirmed)
    except DuplicateWeek as exc:
        raise PlanningConflict() from exc


def _change_menu(repo, clock, week, position, version, operation, dish_id, confirmed):
    with repo.atomic():
        current = monday(clock.today())
        if week < current:
            raise PastWeek()
        if version == 0 and operation in ("assign", "skip"):
            menu = WeeklyMenu.empty(week)
            # Reserve the unique week before reading any rows. SQLite can then
            # serialize concurrent first writes without upgrading a read lock.
            # Invalid transitions and snapshot failures roll back the reservation.
            repo.create(menu)
            version = menu.version
        else:
            menu = repo.get(week)
            if menu is None:
                raise ValueError("Missing menu")
            if menu.version != version:
                raise PlanningConflict()
        if operation in ("assign", "replace"):
            dish = repo.dish_snapshot(dish_id)
            if dish is None:
                raise ValueError("Missing dish")
            changed = menu.select(position, dish, operation == "replace")
        elif operation == "remove":
            changed = menu.remove(position)
        elif operation in ("skip", "reactivate"):
            changed = menu.skip(position, operation == "skip", confirmed)
        else:
            raise ValueError("Invalid operation")
        if changed:
            menu.undo = None
            repo.save(menu, version)
        else:
            repo.guard(week, version)
        if monday(clock.today()) != current:
            raise Rollover()
        return menu


def move_or_undo(repo, clock, week, version, source=None, destination=None, confirmed=False, operation=None):
    with repo.atomic():
        current = monday(clock.today())
        if week < current:
            raise PastWeek()
        menu = repo.get(week)
        if menu is None:
            raise ValueError("Missing menu")
        if menu.version != version:
            raise PlanningConflict()
        if source is not None:
            if source not in menu.slots or destination not in menu.slots:
                raise ValueError("Invalid position")
            if menu.slots[source].state != "selected":
                raise ValueError("Source must be selected")
        if source is not None and source != destination and operation in ("move", "exchange"):
            target_selected = menu.slots[destination].state == "selected"
            if target_selected != (operation == "exchange"):
                raise ValueError("Invalid destination")
        changed = menu.undo_change() if source is None else menu.move_or_exchange(source, destination, confirmed)
        if changed:
            repo.save(menu, version)
        else:
            repo.guard(week, version)
        if monday(clock.today()) != current:
            raise Rollover()
        return menu


def get_menu(repo, week):
    return repo.get(week)


def read_plan(repo, week, editable):
    menu = get_menu(repo, week)
    if not editable:
        return menu, None, {}, {}
    template, categories = repo.template()
    # Stored suggestions are legacy copies. The domain has never supported
    # explicit per-slot overrides, so only the current template guides editing.
    suggestions = {position: (key, categories[key]) for position, key in template.slots.items() if key}
    return menu or WeeklyMenu.empty(week), menu.version if menu else 0, suggestions, categories
