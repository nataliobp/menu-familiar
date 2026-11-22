from django.db import models
from django.db.models import Q


class CategoryRecord(models.Model):
    key = models.CharField(primary_key=True, max_length=32)
    name_ca = models.CharField(max_length=60, unique=True)


class DishRecord(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200)
    primary_category = models.ForeignKey(CategoryRecord, on_delete=models.PROTECT)
    meal_preference = models.CharField(max_length=6)
    special_occasion = models.BooleanField()
    archived = models.BooleanField(default=False)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(id__gte=1), name="dish_id_positive"),
            models.CheckConstraint(condition=Q(version__gte=1), name="dish_version_positive"),
            models.CheckConstraint(condition=Q(meal_preference__in=["lunch", "dinner", "both"]), name="dish_preference_valid"),
        ]


class SecondaryCategoryRecord(models.Model):
    dish = models.ForeignKey(DishRecord, on_delete=models.CASCADE, related_name="secondary_categories")
    category = models.ForeignKey(CategoryRecord, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["dish", "category"], name="unique_dish_secondary_category")]


class WeeklyTemplateRecord(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(id=1), name="template_singleton"),
                       models.CheckConstraint(condition=Q(version__gte=1), name="template_version_positive")]


class TemplateSlotRecord(models.Model):
    template = models.ForeignKey(WeeklyTemplateRecord, on_delete=models.CASCADE, related_name="slots")
    day_index = models.PositiveSmallIntegerField()
    meal = models.CharField(max_length=6)
    suggested_category = models.ForeignKey(CategoryRecord, null=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["template", "day_index", "meal"], name="unique_template_position"),
            models.CheckConstraint(condition=Q(day_index__lte=6), name="template_day_valid"),
            models.CheckConstraint(condition=Q(meal__in=["lunch", "dinner"]), name="template_meal_valid"),
        ]


class WeeklyMenuRecord(models.Model):
    week_start = models.DateField(primary_key=True)
    version = models.PositiveBigIntegerField(default=1)
    shopping_projection_version = models.PositiveSmallIntegerField(default=1)
    undo_payload = models.JSONField(null=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(version__gte=1), name="menu_version_positive")]


class MenuSlotRecord(models.Model):
    weekly_menu = models.ForeignKey(WeeklyMenuRecord, on_delete=models.CASCADE, related_name="slots")
    day_index = models.PositiveSmallIntegerField()
    meal = models.CharField(max_length=6)
    suggested_category_key = models.CharField(max_length=32, null=True)
    suggested_category_name = models.CharField(max_length=60, null=True)
    state = models.CharField(max_length=8)
    dish = models.ForeignKey(DishRecord, null=True, on_delete=models.PROTECT)
    dish_snapshot = models.JSONField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["weekly_menu", "day_index", "meal"], name="unique_menu_position"),
            models.CheckConstraint(condition=Q(day_index__lte=6), name="menu_day_valid"),
            models.CheckConstraint(condition=Q(meal__in=["lunch", "dinner"]), name="menu_meal_valid"),
            models.CheckConstraint(condition=(Q(suggested_category_key__isnull=True, suggested_category_name__isnull=True) | Q(suggested_category_key__isnull=False, suggested_category_name__isnull=False)), name="menu_suggestion_pair"),
            models.CheckConstraint(condition=(Q(state="selected", dish__isnull=False, dish_snapshot__isnull=False) | Q(state__in=["pending", "skipped"], dish__isnull=True, dish_snapshot__isnull=True)), name="menu_slot_state_valid"),
        ]
        indexes = [models.Index(fields=["dish", "weekly_menu"], name="menu_dish_week_idx")]


class CreationReceipt(models.Model):
    token = models.UUIDField(primary_key=True)
    operation = models.CharField(max_length=32)
    scope = models.CharField(max_length=64)
    digest = models.CharField(max_length=64)
    result_id = models.PositiveBigIntegerField()


class RecipeRecord(models.Model):
    dish = models.OneToOneField(DishRecord, primary_key=True, on_delete=models.PROTECT, related_name="recipe")
    draft = models.JSONField(null=True)
    published = models.JSONField(null=True)


class ShoppingStateRecord(models.Model):
    week = models.OneToOneField(WeeklyMenuRecord, primary_key=True, on_delete=models.PROTECT, related_name="shopping")
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(version__gte=1), name="shopping_version_positive")]


class GeneratedOverlayRecord(models.Model):
    shopping = models.ForeignKey(ShoppingStateRecord, on_delete=models.CASCADE, related_name="overlays")
    ingredient_key = models.TextField()
    family = models.CharField(max_length=5)
    last_name = models.TextField()
    last_base_quantity = models.TextField(null=True)
    adjusted_quantity = models.TextField(null=True)
    checked = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["shopping", "ingredient_key", "family"], name="unique_shopping_overlay"),
            models.CheckConstraint(condition=Q(family__in=["g", "ml", "unit", "taste"]), name="overlay_family_valid"),
            models.CheckConstraint(condition=~Q(family="taste") | Q(last_base_quantity__isnull=True, adjusted_quantity__isnull=True), name="taste_overlay_unquantified"),
        ]


class ManualShoppingItemRecord(models.Model):
    shopping = models.ForeignKey(ShoppingStateRecord, on_delete=models.CASCADE, related_name="manual_items")
    name = models.CharField(max_length=120)
    quantity = models.TextField(null=True)
    unit = models.CharField(max_length=4, null=True)
    checked = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(Q(quantity__isnull=True, unit__isnull=True) | Q(quantity__isnull=False, unit__isnull=False)), name="manual_quantity_pair"),
            models.CheckConstraint(condition=Q(unit__isnull=True) | Q(unit__in=["g", "kg", "ml", "l", "unit"]), name="manual_unit_valid"),
        ]


class CatalogueSourceRecord(models.Model):
    source_id = models.PositiveBigIntegerField(primary_key=True)
    dish = models.OneToOneField(DishRecord, on_delete=models.CASCADE, related_name="catalogue_source")
    catalogue_edited = models.BooleanField(default=False)
    rename_applied = models.BooleanField(default=False)
    photo_digest = models.CharField(max_length=64, blank=True)
