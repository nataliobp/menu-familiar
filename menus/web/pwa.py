from django.http import JsonResponse
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_safe


@require_safe
def manifest(request):
    icons = [
        {"src": static(f"menus/pwa/icon-{size}.png"), "sizes": f"{size}x{size}",
         "type": "image/png", "purpose": purpose}
        for size, purpose in ((192, "any"), (512, "any maskable"))
    ]
    return JsonResponse({
        "id": "/",
        "name": "Menú Familiar",
        "short_name": "Menú Familiar",
        "lang": "ca",
        "start_url": reverse("current_menu"),
        "scope": "/",
        "display": "standalone",
        "theme_color": "#286044",
        "background_color": "#f7f7ef",
        "icons": icons,
    }, content_type="application/manifest+json")
