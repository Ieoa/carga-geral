from django.test import TestCase
from unittest.mock import patch
from django.test import override_settings

from .models import Equipamento


class EquipamentoQrCodeTests(TestCase):
    @override_settings(PUBLIC_BASE_URL="https://app.example.com")
    def test_qrcode_uses_public_base_url_when_configured(self):
        class FakeQrCode:
            def save(self, buffer, format):
                buffer.write(b"fake-png")

        with patch("estoque.models.qrcode.make", return_value=FakeQrCode()) as make_qrcode:
            Equipamento.objects.create(
                equipamento="Cinta",
                identificador="C-001",
                tipo_equipamento="MANUAL",
                quantidade=1,
                localizacao="Armazem",
            )

        make_qrcode.assert_called_once_with("https://app.example.com/estoque/dashboard/equipamentos/detalhe_equipamento/1/")
