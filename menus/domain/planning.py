from copy import deepcopy
from dataclasses import dataclass
from datetime import date, timedelta
from menus.domain.template import POSITIONS


MAX_WEEK_START = date.max - timedelta(days=6)


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
        if self.week.weekday() != 0 or self.week > MAX_WEEK_START or self.version < 1 or set(self.slots) != POSITIONS:
            raise ValueError("Invalid menu")

    @classmethod
    def empty(cls, week):
        return cls(week, 1, {position: Slot(None) for position in POSITIONS})

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

    def validate_undo(self):
        undo = self.undo
        if undo is None:
            return
        if not isinstance(undo, dict) or set(undo) != {"positions", "before", "after", "eligible_version"}:
            raise ValueError("Invalid undo")
        version = undo["eligible_version"]
        if type(version) is not int or version != self.version or version < 3:
            raise ValueError("Invalid undo version")
        positions = undo["positions"]
        if not isinstance(positions, list) or len(positions) != 2:
            raise ValueError("Invalid undo positions")
        for position in positions:
            if (not isinstance(position, list) or len(position) != 2
                    or type(position[0]) is not int or tuple(position) not in self.slots):
                raise ValueError("Invalid undo position")
        if positions[0] == positions[1]:
            raise ValueError("Duplicate undo position")
        before, after = undo["before"], undo["after"]
        for image in (before, after):
            if not isinstance(image, list) or len(image) != 2:
                raise ValueError("Invalid undo image")
            for pair in image:
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    raise ValueError("Invalid undo slot")
                state, dish = pair
                Slot(None, state, dish)
                if dish is not None:
                    identifier = dish.get("dish_id")
                    if type(identifier) is not int or not 1 <= identifier <= 9223372036854775807:
                        raise ValueError("Invalid undo dish")
                    validate_snapshot(dish, identifier)
        live = [self.slots[tuple(position)] for position in positions]
        if [tuple(pair) for pair in after] != [(slot.state, slot.dish) for slot in live]:
            raise ValueError("Undo does not match the menu")
        first, second = map(tuple, before)
        expected = [second, first] if second[0] == "selected" else [("pending", None), first]
        if first[0] != "selected" or first == second or list(map(tuple, after)) != expected:
            raise ValueError("Invalid undo transition")

    def refresh_undo(self, changed_positions):
        if self.undo is None:
            return
        if any(tuple(position) in changed_positions for position in self.undo["positions"]):
            self.undo = None
        else:
            self.undo["eligible_version"] = self.version + 1

    def undo_change(self):
        if not self.undo or self.undo["eligible_version"] != self.version:
            raise ValueError("Undo unavailable")
        self.validate_undo()
        positions = [tuple(position) for position in self.undo["positions"]]
        slots = [self.slots[position] for position in positions]
        if [[slot.state, slot.dish] for slot in slots] != [list(value) for value in self.undo["after"]]:
            raise ValueError("Undo unavailable")
        for slot, value in zip(slots, self.undo["before"]):
            slot.state, slot.dish = value
        self.undo = None
        return True


def validate_snapshot(value, dish_id):
    from menus.domain.recipe import validate_content
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
            or value["schema_version"] != 1 or type(value.get("dish_id")) is not int
            or value["dish_id"] != dish_id):
        raise ValueError("Invalid dish snapshot")
    required = {"schema_version", "dish_id", "name", "primary_category", "secondary_categories", "meal_preference", "special_occasion", "recipe_status", "recipe_content"}
    if set(value) != required or not isinstance(value["name"], str) or not value["name"].strip():
        raise ValueError("Invalid dish snapshot")
    if not isinstance(value["secondary_categories"], list):
        raise ValueError("Invalid snapshot categories")
    categories = [value["primary_category"], *value["secondary_categories"]]
    if any(not isinstance(category, dict) or set(category) != {"key", "name"} or not isinstance(category["key"], str) or not category["key"] or not isinstance(category["name"], str) or not category["name"] for category in categories):
        raise ValueError("Invalid snapshot categories")
    keys = [category["key"] for category in categories]
    if len(keys) != len(set(keys)) or value["meal_preference"] not in {"lunch", "dinner", "both"} or type(value["special_occasion"]) is not bool:
        raise ValueError("Invalid snapshot metadata")
    status, content = value["recipe_status"], value["recipe_content"]
    if status not in {"missing", "draft", "published"} or (status == "missing") != (content is None):
        raise ValueError("Invalid snapshot recipe")
    if content is not None:
        validate_content(content, status == "published")
