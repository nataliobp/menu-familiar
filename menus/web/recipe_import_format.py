"""JSON format and prompt for the paste-based recipe workflow."""

import json

from menus.domain.categories import CATEGORIES, pizza_membership_is_valid
from menus.domain.dish_edit import MAX_DISH_NAME_LENGTH, DishInput
from menus.domain.recipe import (
    AMOUNT, MAX_AMOUNT, MAX_INGREDIENT_NOTE_LENGTH, MAX_INGREDIENTS, MAX_PREPARATION_LENGTH,
    UNITS, parse_amount, recipe_content,
)


SERVINGS = 2
MAX_JSON_LENGTH = 200_000
CATEGORY_KEYS = dict(CATEGORIES).keys()


class RecipeImportError(ValueError):
    pass


def _object_schema(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


CATEGORY_SCHEMA = {"type": "string", "enum": list(CATEGORY_KEYS)}
INGREDIENT_SCHEMA = _object_schema({
    "name": {"type": "string", "minLength": 1},
    "quantity": {"type": ["string", "null"], "pattern": AMOUNT.pattern},
    "unit": {"enum": [*sorted(UNITS), None]},
    "taste": {"type": "boolean"},
    "note": {"type": "string", "maxLength": MAX_INGREDIENT_NOTE_LENGTH},
})
RECIPE_SCHEMA = _object_schema({
    "name": {"type": "string", "minLength": 1, "maxLength": MAX_DISH_NAME_LENGTH},
    "primary_category": CATEGORY_SCHEMA,
    "secondary_categories": {"type": "array", "items": CATEGORY_SCHEMA, "uniqueItems": True},
    "servings": {"const": SERVINGS},
    "ingredients": {"type": "array", "minItems": 1, "maxItems": MAX_INGREDIENTS, "items": INGREDIENT_SCHEMA},
    "preparation": {"type": "string", "minLength": 1, "maxLength": MAX_PREPARATION_LENGTH},
})


def import_prompt(dish=None):
    target = "Plat que vull preparar: [escriu aquí quin plat vols preparar]."
    if dish:
        identity = {
            "name": dish.name,
            "primary_category": dish.primary_category_id,
            "secondary_categories": list(dish.secondary_categories),
        }
        target = f"Fes una recepta per a aquest plat i copia aquests valors al resultat: {json.dumps(identity, ensure_ascii=False)}"
    example = {
        "name": "Truita de carbassó",
        "primary_category": "eggs",
        "secondary_categories": ["vegetables"],
        "servings": SERVINGS,
        "ingredients": [
            {"name": "Ous", "quantity": "4", "unit": "unit", "taste": False, "note": ""},
            {"name": "Carbassó", "quantity": "300", "unit": "g", "taste": False, "note": "A rodanxes fines"},
            {"name": "Oli d’oliva", "quantity": "15", "unit": "ml", "taste": False, "note": ""},
            {"name": "Sal", "quantity": None, "unit": None, "taste": True, "note": ""},
        ],
        "preparation": ("Salta el carbassó amb l’oli fins que sigui tendre.\n"
                        "Bat els ous amb la sal i incorpora-hi el carbassó.\n"
                        "Qualla la truita a la paella i gira-la per coure-la per l’altra banda."),
    }
    categories = ", ".join(f"{key} ({label})" for key, label in CATEGORIES)
    maximum = str(MAX_AMOUNT).replace(".", ",")
    schema = json.dumps(RECIPE_SCHEMA, ensure_ascii=False, indent=2)
    return (
        f"{target}\n\n"
        f"Escriu una recepta completa per a {SERVINGS} adults en català normatiu. "
        "Retorna només un objecte JSON vàlid, sense blocs Markdown ni cap text addicional. "
        "Respecta els noms de camp i els codis de categoria i d’unitat.\n\n"
        f"Categories (codi i nom): {categories}. "
        "Tria una categoria principal. Omet-la de les secundàries i evita els duplicats. "
        "Si el plat és una pizza, posa «pizza» com a categoria principal i deixa buida la llista de secundàries. "
        "El codi «pizza» es reserva per a la categoria principal.\n"
        f"Per a una quantitat mesurada, posa «taste» a false, una quantitat positiva de fins a {maximum} "
        "com a cadena de text (amb un punt o una coma i fins a tres decimals) i una unitat del camp «unit» "
        "diferent de null. Si és al gust, posa «taste» a true i «quantity» i «unit» a null. "
        "Deixa «note» com a cadena buida si no cal cap nota. Escriu la preparació amb un pas per línia "
        "dins de la cadena JSON, separant els passos amb \\n. "
        f"El JSON ha de tenir com a màxim {MAX_JSON_LENGTH} caràcters.\n\n"
        f"Esquema JSON:\n{schema}\n\n"
        f"Exemple complet:\n{json.dumps(example, ensure_ascii=False, indent=2)}"
    )


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            label = key.encode("utf-8", errors="replace").decode("utf-8")
            raise RecipeImportError(f"El camp «{label}» apareix més d’una vegada. Deixa’n una sola còpia.")
        result[key] = value
    return result


def _check_fields(value, schema, location):
    if not isinstance(value, dict):
        raise RecipeImportError(f"{location} ha de ser un objecte JSON.")
    expected = set(schema["required"])
    missing, extra = expected - value.keys(), value.keys() - expected
    if missing:
        raise RecipeImportError(f"{location}. Afegeix els camps obligatoris: {', '.join(sorted(missing))}.")
    if extra:
        raise RecipeImportError(f"{location}. Elimina els camps no admesos: {', '.join(sorted(extra))}.")


def _dish(data):
    name = data["name"]
    if not isinstance(name, str) or not name.strip() or len(name) > MAX_DISH_NAME_LENGTH:
        raise RecipeImportError(f"Escriu a «name» un nom de plat d’entre 1 i {MAX_DISH_NAME_LENGTH} caràcters.")
    primary, secondary = data["primary_category"], data["secondary_categories"]
    if not isinstance(primary, str) or primary not in CATEGORY_KEYS:
        raise RecipeImportError("Tria a «primary_category» un codi de categoria de la llista de la instrucció.")
    if not isinstance(secondary, list) or any(not isinstance(key, str) or key not in CATEGORY_KEYS for key in secondary):
        raise RecipeImportError("Escriu a «secondary_categories» una llista de codis de categoria vàlids.")
    if not pizza_membership_is_valid(primary, secondary):
        raise RecipeImportError("La categoria Pizza només pot ser la principal i no admet categories secundàries.")
    if primary in secondary or len(secondary) != len(set(secondary)):
        raise RecipeImportError("Treu de «secondary_categories» la categoria principal i els codis duplicats.")
    return DishInput(name, primary, frozenset(secondary), "both", False)


def _ingredient(line, index):
    location = f"Ingredient {index}"
    _check_fields(line, INGREDIENT_SCHEMA, location)
    if not isinstance(line["name"], str) or not line["name"].strip():
        raise RecipeImportError(f"{location}. Escriu un nom a «name».")
    if not isinstance(line["note"], str) or len(line["note"]) > MAX_INGREDIENT_NOTE_LENGTH:
        raise RecipeImportError(f"{location}. Escriu a «note» un text de fins a {MAX_INGREDIENT_NOTE_LENGTH} caràcters.")
    taste, quantity, unit = line["taste"], line["quantity"], line["unit"]
    if type(taste) is not bool:
        raise RecipeImportError(f"{location}. Posa true o false a «taste».")
    if taste:
        if quantity is not None or unit is not None:
            raise RecipeImportError(f"{location}. Si és al gust, posa null a «quantity» i «unit».")
    else:
        try:
            if not isinstance(quantity, str):
                raise ValueError()
            parse_amount(quantity)
        except ValueError as exc:
            raise RecipeImportError(
                f"{location}. Escriu a «quantity» una quantitat positiva entre cometes, amb fins a tres decimals "
                f"i un màxim de {str(MAX_AMOUNT).replace('.', ',')}."
            ) from exc
        if not isinstance(unit, str) or unit not in UNITS:
            raise RecipeImportError(f"{location}. Tria a «unit» un d’aquests codis: {', '.join(sorted(UNITS))}.")
    return {**line, "quantity": quantity or "", "unit": unit or ""}


def parse_recipe_import(raw):
    if len(raw) > MAX_JSON_LENGTH:
        raise RecipeImportError(f"El JSON supera els {MAX_JSON_LENGTH} caràcters. Escurça’l i torna-ho a provar.")
    try:
        # JSON escapes can decode to lone surrogates that SQLite and HTML cannot encode.
        data = json.loads(raw, object_pairs_hook=_unique_object)
        json.dumps(data, ensure_ascii=False).encode("utf-8")
    except RecipeImportError:
        raise
    except json.JSONDecodeError as exc:
        raise RecipeImportError(
            f"El JSON no és vàlid (línia {exc.lineno}, columna {exc.colno}). Enganxa només l’objecte JSON, sense blocs Markdown."
        ) from exc
    except (ValueError, RecursionError) as exc:
        raise RecipeImportError("El JSON conté valors que no es poden llegir. Torna’l a generar seguint l’exemple.") from exc
    _check_fields(data, RECIPE_SCHEMA, "La recepta")
    dish = _dish(data)
    if type(data["servings"]) is not int or data["servings"] != SERVINGS:
        raise RecipeImportError(f"Posa el nombre {SERVINGS} a «servings».")
    preparation, ingredients = data["preparation"], data["ingredients"]
    if not isinstance(preparation, str) or not preparation.strip() or len(preparation) > MAX_PREPARATION_LENGTH:
        raise RecipeImportError(f"Escriu a «preparation» la preparació completa, amb fins a {MAX_PREPARATION_LENGTH} caràcters.")
    if not isinstance(ingredients, list) or not 0 < len(ingredients) <= MAX_INGREDIENTS:
        raise RecipeImportError(f"Escriu a «ingredients» una llista d’entre 1 i {MAX_INGREDIENTS} ingredients.")
    lines = [_ingredient(line, index) for index, line in enumerate(ingredients, 1)]
    return dish, recipe_content(preparation, lines, publish=True)
