from decimal import Decimal, localcontext

from menus.domain.recipe import validate_content


FAMILIES = {"g": ("g", Decimal(1)), "kg": ("g", Decimal(1000)),
            "ml": ("ml", Decimal(1)), "l": ("ml", Decimal(1000)), "unit": ("unit", Decimal(1))}
ORDER = {"g": 0, "ml": 1, "unit": 2, "taste": 3, "unknown": 4}
MAX_TOTAL = Decimal("1399999999998600.000")


def aggregate(slots):
    rows = {}
    pending = 0
    incomplete = []
    with localcontext() as context:
        context.prec = 32
        for position, slot in sorted(slots.items(), key=lambda item: (item[0][0], item[0][1] != "lunch")):
            if slot.state == "pending":
                pending += 1
                continue
            if slot.state == "skipped":
                continue
            snapshot = slot.dish
            status, content = snapshot["recipe_status"], snapshot["recipe_content"]
            if status != "published":
                incomplete.append((position, snapshot["name"], status))
            if content is None:
                continue
            validate_content(content, published=status == "published")
            for line in content["ingredients"]:
                add_ingredient(rows, line, provisional=status == "draft")

    for (identity, family), row in rows.items():
        row["notes"] = tuple(sorted(row["notes"]))
        if row["quantity"] is not None:
            row["subtotal"] = row["unknown"] or (identity, "unknown") in rows
    return sorted(rows.values(), key=lambda row: (row["key"][0], ORDER[row["key"][1]])), pending, incomplete


def add_ingredient(rows, line, *, provisional):
    family, factor = FAMILIES.get(line["unit"], ("taste" if line["taste"] else "unknown", None))
    key = (line["key"], family)
    row = rows.setdefault(key, {"key": key, "name": line["name"], "quantity": None, "notes": set(),
                                "unknown": False, "provisional": False, "subtotal": False})
    row["name"] = min(row["name"], line["name"])
    if line["note"]:
        row["notes"].add(line["note"])
    if line["quantity"] is not None:
        amount = Decimal(line["quantity"]) * factor
        row["quantity"] = amount if row["quantity"] is None else row["quantity"] + amount
        if row["quantity"] > MAX_TOTAL:
            raise ValueError("Shopping total overflow")
        row["provisional"] |= provisional
    elif line["taste"]:
        row["provisional"] |= provisional
    else:
        row["unknown"] = True
