from django.conf import settings
from django.shortcuts import redirect


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        if request.user.is_authenticated:
            if getattr(request.user, 'must_change_password', False):
                allowed_when_change = {
                    '/password-change/',
                    '/api/password-change/',
                    '/api/logout/',
                    '/api/check-auth/',
                }
                if path not in allowed_when_change:
                    if settings.STATIC_URL and path.startswith(settings.STATIC_URL):
                        return self.get_response(request)
                    if settings.MEDIA_URL and path.startswith(settings.MEDIA_URL):
                        return self.get_response(request)
                    if path.startswith('/api/'):
                        return self.get_response(request)
                    return redirect('/password-change/')
            return self.get_response(request)

        allowed_paths = {
            settings.LOGIN_URL or '/',
            '/',
            '/api/login/',
            '/api/logout/',
            '/api/check-auth/',
            '/password-reset/',
            '/password-reset/done/',
        }

        if path in allowed_paths:
            return self.get_response(request)

        if path.startswith('/reset/'):
            return self.get_response(request)
        if path.startswith('/password-reset/'):
            return self.get_response(request)
        if settings.STATIC_URL and path.startswith(settings.STATIC_URL):
            return self.get_response(request)
        if settings.MEDIA_URL and path.startswith(settings.MEDIA_URL):
            return self.get_response(request)
        if path.startswith('/api/'):
            return self.get_response(request)

        return redirect(settings.LOGIN_URL or '/')
