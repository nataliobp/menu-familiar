import hashlib
import json
from uuid import UUID

from menus.application.planning import Rollover
from menus.domain.planning import monday


class DishConflict(Exception):
    pass


class DuplicateReceipt(Exception):
    pass


def create_dish(repo, data, token):
    token = UUID(str(token))
    payload = {"operation": "create_dish", "scope": "catalogue", "name": data.name,
               "primary": data.primary_category, "secondary": sorted(data.secondary_categories),
               "preference": data.meal_preference, "special": data.special_occasion}
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    try:
        with repo.atomic():
            receipt = repo.receipt(token)
            if receipt:
                if receipt[:3] != ("create_dish", "catalogue", digest):
                    raise DishConflict()
                return receipt[3]
            dish_id = repo.create_dish(data)
            repo.add_receipt(token, "create_dish", "catalogue", digest, dish_id)
            return dish_id
    except DuplicateReceipt:
        with repo.atomic():
            receipt = repo.receipt(token)
            if receipt and receipt[:3] == ("create_dish", "catalogue", digest):
                return receipt[3]
            raise DishConflict()


def update_dish(repo, clock, dish_id, data, version):
    with repo.atomic():
        current = monday(clock.today())
        changed = repo.update_dish(dish_id, data, version)
        if changed:
            repo.refresh_dish(dish_id, current)
        if monday(clock.today()) != current:
            raise Rollover()


def set_archived(repo, dish_id, version, archived):
    with repo.atomic():
        repo.set_archived(dish_id, version, archived)
