from django.db import DatabaseError
from django.shortcuts import render
from menus.application.errors import DataIntegrityError


class DataIntegrityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, (DataIntegrityError, DatabaseError)):
            return render(request, "503.html", status=503)
        return None
