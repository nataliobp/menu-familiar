from decimal import Decimal, InvalidOperation
import re
import unicodedata


AMOUNT = re.compile(r"^[0-9]+(?:[.,][0-9]{1,3})?$")
MAX_AMOUNT = Decimal("999999999.999")
UNITS = {"g", "kg", "ml", "l", "unit"}
MAX_PREPARATION_LENGTH = 10000
MAX_INGREDIENTS = 100
MAX_INGREDIENT_NOTE_LENGTH = 500


def normalize_label(value):
    return unicodedata.normalize("NFC", " ".join(value.split()))


def parse_amount(value, maximum=MAX_AMOUNT):
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
    if not isinstance(preparation, str):
        raise ValueError("Invalid preparation")
    if len(preparation) > MAX_PREPARATION_LENGTH or len(lines) > MAX_INGREDIENTS:
        raise ValueError("Recipe too long")
    ingredients = []
    for line in lines:
        name = normalize_label(line.get("name", ""))
        unit, quantity = line.get("unit", ""), line.get("quantity", "").strip()
        note, taste = line.get("note", ""), line.get("taste", False)
        if (not name or not isinstance(note, str) or len(note) > MAX_INGREDIENT_NOTE_LENGTH
                or unit not in UNITS | {""} or type(taste) is not bool):
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


def validate_content(content, published=False):
    if (not isinstance(content, dict) or type(content.get("schema_version")) is not int
            or content["schema_version"] != 1 or not isinstance(content.get("ingredients"), list)):
        raise ValueError("Invalid recipe schema")
    proposal = content.get("proposal")
    if "proposal" in content and (
        not published or not isinstance(proposal, dict)
        or set(proposal) != {"servings", "provenance", "prep_minutes", "cook_minutes", "notes"}
        or type(proposal["servings"]) is not int or proposal["servings"] != 2
        or proposal["provenance"] not in ("generated_draft", "user_adapted")
        or any(type(proposal[key]) is not int or not 0 <= proposal[key] <= 1440
               for key in ("prep_minutes", "cook_minutes"))
        or not isinstance(proposal["notes"], str) or len(proposal["notes"]) > 500
    ):
        raise ValueError("Invalid proposal metadata")
    try:
        lines = [{"name": item["name"], "quantity": "" if item["quantity"] is None else item["quantity"],
                  "unit": "" if item["unit"] is None else item["unit"], "note": item["note"],
                  "taste": item["taste"]} for item in content["ingredients"]]
        canonical = recipe_content(content["preparation"], lines, published)
        if proposal is not None:
            canonical["proposal"] = proposal
        if canonical != content:
            raise ValueError("Invalid persisted recipe")
    except (TypeError, KeyError, AttributeError) as exc:
        raise ValueError("Invalid persisted recipe") from exc


def effective_recipe(draft, published):
    if published is not None:
        return "published", published
    if draft is not None:
        return "draft", draft
    return "missing", None


def recipe_transition(published, content, publish):
    return (None, content) if publish else (content, published)
