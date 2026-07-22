from django.contrib import messages
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from django.utils import timezone

from ..models import UserAccess


class RequiredPasswordChangeView(PasswordChangeView):
    template_name = 'historico/alterar_senha.html'
    success_url = reverse_lazy('dashboard')

    def form_valid(self, form):
        response = super().form_valid(form)
        UserAccess.objects.update_or_create(
            user=self.request.user,
            defaults={
                'must_change_password': False,
                'password_changed_at': timezone.now(),
            },
        )
        messages.success(self.request, 'Senha alterada com sucesso.')
        return response
