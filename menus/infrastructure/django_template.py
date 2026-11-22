from django.db import transaction
from menus.application.template import TemplateConflict
from menus.application.errors import DataIntegrityError
from menus.domain.template import WeeklyTemplate
from menus.domain.categories import CATEGORIES, canonical_category_name
from menus.models import CategoryRecord, TemplateSlotRecord, WeeklyTemplateRecord


class DjangoTemplateRepository:
    def atomic(self):
        return transaction.atomic()

    def categories(self):
        categories = dict(CategoryRecord.objects.order_by("name_ca").values_list("key", "name_ca"))
        if "salads" in categories:
            categories["salads"] = canonical_category_name(categories["salads"])
        if categories != dict(CATEGORIES):
            raise DataIntegrityError("Invalid category vocabulary")
        return categories

    def get(self):
        try:
            record = WeeklyTemplateRecord.objects.get(pk=1)
        except WeeklyTemplateRecord.DoesNotExist as exc:
            raise DataIntegrityError("Missing template") from exc
        try:
            return WeeklyTemplate(record.version, {(s.day_index, s.meal): s.suggested_category_id for s in record.slots.all()})
        except ValueError as exc:
            raise DataIntegrityError("Invalid template") from exc

    def guard(self, expected_version):
        if not WeeklyTemplateRecord.objects.filter(pk=1, version=expected_version).update(version=expected_version):
            raise TemplateConflict()

    def save(self, template, expected_version):
        if not WeeklyTemplateRecord.objects.filter(pk=1, version=expected_version).update(version=expected_version + 1):
            raise TemplateConflict()
        for (day, meal), category in template.slots.items():
            TemplateSlotRecord.objects.filter(template_id=1, day_index=day, meal=meal).update(suggested_category_id=category)
        template.version += 1
