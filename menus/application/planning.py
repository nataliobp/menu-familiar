from menus.domain.planning import WeeklyMenu, monday


class PastWeek(Exception):
    pass


class PlanningConflict(Exception):
    pass


class Rollover(Exception):
    pass


class DuplicateWeek(Exception):
    pass


def create_menu(repo, clock, week):
    if week.weekday() != 0:
        raise ValueError("Invalid week")
    try:
        with repo.atomic():
            current = monday(clock.today())
            if week < current:
                raise PastWeek()
            menu = repo.get(week)
            if menu is None:
                template, categories = repo.template()
                menu = WeeklyMenu.from_template(week, template, categories)
                repo.create(menu)
            if monday(clock.today()) != current:
                raise Rollover()
            return menu
    except DuplicateWeek:
        with repo.atomic():
            current = monday(clock.today())
            if week < current:
                raise PastWeek()
            menu = repo.get(week)
            if menu is None:
                raise Rollover()
            if monday(clock.today()) != current:
                raise Rollover()
            return menu


def change_menu(repo, clock, week, position, version, operation, dish_id=None, confirmed=False):
    with repo.atomic():
        current = monday(clock.today())
        if week < current:
            raise PastWeek()
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


def move_or_undo(repo, clock, week, version, source=None, destination=None, confirmed=False):
    with repo.atomic():
        current = monday(clock.today())
        if week < current:
            raise PastWeek()
        menu = repo.get(week)
        if menu is None:
            raise ValueError("Missing menu")
        if menu.version != version:
            raise PlanningConflict()
        changed = menu.undo_change() if source is None else menu.move_or_exchange(source, destination, confirmed)
        if changed:
            repo.save(menu, version)
        else:
            repo.guard(week, version)
        if monday(clock.today()) != current:
            raise Rollover()
        return menu
