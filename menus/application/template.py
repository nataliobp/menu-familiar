from typing import Protocol
from menus.domain.template import WeeklyTemplate


class TemplateConflict(Exception):
    pass


class TemplateRepository(Protocol):
    def atomic(self): ...
    def get(self) -> WeeklyTemplate: ...
    def categories(self) -> dict[str, str]: ...
    def save(self, template: WeeklyTemplate, expected_version: int) -> None: ...
    def guard(self, expected_version: int) -> None: ...


def get_template(repository: TemplateRepository):
    with repository.atomic():
        template = repository.get()
        categories = repository.categories()
        if any(key is not None and key not in categories for key in template.slots.values()):
            raise ValueError("Invalid template category")
        return template, categories


def set_template_category(repository: TemplateRepository, position, category, expected_version):
    with repository.atomic():
        template = repository.get()
        if template.version != expected_version:
            raise TemplateConflict()
        if category is not None and category not in repository.categories():
            raise ValueError("Unknown category")
        if template.set_category(position, category):
            repository.save(template, expected_version)
        else:
            repository.guard(expected_version)
        return template
