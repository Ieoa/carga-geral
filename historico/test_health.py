from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse


class HealthCheckTests(TestCase):
    def test_unknown_route_uses_the_custom_404_page(self):
        response = self.client.get("/rota-inexistente/")

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Página não encontrada", status_code=404)

    def test_health_reports_mysql_connection_without_authentication(self):
        response = self.client.get(reverse("health_check"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})
        self.assertEqual(response["Cache-Control"], "no-store")

    @patch("historico.views.health.connection.cursor")
    def test_health_returns_503_without_leaking_exception_details(self, cursor):
        cursor.side_effect = DatabaseError("sensitive connection detail")

        response = self.client.get(reverse("health_check"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"status": "unavailable", "database": "unavailable"},
        )
        self.assertNotContains(
            response,
            "sensitive connection detail",
            status_code=503,
        )
