from django.conf import settings
from django.shortcuts import redirect


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._must_redirect(request):
            return redirect('alterar_senha')
        return self.get_response(request)

    @staticmethod
    def _must_redirect(request):
        if not request.user.is_authenticated:
            return False

        exempt_paths = {
            '/alterar-senha/',
            '/logout/',
            '/estoque/logout/',
        }
        if request.path in exempt_paths:
            return False
        if request.path.startswith(settings.STATIC_URL):
            return False

        access_control = getattr(request.user, 'access_control', None)
        return bool(access_control and access_control.must_change_password)
