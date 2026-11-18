from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol

from menus.domain.catalogue import CatalogueDish


@dataclass(frozen=True)
class ImportResult:
    inserted: int
    unchanged: int


class CatalogueConflict(Exception):
    pass


class CatalogueRepository(Protocol):
    def transaction(self) -> AbstractContextManager: ...

    def get(self, dish_id: int) -> CatalogueDish | None: ...

    def add(self, dish: CatalogueDish) -> None: ...


def import_catalogue(dishes: list[CatalogueDish], repository: CatalogueRepository) -> ImportResult:
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
        return ImportResult(inserted=len(missing), unchanged=len(dishes) - len(missing))
