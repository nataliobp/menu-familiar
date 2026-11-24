import hashlib
import json
from uuid import UUID

from menus.application.planning import Rollover
from menus.application.recipes import save_recipe
from menus.domain.dish_edit import INITIAL_DISH_VERSION
from menus.domain.planning import monday
from menus.domain.recipe import validate_content


class DishConflict(Exception):
    pass


class DishReceiptConflict(DishConflict):
    pass


class DuplicateReceipt(Exception):
    pass


def _dish_creation(data, token, recipe=None):
    token = UUID(str(token))
    payload = {"operation": "create_dish", "scope": "catalogue", "name": data.name,
               "primary": data.primary_category, "secondary": sorted(data.secondary_categories),
               "preference": data.meal_preference, "special": data.special_occasion}
    if recipe is not None:
        payload["recipe"] = recipe
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return token, digest


def review_dish_creation(repo, data, token):
    token, digest = _dish_creation(data, token)
    with repo.atomic():
        receipt = repo.receipt(token)
    return receipt is None or receipt[:3] == ("create_dish", "catalogue", digest)


def create_dish(repo, data, token):
    return _create_dish(repo, data, token)


def create_dish_with_recipe(repo, clock, data, token, content):
    validate_content(content, True)
    return _create_dish(repo, data, token, clock=clock, recipe=content)


def _create_dish(repo, data, token, *, clock=None, recipe=None):
    token, digest = _dish_creation(data, token, recipe)
    try:
        with repo.atomic():
            receipt = repo.receipt(token)
            if receipt:
                if receipt[:3] != ("create_dish", "catalogue", digest):
                    raise DishReceiptConflict()
                return receipt[3]
            dish_id = repo.create_dish(data)
            if recipe is not None:
                save_recipe(repo, clock, dish_id, INITIAL_DISH_VERSION, recipe)
            repo.add_receipt(token, "create_dish", "catalogue", digest, dish_id)
            return dish_id
    except DuplicateReceipt:
        with repo.atomic():
            receipt = repo.receipt(token)
            if receipt and receipt[:3] == ("create_dish", "catalogue", digest):
                return receipt[3]
            raise DishReceiptConflict()


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
