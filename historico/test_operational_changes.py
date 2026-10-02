from datetime import datetime

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import FotoVideoNavio, Navio, UserAccess


class ShipPeriodAndDeletionTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user("operador_periodo", password="senha")
        self.other = User.objects.create_user("outro_periodo", password="senha")
        self.admin = User.objects.create_user(
            "admin_periodo", password="senha", is_staff=True
        )
        for user in (self.employee, self.other, self.admin):
            UserAccess.objects.create(user=user)
        self.january_ship = self._ship_with_media(
            "NAVIO JANEIRO", datetime(2026, 1, 12, 8), self.employee, "jan.jpg"
        )
        self.february_ship = self._ship_with_media(
            "NAVIO FEVEREIRO", datetime(2026, 2, 10, 8), self.employee, "fev.jpg"
        )
        self.client.force_login(self.employee)

    def _ship_with_media(self, name, started_at, owner, filename):
        navio = Navio.objects.create(
            navio=name,
            inicio_operacao=timezone.make_aware(started_at),
            criado_por=owner,
        )
        FotoVideoNavio.objects.create(
            navio=navio,
            arquivo=f"navios/{navio.pk}/midias/{filename}",
            tipo_peca="Carga geral",
            criado_por=owner,
        )
        return navio

    def test_search_accepts_month_name_and_year(self):
        response = self.client.get(reverse("pesquisar_midias"), {"q": "janeiro de 2026"})

        self.assertEqual(response.status_code, 200)
        names = [item["navio"] for item in response.json()["resultados"]]
        self.assertEqual(names, ["NAVIO JANEIRO"])

    def test_search_accepts_explicit_date_range(self):
        response = self.client.get(
            reverse("pesquisar_midias"),
            {"data_inicio": "2026-02-01", "data_fim": "2026-02-28"},
        )

        names = [item["navio"] for item in response.json()["resultados"]]
        self.assertEqual(names, ["NAVIO FEVEREIRO"])

    def test_ship_without_media_is_also_returned_and_can_be_edited(self):
        no_media = Navio.objects.create(
            navio="NAVIO SEM FOTO",
            inicio_operacao=timezone.make_aware(datetime(2026, 3, 4, 8)),
            criado_por=self.employee,
        )

        response = self.client.get(
            reverse("pesquisar_midias"),
            {"data_inicio": "2026-03-01", "data_fim": "2026-03-31"},
        )

        item = response.json()["resultados"][0]
        self.assertEqual(item["navio"], "NAVIO SEM FOTO")
        self.assertIsNone(item["arquivo"])
        self.assertEqual(item["edit_url"], reverse("editar_navio", args=[no_media.pk]))
        self.assertEqual(self.client.get(item["edit_url"]).status_code, 200)

    def test_only_management_can_delete_a_ship(self):
        delete_url = reverse("excluir_navio", args=[self.january_ship.pk])
        denied = self.client.post(delete_url)
        self.assertRedirects(denied, reverse("pagina_pesquisa_midias"))
        self.assertTrue(Navio.objects.filter(pk=self.january_ship.pk).exists())

        admin_client = Client()
        admin_client.force_login(self.admin)
        self.assertEqual(admin_client.get(delete_url).status_code, 200)
        allowed = admin_client.post(delete_url)
        self.assertRedirects(allowed, reverse("pagina_pesquisa_midias"))
        self.assertFalse(Navio.objects.filter(pk=self.january_ship.pk).exists())


class ResponsiveNavigationAndLoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("usuario_layout", password="senha")
        UserAccess.objects.create(user=self.user)

    def test_login_uses_login_label(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, ">Login</label>", html=False)
        self.assertNotContains(response, ">Matrícula</label>", html=False)
        self.assertContains(response, "images/favicon.svg")

    def test_ship_dashboard_displays_favicon_without_company_logo(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, "Histórico de Navios")
        self.assertNotContains(response, "images/logo.png")
        self.assertContains(response, "images/favicon.svg")

    def test_stock_dashboard_displays_ship_logo(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("estoque:dashboard"))

        self.assertContains(response, "images/ship-mark.svg")
        self.assertContains(response, 'alt="Navio"')

    def test_dashboard_has_click_outside_sidebar_control(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, 'id="sidebarBackdrop"')
        self.assertContains(response, "closeMobileSidebar")
