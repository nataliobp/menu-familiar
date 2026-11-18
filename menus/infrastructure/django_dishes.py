from django.db import IntegrityError, transaction
from menus.application.dishes import DishConflict, DuplicateReceipt
from menus.infrastructure.django_planning import DjangoPlanningRepository
from menus.models import CreationReceipt, DishRecord, SecondaryCategoryRecord, WeeklyMenuRecord


class DjangoDishRepository:
    def atomic(self):
        return transaction.atomic()

    def receipt(self, token):
        return CreationReceipt.objects.filter(pk=token).values_list("operation", "scope", "digest", "result_id").first()

    def add_receipt(self, token, operation, scope, digest, result_id):
        try:
            CreationReceipt.objects.create(token=token, operation=operation, scope=scope, digest=digest, result_id=result_id)
        except IntegrityError as exc:
            raise DuplicateReceipt() from exc

    def create_dish(self, data):
        dish = DishRecord.objects.create(name=data.name, primary_category_id=data.primary_category,
            meal_preference=data.meal_preference, special_occasion=data.special_occasion)
        SecondaryCategoryRecord.objects.bulk_create([SecondaryCategoryRecord(dish=dish, category_id=key) for key in data.secondary_categories])
        return dish.pk

    def update_dish(self, dish_id, data, version):
        dish = DishRecord.objects.filter(pk=dish_id).first()
        if dish is None:
            raise ValueError("Missing dish")
        if dish.version != version:
            raise DishConflict()
        previous = (dish.name, dish.primary_category_id, set(dish.secondary_categories.values_list("category_id", flat=True)), dish.meal_preference, dish.special_occasion)
        current = (data.name, data.primary_category, set(data.secondary_categories), data.meal_preference, data.special_occasion)
        if previous == current:
            if not DishRecord.objects.filter(pk=dish_id, version=version).update(version=version):
                raise DishConflict()
            return False
        if not DishRecord.objects.filter(pk=dish_id, version=version).update(name=data.name, primary_category_id=data.primary_category,
                meal_preference=data.meal_preference, special_occasion=data.special_occasion, version=version + 1):
            raise DishConflict()
        SecondaryCategoryRecord.objects.filter(dish_id=dish_id).delete()
        SecondaryCategoryRecord.objects.bulk_create([SecondaryCategoryRecord(dish_id=dish_id, category_id=key) for key in data.secondary_categories])
        return True

    def refresh_dish(self, dish_id, current_week):
        planning = DjangoPlanningRepository()
        snapshot = planning.dish_snapshot(dish_id, include_archived=True)
        weeks = WeeklyMenuRecord.objects.filter(week_start__gte=current_week, slots__dish_id=dish_id).order_by("week_start").distinct().values_list("week_start", flat=True)
        for week in weeks:
            menu = planning.get(week)
            positions = []
            for position, slot in menu.slots.items():
                if slot.dish and slot.dish["dish_id"] == dish_id and slot.dish != snapshot:
                    slot.dish = snapshot.copy()
                    positions.append(position)
            if positions:
                menu.refresh_undo(positions)
                planning.save(menu, menu.version)

    def set_archived(self, dish_id, version, archived):
        dish = DishRecord.objects.filter(pk=dish_id).first()
        if not dish:
            raise ValueError("Missing dish")
        if dish.version != version:
            raise DishConflict()
        next_version = version + (dish.archived != archived)
        if not DishRecord.objects.filter(pk=dish_id, version=version).update(archived=archived, version=next_version):
            raise DishConflict()

    def validate_context(self, context, dish_id, current):
        from menus.application.planning import PastWeek, PlanningConflict
        week, position = context
        if week < current:
            raise PastWeek()
        menu = DjangoPlanningRepository().get(week)
        if not menu or position not in menu.slots or not menu.slots[position].dish or menu.slots[position].dish["dish_id"] != dish_id:
            raise PlanningConflict()

    def save_recipe(self, dish_id, version, content, publish):
        from menus.models import RecipeRecord
        dish = DishRecord.objects.filter(pk=dish_id).first()
        if not dish:
            raise ValueError("Missing dish")
        if dish.version != version:
            raise DishConflict()
        recipe = RecipeRecord.objects.filter(dish_id=dish_id).first()
        draft, published = (recipe.draft, recipe.published) if recipe else (None, None)
        old_effective = ("published", published) if published is not None else ("draft", draft) if draft is not None else ("missing", None)
        new_draft, new_published = (None, content) if publish else (content, published)
        changed = (draft, published) != (new_draft, new_published)
        if not DishRecord.objects.filter(pk=dish_id, version=version).update(version=version + int(changed)):
            raise DishConflict()
        if changed:
            RecipeRecord.objects.update_or_create(dish_id=dish_id, defaults={"draft": new_draft, "published": new_published})
        new_effective = ("published", new_published) if new_published is not None else ("draft", new_draft)
        return old_effective != new_effective
