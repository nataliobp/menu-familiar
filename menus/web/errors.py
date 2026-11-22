from django.shortcuts import render


def bad_request(request, exception):
    return render(request, "menus/http_error.html", {"heading": "La sol·licitud no és vàlida"}, status=400)


def forbidden(request, exception=None):
    return render(request, "menus/http_error.html", {"heading": "No es pot accedir a aquesta pàgina"}, status=403)


def csrf_failure(request, reason=""):
    return render(request, "menus/http_error.html", {
        "heading": "No s’ha pogut confirmar la sol·licitud",
        "detail": "Torna a obrir el formulari i torna-ho a provar.",
    }, status=403)


def server_error(request):
    return render(request, "menus/http_error.html", {
        "heading": "S’ha produït un error", "detail": "Torna-ho a provar més tard.",
    }, status=500)
