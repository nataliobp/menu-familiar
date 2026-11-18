from django.db import transaction

from menus.domain.catalogue import CatalogueDish
from menus.domain.categories import CATEGORY_KEYS_BY_NAME
from menus.models import DishRecord, SecondaryCategoryRecord


class DjangoCatalogueRepository:
    def transaction(self):
        return transaction.atomic()

    def get(self, dish_id):
        record = DishRecord.objects.filter(pk=dish_id).first()
        if record is None:
            return None
        return CatalogueDish(record.pk, record.name, record.primary_category.name_ca, frozenset(record.secondary_categories.values_list("category__name_ca", flat=True)), record.meal_preference, record.special_occasion)

    def add(self, dish):
        record = DishRecord.objects.create(id=dish.id, name=dish.name, primary_category_id=CATEGORY_KEYS_BY_NAME[dish.primary_category], meal_preference=dish.meal_preference, special_occasion=dish.special_occasion)
        SecondaryCategoryRecord.objects.bulk_create([SecondaryCategoryRecord(dish=record, category_id=CATEGORY_KEYS_BY_NAME[name]) for name in dish.secondary_categories])
