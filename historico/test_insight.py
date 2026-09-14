from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import NavioForm
from .models import FotoVideoNavio, Navio
from .services.insight import analyze_navios, evaluate_rules, extract_features, parse_localized_number
from .uploads import validate_media_upload, validate_pdf_upload


def fake_navio(pk=1, **overrides):
    start = timezone.make_aware(datetime(2026, 4, 10, 8, 0))
    defaults = {
        "pk": pk,
        "navio": f"Navio {pk}",
        "armador": "Armador",
        "agencia": "Agência",
        "boca": "32,5",
        "loa": "220,0",
        "eta": start - timedelta(hours=3),
        "pob": start - timedelta(hours=1),
        "inicio_operacao": start,
        "fim_operacao": start + timedelta(hours=20 + pk / 10),
        "tempo_operacao": timedelta(hours=20 + pk / 10),
        "ternos": 2,
        "volume_descarga": "1000",
        "peso_descarga": str(10000 + pk * 50),
        "volume_embarque": "0",
        "peso_embarque": "0",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class InsightUnitTests(SimpleTestCase):
    def test_parse_localized_numbers_and_units(self):
        self.assertEqual(parse_localized_number("1.234,50 t"), 1234.5)
        self.assertEqual(parse_localized_number("2,500.75"), 2500.75)
        self.assertEqual(parse_localized_number("2500 kg"), 2500.0)
        self.assertIsNone(parse_localized_number("sem valor"))

    def test_extracts_duration_and_productivity(self):
        features = extract_features(fake_navio(peso_descarga="10.000", peso_embarque="2.000"))
        self.assertAlmostEqual(features["peso_total"], 12000)
        self.assertGreater(features["produtividade_peso_hora"], 0)
        self.assertEqual(features["loa"], 220)

    def test_rules_explain_invalid_timeline_and_dimensions(self):
        navio = fake_navio(
            inicio_operacao=timezone.now(),
            fim_operacao=timezone.now() - timedelta(hours=2),
            loa="20",
            boca="32",
        )
        codes = {alert["codigo"] for alert in evaluate_rules(navio)}
        self.assertIn("inicio_fim_invertidos", codes)
        self.assertIn("dimensoes_inconsistentes", codes)

    def test_eta_anticipation_is_only_flagged_when_excessive(self):
        navio = fake_navio()
        navio.pob = navio.eta - timedelta(hours=2)
        self.assertNotIn("desvio_eta_pob", {item["codigo"] for item in evaluate_rules(navio)})
        navio.pob = navio.eta - timedelta(hours=30)
        self.assertIn("desvio_eta_pob", {item["codigo"] for item in evaluate_rules(navio)})

    @override_settings(INSIGHT_ML_ENABLED=True)
    def test_robust_statistics_find_injected_outlier(self):
        navios = [fake_navio(pk=index) for index in range(1, 12)]
        navios[-1].fim_operacao = navios[-1].inicio_operacao + timedelta(hours=240)
        navios[-1].tempo_operacao = timedelta(hours=240)
        analysis = analyze_navios(navios, statistical_minimum=10, ml_minimum=100)
        result = next(item for item in analysis["resultados"] if item["navio_id"] == 11)
        self.assertEqual(analysis["modelo"]["status"], "estatistica_robusta")
        self.assertTrue(result["anomalia_modelo"])
        self.assertIn("padrao_operacional_atipico", {item["codigo"] for item in result["alertas"]})

    def test_invalid_high_severity_record_is_not_baseline_sample(self):
        navios = [fake_navio(pk=index) for index in range(1, 11)]
        invalid = fake_navio(pk=20, ternos=-1)
        analysis = analyze_navios(navios + [invalid], statistical_minimum=10, ml_minimum=100)
        self.assertEqual(analysis["modelo"]["amostras"], 10)

    def test_upload_signatures_are_checked(self):
        valid_pdf = SimpleUploadedFile("documento.pdf", b"%PDF-1.7\nconteudo", content_type="text/plain")
        validate_pdf_upload(valid_pdf)
        with self.assertRaises(ValidationError):
            validate_pdf_upload(SimpleUploadedFile("falso.pdf", b"<html>ataque</html>", content_type="application/pdf"))
        with self.assertRaises(ValidationError):
            validate_media_upload(SimpleUploadedFile("ataque.html", b"<script></script>", content_type="text/html"))

    def test_navio_form_renders_browser_formats_and_validates_timeline(self):
        instance = Navio(
            navio="Teste",
            eta=timezone.make_aware(datetime(2026, 4, 10, 8, 30)),
            tempo_operacao=timedelta(hours=30),
        )
        html = NavioForm(instance=instance).as_p()
        self.assertIn('value="2026-04-10T08:30"', html)
        self.assertIn('value="1 06:00:00"', html)
        form = NavioForm(data={
            "navio": "Teste",
            "pob": "2026-04-10T10:00",
            "inicio_operacao": "2026-04-10T09:00",
            "fim_operacao": "2026-04-10T08:00",
            "ternos": "-1",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("inicio_operacao", form.errors)
        self.assertIn("fim_operacao", form.errors)
        self.assertIn("ternos", form.errors)


class InsightViewTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user("gestor", password="SenhaForte!2026", is_staff=True)
        self.employee = User.objects.create_user("empregado", password="SenhaForte!2026")
        self.other = User.objects.create_user("outro", password="SenhaForte!2026")
        start = timezone.make_aware(datetime(2026, 4, 10, 8, 0))
        self.owned = Navio.objects.create(
            navio="Navio próprio",
            eta=start,
            pob=start + timedelta(hours=1),
            inicio_operacao=start + timedelta(hours=2),
            fim_operacao=start + timedelta(hours=12),
            ternos=2,
            peso_descarga="10000",
            criado_por=self.employee,
        )
        self.foreign = Navio.objects.create(
            navio="Navio restrito",
            eta=start,
            inicio_operacao=start + timedelta(hours=2),
            fim_operacao=start + timedelta(hours=20),
            criado_por=self.other,
        )

    def test_insight_requires_login_and_scopes_employee_records(self):
        response = self.client.get(reverse("insight_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.employee)
        response = self.client.get(reverse("insight_dashboard"))
        self.assertContains(response, "Navio próprio")
        self.assertNotContains(response, "Navio restrito")
        self.assertEqual(self.client.get(reverse("insight_navio_api", args=[self.foreign.pk])).status_code, 404)

    def test_manager_sees_all_and_internal_api_is_explainable(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("insight_dashboard"))
        self.assertContains(response, "Navio próprio")
        self.assertContains(response, "Navio restrito")
        api_response = self.client.get(reverse("insight_navio_api", args=[self.owned.pk]))
        self.assertEqual(api_response.status_code, 200)
        payload = api_response.json()
        self.assertIn("pontuacao", payload["analise"])
        self.assertIn("modelo", payload)

    def test_dashboard_escapes_chart_labels(self):
        FotoVideoNavio.objects.create(
            navio=self.owned,
            arquivo="navios/teste/midias/x.png",
            tipo_peca="</script><script>alert(1)</script>",
            criado_por=self.employee,
        )
        self.client.force_login(self.employee)
        response = self.client.get(reverse("dashboard"))
        self.assertNotContains(response, "</script><script>alert(1)</script>")
        self.assertContains(response, "\\u003C/script\\u003E")

    def test_media_is_private_and_owner_can_download(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            relative = "navios/1/midias/teste.png"
            target = Path(media_root) / relative
            target.parent.mkdir(parents=True)
            target.write_bytes(b"\x89PNG\r\n\x1a\nconteudo")
            FotoVideoNavio.objects.create(
                navio=self.owned,
                arquivo=relative,
                tipo_peca="Teste",
                criado_por=self.employee,
            )
            url = f"/media/{relative}"
            self.assertEqual(self.client.get(url).status_code, 302)
            self.client.force_login(self.other)
            self.assertEqual(self.client.get(url).status_code, 404)
            self.client.force_login(self.employee)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            response.close()
