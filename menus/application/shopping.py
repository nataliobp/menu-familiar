from dataclasses import dataclass
import hashlib
import json
from uuid import UUID

from menus.application.planning import PastWeek, Rollover
from menus.domain.planning import monday
from menus.domain.shopping import ORDER, manual_item
from menus.application.dishes import DuplicateReceipt


class ShoppingConflict(Exception):
    pass


class ShoppingReceiptConflict(ShoppingConflict):
    pass


def check_action(action, data):
    if action not in {"checked", "manual_check", "check"}:
        return action
    item_id, key, family = data.get("id"), data.get("key"), data.get("family")
    if item_id not in (None, ""):
        identifier = str(item_id)
        if (action == "check" or key not in (None, "") or family not in (None, "")
                or not identifier.isascii() or not identifier.isdecimal()
                or len(identifier) > 19 or not 1 <= int(identifier) <= 9223372036854775807):
            raise ValueError("Invalid manual item reference")
        return "manual_check"
    if action == "manual_check" or not isinstance(key, str) or not key or not isinstance(family, str) or family not in ORDER:
        raise ValueError("Invalid generated item reference")
    return "check"


def _manual_creation(week, data):
    name, quantity, unit = manual_item(data.get("name", ""), data.get("quantity", ""), data.get("unit", ""))
    token = UUID(data.get("token", ""))
    payload = {"operation": "manual_add", "scope": week.isoformat(), "name": name, "quantity": quantity, "unit": unit}
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return token, hashlib.sha256(encoded).hexdigest(), (name, quantity, unit)


def _replay(repo, week, token, digest):
    receipt = repo.get_receipt(token)
    if receipt is None:
        return None
    operation, scope, recorded_digest, item_id = receipt
    if (operation, scope, recorded_digest) != ("manual_add", week.isoformat(), digest):
        raise ShoppingReceiptConflict()
    return item_id


def review_manual_creation(repo, week, data):
    token, digest, _ = _manual_creation(week, data)
    try:
        _replay(repo, week, token, digest)
    except ShoppingReceiptConflict:
        return False
    return True


@dataclass(frozen=True)
class ManualCreation:
    item_id: int
    replayed: bool
    exists: bool


def mutate_shopping(repo, clock, week, menu_version, overlay_version, action, data, *, receipt=False):
    action = check_action(action, data)
    if action == "manual_add":
        token, digest, values = _manual_creation(week, data)
        data = {**data, "receipt_token": token, "digest": digest, "values": values}
    elif action == "manual_edit":
        data = {**data, "values": manual_item(data.get("name", ""), data.get("quantity", ""), data.get("unit", ""))}
    try:
        with repo.atomic():
            if action == "manual_add":
                replay = _replay(repo, week, token, digest)
                if replay is not None:
                    return _creation(repo, week, replay, True, receipt)
            current = monday(clock.today())
            if week < current:
                raise PastWeek()
            result = repo.mutate(week, menu_version, overlay_version, action, data)
            if monday(clock.today()) != current:
                raise Rollover()
            return _creation(repo, week, result, False, receipt) if action == "manual_add" else result
    except DuplicateReceipt:
        with repo.atomic():
            replay = _replay(repo, week, token, digest)
            if replay is None:
                raise ValueError("Missing receipt")
            return _creation(repo, week, replay, True, receipt)


def _creation(repo, week, item_id, replayed, receipt):
    if not receipt:
        return item_id
    view = repo.read(week)
    state = view[1] if view else None
    exists = bool(state and any(item.id == item_id for item in state.manual_items))
    return ManualCreation(item_id, replayed, exists)


def get_shopping(repo, week):
    return repo.read(week)
