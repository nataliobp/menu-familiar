from django.conf import settings
from django.db import DatabaseError
from django.shortcuts import render
from django.utils.cache import add_never_cache_headers
from menus.application.errors import DataIntegrityError
from menus.web.errors import forbidden


class TailscaleProxyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        meta = request.META
        if meta.get("SERVER_PORT") != "8001":
            return self.get_response(request)

        authority = f"{settings.TAILSCALE_HOST}:8443"
        if (not settings.TAILSCALE_HOST or not settings.TAILSCALE_PROXY_IP
                or meta.get("REMOTE_ADDR") != settings.TAILSCALE_PROXY_IP
                or meta.get("HTTP_HOST") != authority
                or meta.get("HTTP_X_FORWARDED_HOST") != authority
                or meta.get("HTTP_X_FORWARDED_PROTO") != "https"
                or "HTTP_TAILSCALE_FUNNEL_REQUEST" in meta):
            return forbidden(request)

        # Gunicorn leaves forwarded scheme handling to this dedicated listener.
        # Django's standard same-origin and HTTPS Referer checks can now run.
        meta["wsgi.url_scheme"] = "https"
        response = self.get_response(request)
        for name in (settings.CSRF_COOKIE_NAME, settings.SESSION_COOKIE_NAME):
            if name in response.cookies:
                response.cookies[name]["secure"] = True
        return response


class PrivateResponseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        add_never_cache_headers(response)
        return response


class DataIntegrityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code == 405 and not response.content:
            response.content = render(request, "menus/http_error.html", {
                "heading": "Aquesta acció no està disponible",
            }).content
        return response

    def process_exception(self, request, exception):
        if isinstance(exception, (DataIntegrityError, DatabaseError)):
            return render(request, "503.html", status=503)
        return None
