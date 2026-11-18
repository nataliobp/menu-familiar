from dataclasses import dataclass


@dataclass(frozen=True)
class ManualItemView:
    id: int
    name: str
    quantity: str | None
    unit: str | None
    checked: bool


@dataclass(frozen=True)
class OverlayView:
    ingredient_key: str
    family: str
    last_name: str
    last_base_quantity: str | None
    adjusted_quantity: str | None
    checked: bool


@dataclass(frozen=True)
class ShoppingStateView:
    version: int
    manual_items: tuple[ManualItemView, ...]
