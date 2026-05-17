from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import requests
from django.test import SimpleTestCase, override_settings

from .utils.scraping_praticagem_reduzido import get_navios_cargo_reduzido


class PraticagemCacheTests(SimpleTestCase):
    def test_returns_cached_navios_when_request_fails(self):
        with TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache_dir.mkdir()
            cache_file = cache_dir / "praticagem_navios.json"
            cache_file.write_text(
                '[{"data": "01/01/2026", "hora": "10:00", "navio": "NAVIO TESTE", "tipo_navio": "CARGO SHIP", "terminal": "TECONT1"}]',
                encoding="utf-8",
            )

            with override_settings(MEDIA_ROOT=temp_dir):
                with patch(
                    "historico.utils.scraping_praticagem_reduzido.requests.get",
                    side_effect=requests.RequestException,
                ):
                    navios = get_navios_cargo_reduzido()

        self.assertEqual(navios[0]["navio"], "NAVIO TESTE")
