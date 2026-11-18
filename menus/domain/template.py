from dataclasses import dataclass


POSITIONS = frozenset((day, meal) for day in range(7) for meal in ("lunch", "dinner"))


@dataclass
class WeeklyTemplate:
    version: int
    slots: dict[tuple[int, str], str | None]

    def __post_init__(self):
        if self.version < 1 or set(self.slots) != POSITIONS:
            raise ValueError("Invalid template")

    def set_category(self, position, category):
        if position not in POSITIONS:
            raise ValueError("Invalid position")
        changed = self.slots[position] != category
        self.slots[position] = category
        return changed
