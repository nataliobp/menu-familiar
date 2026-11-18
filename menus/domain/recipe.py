from decimal import Decimal, InvalidOperation
import re
import unicodedata


AMOUNT = re.compile(r"^[0-9]+(?:[.,][0-9]{1,3})?$")
UNITS = {"g", "kg", "ml", "l", "unit"}


def normalize_label(value):
    return unicodedata.normalize("NFC", " ".join(value.split()))


def parse_amount(value, maximum=Decimal("999999999.999")):
    if not AMOUNT.fullmatch(value):
        raise ValueError("Invalid quantity")
    try:
        amount = Decimal(value.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Invalid quantity") from exc
    if amount <= 0 or amount > maximum:
        raise ValueError("Invalid quantity")
    return format(amount, ".3f")


def recipe_content(preparation, lines, publish=False):
    if len(preparation) > 10000 or len(lines) > 100:
        raise ValueError("Recipe too long")
    ingredients = []
    for line in lines:
        name = normalize_label(line.get("name", ""))
        unit, quantity = line.get("unit", ""), line.get("quantity", "").strip()
        note, taste = line.get("note", ""), line.get("taste", False)
        if not name or len(name) > 120 or len(note) > 500 or unit not in UNITS | {""} or type(taste) is not bool:
            raise ValueError("Invalid ingredient")
        if taste and (unit or quantity):
            raise ValueError("Invalid taste ingredient")
        if quantity and not unit:
            raise ValueError("Missing unit")
        if publish and not taste and (not quantity or not unit):
            raise ValueError("Incomplete ingredient")
        ingredients.append({"name": name, "key": unicodedata.normalize("NFC", name.casefold()),
                            "quantity": parse_amount(quantity) if quantity else None,
                            "unit": unit or None, "taste": taste, "note": note})
    if publish and (not preparation.strip() or not ingredients):
        raise ValueError("Incomplete recipe")
    return {"schema_version": 1, "preparation": preparation, "ingredients": ingredients}
