"""Apply the owner-approved private content through the existing dish and recipe use cases."""

from dataclasses import dataclass, replace

from menus.application.dishes import update_dish
from menus.application.planning import Rollover
from menus.application.recipes import save_recipe
from menus.domain.dish_edit import DishInput
from menus.domain.planning import monday


@dataclass(frozen=True)
class Proposal:
    source_id: int
    original_name: str
    approved_name: str
    content: dict


@dataclass(frozen=True)
class ImportTarget:
    dish_id: int
    dish: DishInput
    version: int
    linked: bool
    catalogue_edited: bool
    rename_applied: bool
    photo_digest: str
    draft: dict | None
    published: dict | None


@dataclass(frozen=True)
class ImportOutcome:
    source_id: int
    recipe: str
    rename: str = "none"
    photo: str = "pending"


def import_proposals(repo, clock, proposals, legacy_catalogue, photos, dry_run, store_photo):
    outcomes = []
    with repo.atomic():
        current_week = monday(clock.today())
        for proposal in proposals:
            source_id = proposal.source_id
            target = repo.resolve_source(source_id, legacy_catalogue.get(source_id))
            if isinstance(target, str):
                outcomes.append(ImportOutcome(source_id, target, "blocked", "blocked"))
                continue
            dish_id, dish, version = target.dish_id, target.dish, target.version
            renamed = target.rename_applied
            expected = proposal.approved_name if renamed else proposal.original_name
            if dish.name != expected:
                outcomes.append(ImportOutcome(source_id, "name_conflict", "blocked", "blocked"))
                continue
            rename = not renamed and proposal.approved_name != proposal.original_name
            if rename and target.catalogue_edited:
                outcomes.append(ImportOutcome(source_id, "identity_conflict", "blocked", "blocked"))
                continue
            if target.draft is not None:
                recipe = "preserved_draft"
            elif target.published is None:
                recipe = "imported"
            else:
                recipe = "unchanged" if target.published == proposal.content else "preserved_published"
            photo = "pending"
            if source_id in photos:
                photo = "unchanged" if target.photo_digest == photos[source_id] else "linked"
            if not dry_run:
                if not target.linked:
                    repo.adopt_source(source_id, dish_id, version)
                if rename:
                    update_dish(repo, clock, dish_id, replace(dish, name=proposal.approved_name), version)
                    version += 1
                    repo.mark_rename(source_id)
                if recipe == "imported":
                    save_recipe(repo, clock, dish_id, version, proposal.content, publish=True)
                    version += 1
                if source_id in photos:
                    store_photo(source_id)
                    if photo == "linked":
                        repo.link_photo(source_id, dish_id, version, photos[source_id])
            outcomes.append(ImportOutcome(source_id, recipe, "renamed" if rename else "none", photo))
        if not dry_run and monday(clock.today()) != current_week:
            raise Rollover()
    return outcomes
