from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health_check(request):
    """Health probe for the intranet service without exposing configuration data."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            database_ok = cursor.fetchone() == (1,)
    except Exception:
        database_ok = False

    status = 200 if database_ok else 503
    response = JsonResponse(
        {
            "status": "ok" if database_ok else "unavailable",
            "database": "ok" if database_ok else "unavailable",
        },
        status=status,
    )
    response["Cache-Control"] = "no-store"
    return response
