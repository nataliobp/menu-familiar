from django.http import HttpResponse
from menus.application.errors import DataIntegrityError


class DataIntegrityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, DataIntegrityError):
            return HttpResponse("El servei no està disponible. Torna-ho a provar.", status=503)
        return None
