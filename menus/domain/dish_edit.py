from dataclasses import dataclass
from menus.domain.categories import CATEGORIES


@dataclass(frozen=True)
class DishInput:
    name: str
    primary_category: str
    secondary_categories: frozenset[str]
    meal_preference: str
    special_occasion: bool

    def __post_init__(self):
        object.__setattr__(self, "name", self.name.strip())
        keys = {key for key, _ in CATEGORIES}
        if (not self.name or len(self.name) > 200 or self.primary_category not in keys
                or not self.secondary_categories <= keys or self.primary_category in self.secondary_categories
                or self.meal_preference not in {"lunch", "dinner", "both"}
                or type(self.special_occasion) is not bool):
            raise ValueError("Invalid dish")
