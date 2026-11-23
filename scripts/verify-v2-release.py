"""Verify the approved intake or compare a V1 backup with its staged V2 upgrade."""

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from menus.infrastructure.private_recipe_bundle import read_proposals
from menus.infrastructure.recipe_photos import MAX_PHOTO_BYTES, PhotoStore, read_photos


SOURCES = "menus_cataloguesourcerecord"
RECIPES = "menus_reciperecord"
DISHES = "menus_dishrecord"
MENUS = "menus_weeklymenurecord"
SLOTS = "menus_menuslotrecord"
MIGRATIONS = "django_migrations"
CONTENT_TYPES = "django_content_type"
PERMISSIONS = "auth_permission"
PENDING_PHOTOS = {16, 51, 52, 56, 57}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def table_names(db):
    return {name for (name,) in db.execute("SELECT name FROM sqlite_schema WHERE type = 'table'")}


def rows(db, table, key=0):
    # Only tables returned from sqlite_schema or constants are passed here.
    identifier = '"' + table.replace('"', '""') + '"'
    return {row[key]: dict(row) for row in db.execute(f"SELECT * FROM {identifier}")}


def checked_database(directory):
    db = sqlite3.connect((directory / "menu.sqlite3").absolute().as_uri() + "?mode=ro", uri=True)
    try:
        require(db.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "SQLite integrity failure.")
        require(db.execute("PRAGMA foreign_key_check").fetchone() is None, "SQLite foreign key failure.")
        db.row_factory = sqlite3.Row
        if SOURCES in table_names(db):
            store = PhotoStore(directory / "recipe-photos")
            for source in rows(db, SOURCES).values():
                source_id, digest = source["source_id"], source["photo_digest"]
                if digest:
                    with store.open(source_id, digest) as photo:
                        data = photo.read(MAX_PHOTO_BYTES + 1)
                    require(len(data) <= MAX_PHOTO_BYTES and hashlib.sha256(data).hexdigest() == digest,
                            f"Photo integrity failure for source {source_id}.")
    except BaseException:
        db.close()
        raise
    return db


def verify_fixture(directory, bundle):
    proposals = {proposal.source_id: proposal for proposal in read_proposals(bundle, {})}
    photos = read_photos(bundle)
    require(proposals.keys() - photos.keys() == PENDING_PHOTOS, "Unexpected photo coverage.")
    with closing(checked_database(directory)) as db:
        sources, recipes, dishes = (rows(db, table) for table in (SOURCES, RECIPES, DISHES))
        require(sources.keys() == proposals.keys(), "Fixture source IDs differ from the bundle.")
        require(recipes.keys() == {row["dish_id"] for row in sources.values()}, "Unexpected fixture recipes.")
        for source_id, source in sources.items():
            dish_id = source["dish_id"]
            proposal, photo = proposals[source_id], photos.get(source_id)
            require(dishes[dish_id]["name"] == proposal.approved_name, f"Name differs for source {source_id}.")
            recipe = recipes[dish_id]
            require(recipe["draft"] is None and json.loads(recipe["published"]) == proposal.content,
                    f"Recipe differs for source {source_id}.")
            require(source["photo_digest"] == (photo.digest if photo else ""), f"Photo differs for source {source_id}.")
    print(f"Approved intake verified: {len(proposals)} recipes and {len(photos)} photographs.")
    return proposals, photos


def verify_upgrade(before, after, fixture, bundle, week):
    proposals, photos = verify_fixture(fixture, bundle)
    with closing(checked_database(before)) as old, closing(checked_database(after)) as new:
        old_tables, new_tables = table_names(old), table_names(new)
        require(new_tables == old_tables | {SOURCES}, "Unexpected schema tables.")
        migrations = rows(new, MIGRATIONS)
        old_migrations = rows(old, MIGRATIONS)
        require(all(migrations.get(key) == value for key, value in old_migrations.items())
                and [(row["app"], row["name"]) for key, row in migrations.items() if key not in old_migrations]
                == ([] if SOURCES in old_tables else [("menus", "0011_catalogue_source")]),
                "Unexpected migration changes.")
        unchanged = old_tables - {
            MIGRATIONS, "sqlite_sequence", SOURCES, RECIPES, DISHES, MENUS, SLOTS,
            CONTENT_TYPES, PERMISSIONS,
        }
        for table in sorted(unchanged):
            require(rows(old, table) == rows(new, table), f"Unexpected changes in {table}.")
        verify_model_permissions(old, new, SOURCES not in old_tables)

        previous_sources = rows(old, SOURCES) if SOURCES in old_tables else {}
        sources = rows(new, SOURCES)
        require(previous_sources.keys() <= sources.keys(), "Source links were removed.")
        for source_id, source in sources.items():
            previous = previous_sources.get(source_id)
            digest = source["photo_digest"]
            if previous is None:
                require(source_id in proposals and source["dish_id"] == source_id
                        and not source["catalogue_edited"] and not source["rename_applied"],
                        f"Unexpected new identity for source {source_id}.")
            else:
                require(dict(source, photo_digest=previous["photo_digest"]) == previous
                        and (not previous["photo_digest"] or digest == previous["photo_digest"]),
                        f"Existing identity or photo changed for source {source_id}.")
            if digest and (previous is None or not previous["photo_digest"]):
                require(source_id in photos and digest == photos[source_id].digest,
                        f"Unexpected photo for source {source_id}.")

        old_recipes, new_recipes = rows(old, RECIPES), rows(new, RECIPES)
        require(old_recipes.keys() <= new_recipes.keys(), "Recipes were removed.")
        source_by_dish = {row["dish_id"]: source_id for source_id, row in sources.items()}
        added = {}
        for dish_id, recipe in new_recipes.items():
            previous = old_recipes.get(dish_id)
            if recipe == previous:
                continue
            require(previous is None or (previous["draft"] is None and previous["published"] is None),
                    f"Owner recipe changed for dish {dish_id}.")
            proposal = proposals.get(source_by_dish.get(dish_id))
            require(proposal and recipe["draft"] is None and json.loads(recipe["published"]) == proposal.content,
                    f"Unexpected imported recipe for dish {dish_id}.")
            added[dish_id] = proposal.content

        old_dishes, dishes = rows(old, DISHES), rows(new, DISHES)
        require(old_dishes.keys() == dishes.keys(), "Dish catalogue membership changed.")
        for dish_id, dish in old_dishes.items():
            require(dishes[dish_id] == dict(dish, version=dish["version"] + (dish_id in added)),
                    f"Dish fields changed for dish {dish_id}.")
        verify_menus(old, new, added, week)
    print(f"Upgrade preservation verified. Imported recipes: {len(added)}.")


def verify_model_permissions(old, new, new_model):
    additions = {}
    for table in (CONTENT_TYPES, PERMISSIONS):
        prior, current = rows(old, table), rows(new, table)
        require(all(current.get(key) == value for key, value in prior.items()),
                f"Existing rows changed in {table}.")
        additions[table] = [row for key, row in current.items() if key not in prior]
    if not new_model:
        require(not any(additions.values()), "Unexpected content types or permissions.")
        return
    content_types = additions[CONTENT_TYPES]
    require(len(content_types) == 1 and content_types[0]["app_label"] == "menus"
            and content_types[0]["model"] == "cataloguesourcerecord", "Unexpected content type.")
    expected = {f"{action}_cataloguesourcerecord" for action in ("add", "change", "delete", "view")}
    permissions = additions[PERMISSIONS]
    require(len(permissions) == len(expected) and {row["codename"] for row in permissions} == expected
            and all(row["content_type_id"] == content_types[0]["id"] for row in permissions),
            "Unexpected model permissions.")


def verify_menus(old, new, added, week):
    old_slots, slots = rows(old, SLOTS), rows(new, SLOTS)
    require(old_slots.keys() == slots.keys(), "Menu slot membership changed.")
    updated = {}
    for slot_id, prior in old_slots.items():
        target, dish_id = prior["weekly_menu_id"], prior["dish_id"]
        if target >= week and dish_id in added:
            # Publishing a previously missing recipe changes the effective snapshot only.
            snapshot = json.loads(prior["dish_snapshot"])
            expected = dict(snapshot, recipe_status="published", recipe_content=added[dish_id])
            actual = json.loads(slots[slot_id]["dish_snapshot"])
            require(actual == expected, f"Unexpected editable snapshot in slot {slot_id}.")
            prior = dict(prior, dish_snapshot=slots[slot_id]["dish_snapshot"])
            updated.setdefault(target, set()).add((prior["day_index"], prior["meal"]))
        require(slots[slot_id] == prior, f"Menu slot changed unexpectedly: {slot_id}.")

    old_menus, menus = rows(old, MENUS), rows(new, MENUS)
    require(old_menus.keys() == menus.keys(), "Menu membership changed.")
    for target, prior in old_menus.items():
        if target in updated:
            undo = json.loads(prior["undo_payload"]) if prior["undo_payload"] else None
            revision = menus[target]["version"]
            require(prior["version"] < revision <= prior["version"] + len(added),
                    f"Unexpected menu version for week {target}.")
            if undo and any(tuple(position) in updated[target] for position in undo["positions"]):
                undo = None
            elif undo:
                undo["eligible_version"] = revision
            actual_undo = menus[target]["undo_payload"]
            require((json.loads(actual_undo) if actual_undo else None) == undo,
                    f"Unexpected undo state for week {target}.")
            prior = dict(prior, undo_payload=actual_undo, version=revision)
        require(menus[target] == prior, f"Menu changed unexpectedly for week {target}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--upgrade", nargs=3, metavar=("V1_BACKUP", "STAGED_V2", "MADRID_WEEK"))
    args = parser.parse_args()
    try:
        if args.upgrade:
            before, after, week = args.upgrade
            verify_upgrade(Path(before), Path(after), args.fixture, args.bundle, week)
        else:
            verify_fixture(args.fixture, args.bundle)
    except (OSError, ValueError, sqlite3.Error, TypeError, KeyError) as exc:
        parser.exit(1, f"Verification failed: {exc}\n")


if __name__ == "__main__":
    main()
