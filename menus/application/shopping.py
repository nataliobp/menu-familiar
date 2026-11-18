from menus.application.planning import PastWeek, Rollover
from menus.domain.planning import monday


def mutate_shopping(repo, clock, week, menu_version, overlay_version, action, data):
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
