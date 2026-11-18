from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CategoryView:
    key: str
    name_ca: str


@dataclass(frozen=True)
class DishView:
    id: int
    name: str
    primary_category: CategoryView
    secondary_categories: tuple[str, ...]
    meal_preference: str
    special_occasion: bool
    archived: bool
    version: int
    recipe_status: str = "missing"

    @property
    def pk(self):
        return self.id

    @property
    def primary_category_id(self):
        return self.primary_category.key


@dataclass(frozen=True)
class RecipeView:
    draft: dict | None
    published: dict | None


class CatalogueQueries(Protocol):
    def dishes(self, archived: bool) -> list[DishView]: ...
    def dish(self, dish_id: int) -> DishView | None: ...
    def recipe(self, dish_id: int) -> RecipeView | None: ...
    def latest_dates(self) -> dict: ...


def get_dish(queries: CatalogueQueries, dish_id: int):
    return queries.dish(dish_id)


def get_recipe(queries: CatalogueQueries, dish_id: int):
    return queries.recipe(dish_id)


def browse_dishes(queries: CatalogueQueries, archived: bool, category: str, query: str):
    from menus.domain.recommendations import search_key
    needle = search_key(query)
    matches = (dish for dish in queries.dishes(archived) if needle in search_key(dish.name)
               and (not category or category in {dish.primary_category_id, *dish.secondary_categories}))
    return sorted(matches, key=lambda dish: (dish.name.casefold(), dish.id))


def picker_dishes(queries: CatalogueQueries, meal: str, category: str | None, query: str):
    from menus.domain.recommendations import rank_candidates
    candidates = [{"id": dish.id, "name": dish.name, "primary_name": dish.primary_category.name_ca,
                   "categories": {dish.primary_category_id, *dish.secondary_categories},
                   "meal_preference": dish.meal_preference, "special_occasion": dish.special_occasion}
                  for dish in queries.dishes(False)]
    return rank_candidates(candidates, meal, queries.latest_dates(), category, query)
