from contextlib import AbstractContextManager
from typing import Protocol

from menus.domain.catalogue import CatalogueDish


class CatalogueConflict(Exception):
    pass


class CatalogueRepository(Protocol):
    def transaction(self) -> AbstractContextManager: ...

    def get(self, dish_id: int) -> CatalogueDish | None: ...

    def add(self, dish: CatalogueDish) -> None: ...


def import_catalogue(dishes: list[CatalogueDish], repository: CatalogueRepository) -> int:
    with repository.transaction():
        missing = []
        for dish in dishes:
            existing = repository.get(dish.id)
            if existing is None:
                missing.append(dish)
            elif existing != dish:
                raise CatalogueConflict(dish.id)
        for dish in missing:
            repository.add(dish)
        return len(missing)
