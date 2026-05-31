from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from ..models import AuditLog
from ..permissions import is_manager


@login_required
def auditoria(request):
    base_logs = AuditLog.objects.select_related("user")
    if not is_manager(request.user):
        base_logs = base_logs.filter(user=request.user)

    logs = base_logs
    action = request.GET.get("acao", "").strip()
    model_name = request.GET.get("modelo", "").strip()
    if action:
        logs = logs.filter(action=action)
    if model_name:
        logs = logs.filter(model_name=model_name)

    paginator = Paginator(logs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "historico/auditoria.html",
        {
            "page_obj": page_obj,
            "acao": action,
            "modelo": model_name,
            "modelos": base_logs.order_by("model_name")
            .values_list("model_name", flat=True)
            .distinct(),
            "acoes": AuditLog.ACTION_CHOICES,
        },
    )
