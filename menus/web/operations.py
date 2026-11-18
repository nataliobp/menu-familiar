from django.db import DatabaseError, connection
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET"])
def healthz(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM django_migrations LIMIT 1")
            cursor.fetchone()
        return HttpResponse("OK", content_type="text/plain")
    except DatabaseError:
        return HttpResponse("No disponible", status=503, content_type="text/plain")
