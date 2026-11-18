from decimal import Decimal
from menus.domain.shopping import aggregate
from menus.models import ShoppingStateRecord
from menus.application.shopping import ShoppingConflict
from menus.application.shopping_views import ManualItemView, OverlayView, ShoppingStateView
from menus.application.errors import DataIntegrityError


def reconcile(menu):
    state = ShoppingStateRecord.objects.filter(pk=menu.week).first()
    if state is None:
        return
    DjangoShoppingRepository().read(menu.week)
    rows, _, _ = aggregate(menu.slots)
    generated = {row["key"]: row for row in rows}
    changed = False
    for overlay in state.overlays.all():
        row = generated.get((overlay.ingredient_key, overlay.family))
        if row is None:
            if overlay.adjusted_quantity is None:
                overlay.delete()
                changed = True
            elif overlay.checked:
                overlay.checked = False
                overlay.save(update_fields=["checked"])
                changed = True
        else:
            base = format(row["quantity"], ".3f") if row["quantity"] is not None else None
            if (overlay.last_name, overlay.last_base_quantity) != (row["name"], base):
                overlay.last_name, overlay.last_base_quantity = row["name"], base
                overlay.save(update_fields=["last_name", "last_base_quantity"])
                changed = True
    if changed:
        state.version += 1
        state.save(update_fields=["version"])


class DjangoShoppingRepository:
    def atomic(self):
        from django.db import transaction
        return transaction.atomic()

    def read(self, week):
        try:
            return self._read(week)
        except (ValueError, KeyError, TypeError, AttributeError, ArithmeticError) as exc:
            raise DataIntegrityError("Invalid stored shopping data") from exc

    def _read(self, week):
        from menus.infrastructure.django_planning import DjangoPlanningRepository
        menu = DjangoPlanningRepository().get(week)
        if menu is None:
            return None
        rows, pending, incomplete = aggregate(menu.slots)
        state = ShoppingStateRecord.objects.filter(pk=week).first()
        if state:
            from menus.domain.recipe import normalize_label, parse_amount
            from menus.domain.shopping import manual_item
            if state.version < 1:
                raise ValueError("Invalid shopping version")
            for item in state.manual_items.all():
                expected = manual_item(item.name, item.quantity or "", item.unit or "")
                if expected != (item.name, item.quantity, item.unit):
                    raise ValueError("Invalid manual item")
            saved = list(state.overlays.all())
            for overlay in saved:
                if (not overlay.ingredient_key or overlay.family not in {"g", "ml", "unit", "taste"}
                        or not overlay.last_name or normalize_label(overlay.last_name) != overlay.last_name):
                    raise ValueError("Invalid shopping overlay")
                for amount in (overlay.last_base_quantity, overlay.adjusted_quantity):
                    if amount is not None and parse_amount(amount, Decimal("1399999999998600.000")) != amount:
                        raise ValueError("Invalid overlay quantity")
                if overlay.family == "taste" and (overlay.last_base_quantity is not None or overlay.adjusted_quantity is not None):
                    raise ValueError("Invalid taste overlay")
        else:
            saved = []
        overlays = {(o.ingredient_key, o.family): OverlayView(o.ingredient_key, o.family, o.last_name, o.last_base_quantity, o.adjusted_quantity, o.checked) for o in saved}
        for row in rows:
            row["overlay"] = overlays.pop(row["key"], None)
        state_view = ShoppingStateView(state.version, tuple(ManualItemView(item.pk, item.name, item.quantity, item.unit, item.checked) for item in state.manual_items.order_by("id"))) if state else None
        return menu, state_view, rows, pending, incomplete, list(overlays.values())

    def get_receipt(self, token):
        from menus.models import CreationReceipt

        return CreationReceipt.objects.filter(pk=token).values_list(
            "operation", "scope", "digest", "result_id"
        ).first()

    def mutate(self, week, menu_version, overlay_version, action, data):
        from menus.models import WeeklyMenuRecord, GeneratedOverlayRecord, ManualShoppingItemRecord
        from menus.domain.shopping import ORDER, desired_check, overlay_transition
        view = self.read(week)
        if view is None:
            raise ValueError("Missing menu")
        menu, state_view, rows, _, _, orphans = view
        if menu.version != menu_version or (state_view.version if state_view else 0) != overlay_version:
            raise ShoppingConflict()
        state = ShoppingStateRecord.objects.filter(pk=week).first()
        if not WeeklyMenuRecord.objects.filter(pk=week, version=menu_version).update(version=menu_version):
            raise ShoppingConflict()
        if state is None:
            state = ShoppingStateRecord.objects.create(week_id=week, version=1)
            created = True
        else:
            if not ShoppingStateRecord.objects.filter(pk=week, version=overlay_version).update(version=overlay_version):
                raise ShoppingConflict()
            created = False
        changed = False
        result = None
        if action == "manual_add":
            name, quantity, unit = data["values"]
            item = ManualShoppingItemRecord.objects.create(shopping=state, name=name, quantity=quantity, unit=unit)
            from menus.models import CreationReceipt
            token, digest = data["receipt_token"], data["digest"]
            from django.db import IntegrityError
            from menus.application.dishes import DuplicateReceipt
            try:
                CreationReceipt.objects.create(token=token, operation="manual_add", scope=week.isoformat(), digest=digest, result_id=item.pk)
            except IntegrityError as exc:
                raise DuplicateReceipt() from exc
            changed = True
            result = item.pk
        elif action in ("manual_edit", "manual_remove", "manual_check"):
            item = state.manual_items.filter(pk=data.get("id")).first()
            if not item:
                raise ValueError("Missing item")
            if action == "manual_remove":
                item.delete()
                changed = True
            elif action == "manual_edit":
                values = data["values"]
                changed = (item.name, item.quantity, item.unit) != values
                if changed:
                    item.name, item.quantity, item.unit = values
                    item.save(update_fields=["name", "quantity", "unit"])
            else:
                checked = desired_check(data)
                changed = item.checked != checked
                if changed:
                    item.checked = checked
                    item.save(update_fields=["checked"])
        elif action in ("adjust", "reset", "check"):
            key = (data.get("key"), data.get("family"))
            row = next((row for row in rows if row["key"] == key), None)
            overlay = state.overlays.filter(ingredient_key=key[0], family=key[1]).first()
            if not key[0] or key[1] not in ORDER or (row is None and overlay is None):
                raise ValueError("Invalid generated item")
            previous = (overlay.adjusted_quantity, overlay.checked) if overlay else None
            updated = overlay_transition(action, data, row, previous)
            changed = updated != previous
            if changed and updated is None:
                overlay.delete()
            elif changed and overlay:
                overlay.adjusted_quantity, overlay.checked = updated
                overlay.save(update_fields=["adjusted_quantity", "checked"])
            elif changed:
                adjusted, checked = updated
                GeneratedOverlayRecord.objects.create(
                    shopping=state, ingredient_key=key[0], family=key[1],
                    last_name=row["name"],
                    last_base_quantity=format(row["quantity"], ".3f") if row["quantity"] is not None else None,
                    adjusted_quantity=adjusted, checked=checked,
                )
        else:
            raise ValueError("Invalid action")
        if not changed and created:
            state.delete()
        elif changed and not created:
            state.version += 1
            state.save(update_fields=["version"])
        return result
