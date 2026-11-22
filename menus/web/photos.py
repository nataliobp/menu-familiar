from django.conf import settings
from django.http import FileResponse, Http404
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from menus.infrastructure.django_private_recipes import photo_reference
from menus.infrastructure.recipe_photos import PhotoStore


def recipe_photo_url(dish_id):
    reference = photo_reference(dish_id)
    if reference and PhotoStore(settings.RECIPE_PHOTO_ROOT).exists(*reference):
        return reverse("recipe_photo", args=[dish_id])
    return None


@require_safe
@never_cache
def recipe_photo(request, dish_id):
    reference = photo_reference(dish_id)
    if reference is None:
        raise Http404()
    try:
        photo = PhotoStore(settings.RECIPE_PHOTO_ROOT).open(*reference)
    except (OSError, ValueError):
        raise Http404() from None
    response = FileResponse(photo, content_type="image/webp")
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
