from decimal import Decimal, InvalidOperation, localcontext
import re
from menus.domain.recipe import normalize_label, parse_amount
import unicodedata


FAMILIES = {"g": ("g", Decimal(1)), "kg": ("g", Decimal(1000)),
            "ml": ("ml", Decimal(1)), "l": ("ml", Decimal(1000)), "unit": ("unit", Decimal(1))}
ORDER = {"g": 0, "ml": 1, "unit": 2, "taste": 3}


def aggregate(slots):
    rows = {}
    pending = 0
    incomplete = []
    with localcontext() as context:
        context.prec = 32
        for position, slot in slots.items():
            if slot.state == "pending":
                pending += 1
                continue
            if slot.state == "skipped":
                continue
            snapshot = slot.dish
            content = snapshot["recipe_content"]
            if snapshot["recipe_status"] != "published":
                incomplete.append((position, snapshot["name"], snapshot["recipe_status"]))
            if content is None:
                continue
            if content.get("schema_version") != 1:
                raise ValueError("Invalid recipe version")
            for line in content["ingredients"]:
                name = line["name"]
                if normalize_label(name) != name or line["key"] != unicodedata.normalize("NFC", name.casefold()):
                    raise ValueError("Invalid ingredient identity")
                if line["quantity"] is not None:
                    raw = line["quantity"]
                    if not isinstance(raw, str) or not re.fullmatch(r"[0-9]+\.[0-9]{3}", raw):
                        raise ValueError("Invalid persisted quantity")
                    try:
                        parsed = Decimal(raw)
                    except InvalidOperation as exc:
                        raise ValueError("Invalid persisted quantity") from exc
                    if parsed <= 0 or parsed > Decimal("999999999.999") or line["unit"] not in FAMILIES or line["taste"]:
                        raise ValueError("Invalid persisted quantity")
                if line["taste"]:
                    family, amount = "taste", None
                elif line["quantity"] is None:
                    continue
                else:
                    family, factor = FAMILIES[line["unit"]]
                    amount = Decimal(line["quantity"]) * factor
                key = (line["key"], family)
                if key not in rows:
                    rows[key] = {"key": key, "name": line["name"], "quantity": amount, "notes": set()}
                else:
                    rows[key]["name"] = min(rows[key]["name"], line["name"])
                    if amount is not None:
                        rows[key]["quantity"] += amount
                        if rows[key]["quantity"] > Decimal("1399999999998600.000"):
                            raise ValueError("Shopping total overflow")
                if line["note"]:
                    rows[key]["notes"].add(line["note"])
        for row in rows.values():
            row["notes"] = tuple(sorted(row["notes"]))
        return sorted(rows.values(), key=lambda row: (row["key"][0], ORDER[row["key"][1]])), pending, incomplete


def manual_item(name, quantity, unit):
    from menus.domain.recipe import normalize_label, parse_amount, UNITS
    name = normalize_label(name)
    if not name or len(name) > 120 or bool(quantity) != bool(unit) or (unit and unit not in UNITS):
        raise ValueError("Invalid manual item")
    return name, parse_amount(quantity) if quantity else None, unit or None

def overlay_transition(action, data, row, previous):
    """Return the adjustment and check state to keep, or None to remove it."""
    adjustment, checked = previous or (None, False)
    if action == "reset":
        if adjustment is None:
            return previous
        adjustment, checked = None, checked and row is not None
    elif row is None:
        raise ValueError("Missing generated item")
    elif action == "adjust":
        if row["quantity"] is None:
            raise ValueError("Cannot adjust taste")
        amount = parse_amount(data.get("quantity", ""), Decimal("1399999999998600.000"))
        adjustment = None if amount == format(row["quantity"], ".3f") else amount
    elif action == "check":
        checked = desired_check(data)
    else:
        raise ValueError("Invalid operation")
    return (adjustment, checked) if adjustment is not None or checked else None


def desired_check(data):
    if data.get("checked") not in ("0", "1"):
        raise ValueError("Invalid check state")
    return data["checked"] == "1"
