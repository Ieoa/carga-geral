from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from historico.services.insight import _MODEL_CACHE, analyze_navios


def _operation(index, *, anomalous=False):
    eta = datetime(2026, 4, 10, 8, tzinfo=timezone.utc) + timedelta(days=index)
    pob = eta + timedelta(hours=2 + (index % 3) * 0.25)
    start = pob + timedelta(hours=1 + (index % 4) * 0.1)
    duration = 60 if anomalous else 8 + (index % 7) * 0.2
    end = start + timedelta(hours=duration)
    weight = 50000 if anomalous else 9000 + (index % 11) * 80
    return SimpleNamespace(
        pk=index + 1,
        navio=f"Navio {index + 1}",
        armador="Armador",
        agencia="Agência",
        eta=eta,
        pob=pob,
        inicio_operacao=start,
        fim_operacao=end,
        tempo_operacao=end - start,
        peso_descarga=str(weight),
        peso_embarque="0",
        volume_descarga=str(4000 + index % 9),
        volume_embarque="0",
        ternos=2 + index % 2,
        loa=str(190 + index % 8),
        boca=str(30 + (index % 5) * 0.2),
    )


@override_settings(INSIGHT_ML_ENABLED=True)
class InsightLocalModelTests(SimpleTestCase):
    def setUp(self):
        _MODEL_CACHE.clear()

    def test_isolation_forest_is_local_and_deterministic_at_100_samples(self):
        operations = [_operation(index) for index in range(104)]
        operations.append(_operation(104, anomalous=True))

        with patch("socket.create_connection", side_effect=AssertionError("network access")):
            first = analyze_navios(
                operations,
                statistical_minimum=30,
                ml_minimum=100,
                contamination=0.05,
            )
            second = analyze_navios(
                operations,
                statistical_minimum=30,
                ml_minimum=100,
                contamination=0.05,
            )

        self.assertEqual(first["modelo"]["status"], "modelo_local_ativo")
        self.assertEqual(first["modelo"]["minimo_amostras"], 100)
        self.assertEqual(first, second)
        analyzed = {item["navio_id"]: item for item in first["resultados"]}
        self.assertTrue(analyzed[105]["anomalia_modelo"])
        self.assertIn(
            "padrao_operacional_atipico",
            {alert["codigo"] for alert in analyzed[105]["alertas"]},
        )
