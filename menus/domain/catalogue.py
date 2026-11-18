from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogueDish:
    id: int
    name: str
    primary_category: str
    secondary_categories: frozenset[str]
    meal_preference: str
    special_occasion: bool
