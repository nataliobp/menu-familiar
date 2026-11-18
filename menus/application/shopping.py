from dataclasses import dataclass
import hashlib
import json
from uuid import UUID

from menus.application.planning import PastWeek, Rollover
from menus.domain.planning import monday
from menus.domain.shopping import manual_item
from menus.application.dishes import DuplicateReceipt


class ShoppingConflict(Exception):
    pass


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
        raise ShoppingConflict()
    return item_id


@dataclass(frozen=True)
class ManualCreation:
    item_id: int
    replayed: bool
    exists: bool


def mutate_shopping(repo, clock, week, menu_version, overlay_version, action, data, *, receipt=False):
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
