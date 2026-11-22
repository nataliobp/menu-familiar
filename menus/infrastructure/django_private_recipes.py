from django.db.models import F

from menus.application.dishes import DishConflict
from menus.application.private_recipes import ImportTarget
from menus.domain.categories import CATEGORY_KEYS_BY_NAME
from menus.domain.dish_edit import DishInput
from menus.infrastructure.django_dishes import DjangoDishRepository
from menus.models import CatalogueSourceRecord, DishRecord


class DjangoPrivateRecipeRepository(DjangoDishRepository):
    def resolve_source(self, source_id, legacy_dish):
        source = CatalogueSourceRecord.objects.filter(pk=source_id).first()
        if source is None and legacy_dish is None:
            return "unknown_source"
        # The original CSV adapter assigned the seed ID as the PK. Only use that
        # contract for an explicitly supplied legacy seed and verify its data.
        dish_id = source.dish_id if source else legacy_dish.id
        dish = (DishRecord.objects.select_related("recipe", "catalogue_source")
                .prefetch_related("secondary_categories").filter(pk=dish_id).first())
        if dish is None:
            return "unknown_source"
        if source is None and hasattr(dish, "catalogue_source"):
            return "identity_conflict"
        data = DishInput(dish.name, dish.primary_category_id,
                         frozenset(item.category_id for item in dish.secondary_categories.all()),
                         dish.meal_preference, dish.special_occasion)
        if data.name != dish.name:
            return "name_conflict"
        if source is None:
            if dish.name != legacy_dish.name:
                return "name_conflict"
            expected = DishInput(legacy_dish.name, CATEGORY_KEYS_BY_NAME[legacy_dish.primary_category],
                                 frozenset(CATEGORY_KEYS_BY_NAME[name] for name in legacy_dish.secondary_categories),
                                 legacy_dish.meal_preference, legacy_dish.special_occasion)
            if data != expected:
                return "identity_conflict"
        recipe = getattr(dish, "recipe", None)
        return ImportTarget(dish_id, data, dish.version, source is not None,
                            bool(source and source.catalogue_edited), bool(source and source.rename_applied),
                            source.photo_digest if source else "",
                            recipe.draft if recipe else None, recipe.published if recipe else None)

    def guard_dish(self, dish_id, version):
        if not DishRecord.objects.filter(pk=dish_id, version=version).update(version=F("version")):
            raise DishConflict()

    def adopt_source(self, source_id, dish_id, version):
        self.guard_dish(dish_id, version)
        CatalogueSourceRecord.objects.create(source_id=source_id, dish_id=dish_id)

    def mark_rename(self, source_id):
        CatalogueSourceRecord.objects.filter(pk=source_id).update(rename_applied=True)

    def link_photo(self, source_id, dish_id, version, digest):
        self.guard_dish(dish_id, version)
        if not CatalogueSourceRecord.objects.filter(pk=source_id, dish_id=dish_id, photo_digest="").update(photo_digest=digest):
            raise DishConflict()


def photo_reference(dish_id):
    if not 1 <= dish_id <= 9223372036854775807:
        return None
    return (CatalogueSourceRecord.objects.filter(dish_id=dish_id).exclude(photo_digest="")
            .values_list("source_id", "photo_digest").first())
