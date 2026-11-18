from datetime import timedelta
from django.db import transaction
from menus.application.catalogue_queries import CategoryView, DishView, RecipeView
from menus.models import DishRecord, MenuSlotRecord, RecipeRecord


class DjangoCatalogueQueries:
    def atomic(self):
        return transaction.atomic()

    def _dish(self, record):
        recipe = getattr(record, "recipe", None)
        status = "published" if recipe and recipe.published is not None else (
            "draft" if recipe and recipe.draft is not None else "missing"
        )
        return DishView(record.pk, record.name, CategoryView(record.primary_category_id, record.primary_category.name_ca),
                        tuple(sorted(category.category_id for category in record.secondary_categories.all())),
                        record.meal_preference, record.special_occasion, record.archived, record.version, status)

    def dishes(self, archived):
        records = DishRecord.objects.filter(archived=archived).select_related("primary_category", "recipe").prefetch_related("secondary_categories").order_by("id")
        return [self._dish(record) for record in records]

    def dish(self, dish_id):
        if not 1 <= dish_id <= 9223372036854775807:
            return None
        record = DishRecord.objects.select_related("primary_category", "recipe").prefetch_related("secondary_categories").filter(pk=dish_id).first()
        return self._dish(record) if record else None

    def recipe(self, dish_id):
        record = RecipeRecord.objects.filter(dish_id=dish_id).first()
        return RecipeView(record.draft, record.published) if record else None

    def latest_dates(self):
        latest = {}
        for dish_id, week_start, day_index in MenuSlotRecord.objects.filter(dish__isnull=False).values_list("dish_id", "weekly_menu_id", "day_index"):
            occurrence = week_start + timedelta(days=day_index)
            if dish_id not in latest or occurrence > latest[dish_id]:
                latest[dish_id] = occurrence
        return latest
