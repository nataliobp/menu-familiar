from copy import deepcopy
from dataclasses import dataclass
from datetime import date, timedelta
from menus.domain.template import POSITIONS


def monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


@dataclass
class Slot:
    suggestion: tuple[str, str] | None
    state: str = "pending"
    dish: dict | None = None

    def __post_init__(self):
        if self.state not in {"pending", "selected", "skipped"} or (self.state == "selected") != (self.dish is not None):
            raise ValueError("Invalid slot")


@dataclass
class WeeklyMenu:
    week: date
    version: int
    slots: dict[tuple[int, str], Slot]
    undo: dict | None = None

    def __post_init__(self):
        if self.week.weekday() != 0 or self.version < 1 or set(self.slots) != POSITIONS:
            raise ValueError("Invalid menu")

    @classmethod
    def from_template(cls, week, template, categories):
        return cls(week, 1, {position: Slot((key, categories[key]) if key else None)
                             for position, key in template.slots.items()})

    def select(self, position, dish, replace=False):
        slot = self.slots[position]
        if slot.state != ("selected" if replace else "pending"):
            raise ValueError("Invalid transition")
        if replace and slot.dish["dish_id"] == dish["dish_id"]:
            return False
        slot.state, slot.dish = "selected", dish
        return True

    def remove(self, position):
        slot = self.slots[position]
        if slot.state != "selected":
            raise ValueError("Invalid transition")
        slot.state, slot.dish = "pending", None
        return True

    def skip(self, position, skipped, confirmed=False):
        slot = self.slots[position]
        if skipped:
            if slot.state == "skipped":
                return False
            if slot.state == "selected" and not confirmed:
                raise ValueError("Confirmation required")
            slot.state, slot.dish = "skipped", None
        else:
            if slot.state == "pending":
                return False
            if slot.state != "skipped":
                raise ValueError("Invalid transition")
            slot.state = "pending"
        return True

    def move_or_exchange(self, source, destination, confirmed=False):
        if source == destination:
            return False
        first, second = self.slots[source], self.slots[destination]
        if first.state != "selected":
            raise ValueError("Source must be selected")
        if second.state == "skipped" and not confirmed:
            raise ValueError("Confirmation required")
        if second.state == "selected" and first.dish == second.dish:
            return False
        before = [(first.state, deepcopy(first.dish)), (second.state, deepcopy(second.dish))]
        if second.state == "selected":
            first.dish, second.dish = second.dish, first.dish
        else:
            second.state, second.dish = "selected", first.dish
            first.state, first.dish = "pending", None
        self.undo = {"positions": [list(source), list(destination)], "before": before,
                     "after": [(first.state, deepcopy(first.dish)), (second.state, deepcopy(second.dish))],
                     "eligible_version": self.version + 1}
        return True

    def undo_change(self):
        if not self.undo or self.undo["eligible_version"] != self.version:
            raise ValueError("Undo unavailable")
        positions = [tuple(position) for position in self.undo["positions"]]
        slots = [self.slots[position] for position in positions]
        if [[slot.state, slot.dish] for slot in slots] != [list(value) for value in self.undo["after"]]:
            raise ValueError("Undo unavailable")
        for slot, value in zip(slots, self.undo["before"]):
            slot.state, slot.dish = value
        self.undo = None
        return True
