from datetime import datetime
from zoneinfo import ZoneInfo
from django.db import IntegrityError, transaction
from menus.application.planning import DuplicateWeek, PlanningConflict
from menus.application.errors import DataIntegrityError
from menus.domain.planning import Slot, WeeklyMenu, validate_snapshot
from menus.infrastructure.django_template import DjangoTemplateRepository
from menus.models import DishRecord, MenuSlotRecord, WeeklyMenuRecord, RecipeRecord


class MadridClock:
    def today(self):
        return datetime.now(ZoneInfo("Europe/Madrid")).date()


class DjangoPlanningRepository:
    def atomic(self):
        return transaction.atomic()

    def template(self):
        repo = DjangoTemplateRepository()
        return repo.get(), repo.categories()

    def get(self, week):
        try:
            return self._get(week)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise DataIntegrityError("Invalid stored menu") from exc

    def _get(self, week):
        root = WeeklyMenuRecord.objects.filter(pk=week).first()
        if root is None:
            return None
        if root.shopping_projection_version != 1:
            raise ValueError("Unsupported shopping projection")
        slots = {}
        for row in root.slots.all():
            suggestion = (row.suggested_category_key, row.suggested_category_name) if row.suggested_category_key else None
            if row.dish_snapshot is not None:
                validate_snapshot(row.dish_snapshot, row.dish_id)
            slots[(row.day_index, row.meal)] = Slot(suggestion, row.state, row.dish_snapshot)
        return WeeklyMenu(root.week_start, root.version, slots, root.undo_payload)

    def create(self, menu):
        try:
            root = WeeklyMenuRecord.objects.create(week_start=menu.week)
        except IntegrityError as exc:
            raise DuplicateWeek() from exc
        MenuSlotRecord.objects.bulk_create([MenuSlotRecord(weekly_menu=root, day_index=day, meal=meal,
            suggested_category_key=slot.suggestion[0] if slot.suggestion else None,
            suggested_category_name=slot.suggestion[1] if slot.suggestion else None,
            state=slot.state) for (day, meal), slot in menu.slots.items()])

    def guard(self, week, expected_version):
        if not WeeklyMenuRecord.objects.filter(pk=week, version=expected_version).update(version=expected_version):
            raise PlanningConflict()

    def save(self, menu, expected_version):
        if not WeeklyMenuRecord.objects.filter(pk=menu.week, version=expected_version).update(version=expected_version + 1, undo_payload=menu.undo):
            raise PlanningConflict()
        for (day, meal), slot in menu.slots.items():
            MenuSlotRecord.objects.filter(weekly_menu_id=menu.week, day_index=day, meal=meal).update(
                state=slot.state, dish_id=slot.dish["dish_id"] if slot.dish else None, dish_snapshot=slot.dish)
        menu.version += 1
        from menus.infrastructure.django_shopping import reconcile
        reconcile(menu)

    def dish_snapshot(self, dish_id, include_archived=False):
        query = DishRecord.objects.select_related("primary_category").filter(pk=dish_id)
        if not include_archived:
            query = query.filter(archived=False)
        dish = query.first()
        if dish is None:
            return None
        recipe = RecipeRecord.objects.filter(dish_id=dish_id).first()
        effective = (recipe.published or recipe.draft) if recipe else None
        status = "published" if recipe and recipe.published is not None else "draft" if recipe and recipe.draft is not None else "missing"
        snapshot = {"schema_version": 1, "dish_id": dish.pk, "name": dish.name,
                "primary_category": {"key": dish.primary_category_id, "name": dish.primary_category.name_ca},
                "secondary_categories": [{"key": key, "name": name} for key, name in dish.secondary_categories.order_by("category_id").values_list("category_id", "category__name_ca")],
                "meal_preference": dish.meal_preference, "special_occasion": dish.special_occasion,
                "recipe_status": status, "recipe_content": effective}
        try:
            validate_snapshot(snapshot, dish.pk)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise DataIntegrityError("Invalid stored dish") from exc
        return snapshot
