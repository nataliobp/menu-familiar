from menus.application.planning import PastWeek, Rollover
from menus.domain.planning import monday
from menus.application.dishes import DuplicateReceipt


def mutate_shopping(repo, clock, week, menu_version, overlay_version, action, data):
    try:
        with repo.atomic():
            if action == "manual_add":
                replay = repo.manual_replay(week, data)
                if replay is not None:
                    return replay
            current = monday(clock.today())
            if week < current:
                raise PastWeek()
            result = repo.mutate(week, menu_version, overlay_version, action, data)
            if monday(clock.today()) != current:
                raise Rollover()
            return result
    except DuplicateReceipt:
        with repo.atomic():
            replay = repo.manual_replay(week, data)
            if replay is None:
                raise ValueError("Missing receipt")
            return replay


def get_shopping(repo, week):
    return repo.read(week)
