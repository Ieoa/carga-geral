from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from historico.models import FotoVideoNavio, Navio


class ProtectedMediaRangeTests(TestCase):
    def test_authenticated_owner_can_stream_a_byte_range(self):
        owner = User.objects.create_user("range_owner", password="SenhaForte!2026")
        navio = Navio.objects.create(navio="Navio Range", criado_por=owner)
        relative_path = f"navios/{navio.pk}/midias/video.mp4"
        FotoVideoNavio.objects.create(
            navio=navio,
            arquivo=relative_path,
            criado_por=owner,
        )

        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            target = Path(media_root) / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"0123456789")
            self.client.force_login(owner)

            response = self.client.get(
                f"/media/{relative_path}",
                HTTP_RANGE="bytes=2-5",
            )

            self.assertEqual(response.status_code, 206)
            self.assertEqual(response["Content-Range"], "bytes 2-5/10")
            self.assertEqual(response["Content-Length"], "4")
            self.assertEqual(b"".join(response.streaming_content), b"2345")

    def test_invalid_range_is_rejected_without_content(self):
        owner = User.objects.create_user("range_invalid", password="SenhaForte!2026")
        navio = Navio.objects.create(navio="Navio Range Inválido", criado_por=owner)
        relative_path = f"navios/{navio.pk}/midias/video.mp4"
        FotoVideoNavio.objects.create(navio=navio, arquivo=relative_path, criado_por=owner)

        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            target = Path(media_root) / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"0123456789")
            self.client.force_login(owner)

            response = self.client.get(
                f"/media/{relative_path}",
                HTTP_RANGE="bytes=99-100",
            )

            self.assertEqual(response.status_code, 416)
            self.assertEqual(response["Content-Range"], "bytes */10")
