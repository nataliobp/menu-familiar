"""Read the versioned private bundle without including source values in errors."""

import json
import re
import unicodedata

from menus.application.private_recipes import Proposal
from menus.domain.categories import CATEGORY_KEYS_BY_NAME, canonical_category_name
from menus.domain.recipe import normalize_label, recipe_content, validate_content


SOURCE_IDS = set(range(1, 58))
RENAME_IDS = {7, 17}
UNITS = {"g": "g", "ml": "ml", "u": "unit"}


class InvalidBundle(ValueError):
    pass


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidBundle("duplicate JSON field")
        result[key] = value
    return result


def read_json(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except (OSError, UnicodeError, ValueError) as exc:
        raise InvalidBundle(f"invalid {path.name}") from exc


def indexed(rows, expected_ids):
    if not isinstance(rows, list):
        raise InvalidBundle("invalid record list")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or type(row.get("source_id")) is not int:
            raise InvalidBundle("invalid source ID")
        source_id = row["source_id"]
        if source_id not in expected_ids or source_id in result:
            raise InvalidBundle("unknown or duplicate source ID")
        result[source_id] = row
    if result.keys() != expected_ids:
        raise InvalidBundle("missing source IDs")
    return result


def text(value, limit, *, allow_empty=False):
    if (not isinstance(value, str) or not (allow_empty or value.strip()) or len(value) > limit
            or any(unicodedata.category(char) == "Cc" for char in value)):
        raise ValueError()
    return value.strip()


def ingredient_slug(name):
    decomposed = unicodedata.normalize("NFKD", name.casefold())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")


def category_key(label):
    return CATEGORY_KEYS_BY_NAME[canonical_category_name(label)]


def read_proposals(root, legacy_catalogue):
    bundle = read_json(root / "recipes-57.json")
    renames = read_json(root / "catalogue-renames.json")
    if (bundle.get("schema_version") != "2.3-2.4-draft-1"
            or bundle.get("type") != "private_household_recipe_proposals"
            or bundle.get("language") != "ca-ES" or bundle.get("intended_servings") != 2
            or type(renames.get("schema_version")) is not int or renames["schema_version"] != 1
            or renames.get("do_not_change_unapproved_names") is not True
            or renames.get("category_display_overrides") != [{"source_category": "Ensalades", "display_ca": "Amanides"}]):
        raise InvalidBundle("unsupported recipe or rename schema")
    if legacy_catalogue and legacy_catalogue.keys() != SOURCE_IDS:
        raise InvalidBundle("legacy catalogue source IDs do not match")
    overrides = indexed(renames.get("approved_name_overrides"), RENAME_IDS)
    proposals = [read_proposal(source_id, row, overrides.get(source_id), legacy_catalogue.get(source_id))
                 for source_id, row in sorted(indexed(bundle.get("recipes"), SOURCE_IDS).items())]
    ingredient_keys = {}
    for proposal in proposals:
        for line in proposal.content["ingredients"]:
            alias = ingredient_slug(line["name"])
            if ingredient_keys.setdefault(alias, line["key"]) != line["key"]:
                raise InvalidBundle(f"ambiguous ingredient identity for source ID {proposal.source_id}")
    return proposals


def read_proposal(source_id, row, override, legacy):
    try:
        original = text(row["expected_original_name_ca"], 200)
        approved = text(row["proposed_name_ca"], 200)
        if override:
            if original == approved or (original, approved) != (override["expected_name_ca"], override["new_name_ca"]):
                raise ValueError()
        elif original != approved:
            raise ValueError()
        primary = category_key(row["primary_category"])
        if not isinstance(row["secondary_categories"], list):
            raise ValueError()
        secondary = [category_key(name) for name in row["secondary_categories"]]
        if primary in secondary or len(secondary) != len(set(secondary)):
            raise ValueError()
        if legacy and (original != legacy.name or primary != category_key(legacy.primary_category)
                       or set(secondary) != {category_key(name) for name in legacy.secondary_categories}):
            raise ValueError()
        steps = row["preparation_steps_ca"]
        ingredients = row["ingredients"]
        if (row["review_status"] != "proposta_pendent_de_validacio" or not isinstance(steps, list) or not steps
                or not isinstance(ingredients, list) or not 1 <= len(ingredients) <= 30
                or row["image_filename"] != f"{source_id:02}.webp"):
            raise ValueError()
        lines = []
        identities = set()
        for ingredient in ingredients:
            name = normalize_label(text(ingredient["name_ca"], 200))
            key = ingredient["ingredient_key"]
            if key != ingredient_slug(name) or not key or key in identities:
                raise ValueError()
            identities.add(key)
            lines.append({"name": name, "quantity": text(ingredient["quantity"], 16), "unit": UNITS[ingredient["unit"]]})
        content = recipe_content("\n".join(text(step, 2000) for step in steps), lines, publish=True)
        content["proposal"] = {"servings": row["servings"], "provenance": row["provenance"],
                               "prep_minutes": row["prep_minutes"], "cook_minutes": row["cook_minutes"],
                               "notes": text(row.get("notes_ca", ""), 500, allow_empty=True)}
        validate_content(content, published=True)
        return Proposal(source_id, original, approved, content)
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidBundle(f"invalid recipe or catalogue data for source ID {source_id}") from exc
