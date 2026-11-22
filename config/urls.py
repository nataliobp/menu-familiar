from django.urls import path
from menus.web import catalogue, operations, photos, planning, recipes, shopping, template

urlpatterns = [
    path("healthz", operations.healthz, name="healthz"),
    path("", planning.current_menu),
    path("menu/", planning.current_menu, name="current_menu"),
    path("menu/<str:week>/", planning.menu_view, name="menu_week"),
    path("menu/<str:week>/<str:action>/", planning.move_action, name="move_action"),
    path("menu/<str:week>/slots/<int:day>/<str:meal>/move/", planning.move_choice, name="move_choice"),
    path("menu/<str:week>/slots/<int:day>/<str:meal>/triar/", planning.menu_picker, name="menu_picker"),
    path("menu/<str:week>/slots/<int:day>/<str:meal>/", planning.slot_detail, name="slot_detail"),
    path("menu/<str:week>/slots/<int:day>/<str:meal>/remove/", planning.menu_confirm, {"action": "remove"}, name="confirm_remove"),
    path("menu/<str:week>/slots/<int:day>/<str:meal>/skip/", planning.menu_confirm, {"action": "skip"}, name="confirm_skip"),
    path("menu/<str:week>/slots/<int:day>/<str:meal>/<str:action>/", planning.menu_action, name="menu_action"),
    path("compra/", shopping.current_shopping, name="current_shopping"),
    path("compra/<str:week>/", shopping.shopping_view, name="shopping_week"),
    path("plats/", catalogue.catalogue, name="catalogue"),
    path("plats/new/", catalogue.dish_edit, name="dish_create"),
    path("plats/<int:dish_id>/", catalogue.dish_detail, name="dish_detail"),
    path("plats/<int:dish_id>/edit/", catalogue.dish_edit, name="dish_edit"),
    path("plats/<int:dish_id>/recepta/foto/", photos.recipe_photo, name="recipe_photo"),
    path("plats/<int:dish_id>/recepta/", recipes.recipe_view, name="recipe_view"),
    path("plats/<int:dish_id>/recepta/edit/", recipes.recipe_editor, name="recipe_edit"),
    path("plats/<int:dish_id>/recepta/draft/", recipes.recipe_editor, {"intent": "draft"}, name="recipe_draft"),
    path("plats/<int:dish_id>/recepta/publish/", recipes.recipe_editor, {"intent": "publish"}, name="recipe_publish"),
    path("menu/<str:week>/slots/<int:day>/<str:meal>/recepta/edit/", recipes.recipe_editor, {"dish_id": None}, name="slot_recipe_edit"),
    path("menu/<str:week>/slots/<int:day>/<str:meal>/recepta/draft/", recipes.recipe_editor, {"dish_id": None, "intent": "draft"}, name="slot_recipe_draft"),
    path("menu/<str:week>/slots/<int:day>/<str:meal>/recepta/publish/", recipes.recipe_editor, {"dish_id": None, "intent": "publish"}, name="slot_recipe_publish"),
    path("plats/<int:dish_id>/<str:action>/", catalogue.dish_archive, name="dish_archive"),
    path("plantilla/", template.template_view, name="weekly_template"),
    path("plantilla/<int:day>/<str:meal>/", template.template_edit, name="template_edit"),
]

handler400 = "menus.web.errors.bad_request"
handler403 = "menus.web.errors.forbidden"
handler500 = "menus.web.errors.server_error"
