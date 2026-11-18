import csv
from pathlib import Path

from menus.domain.catalogue import CatalogueDish
from menus.domain.categories import CATEGORY_KEYS_BY_NAME


class InvalidCatalogue(ValueError):
    pass


def read_catalogue(path: Path) -> list[CatalogueDish]:
    required = {"id", "name_ca", "primary_category", "secondary_categories", "meal_preference", "special_occasion", "recipe_status", "image_status"}
    dishes = []
    ids = set()

    def invalid(row, field, code):
        raise InvalidCatalogue(f"row={row} field={field} code={code}")

    try:
        with path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source, strict=True)
            headers = reader.fieldnames
            if not headers or len(headers) != len(set(headers)) or set(headers) != required:
                invalid(1, "headers", "invalid")
            for row in reader:
                number = reader.line_num
                if None in row or any(value is None for value in row.values()):
                    invalid(number, "row", "width")
                raw_id = row["id"]
                if not raw_id.isascii() or not raw_id.isdigit() or len(raw_id.lstrip("0")) > 19 or not 1 <= int(raw_id.lstrip("0") or "0") < 9223372036854775807:
                    invalid(number, "id", "invalid")
                dish_id = int(raw_id.lstrip("0") or "0")
                if dish_id in ids:
                    invalid(number, "id", "duplicate")
                ids.add(dish_id)
                if not row["name_ca"].strip() or len(row["name_ca"]) > 200:
                    invalid(number, "name_ca", "invalid")
                if row["primary_category"] not in CATEGORY_KEYS_BY_NAME:
                    invalid(number, "primary_category", "unknown")
                if row["meal_preference"] not in {"lunch", "dinner", "both"}:
                    invalid(number, "meal_preference", "invalid")
                if row["special_occasion"] not in {"true", "false"}:
                    invalid(number, "special_occasion", "invalid")
                if row["recipe_status"] != "pending":
                    invalid(number, "recipe_status", "unsupported")
                categories = [value.strip() for value in row["secondary_categories"].split(",")] if row["secondary_categories"] else []
                if (any(value not in CATEGORY_KEYS_BY_NAME for value in categories)
                        or len(categories) != len(set(categories)) or row["primary_category"] in categories):
                    invalid(number, "secondary_categories", "invalid")
                dishes.append(CatalogueDish(dish_id, row["name_ca"], row["primary_category"], frozenset(categories), row["meal_preference"], row["special_occasion"] == "true"))
    except (csv.Error, UnicodeError) as exc:
        raise InvalidCatalogue("row=unknown field=csv code=invalid") from exc
    if not dishes:
        invalid(1, "rows", "empty")
    return dishes
