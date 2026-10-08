from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .forms import DocumentoNavioForm
from .models import DocumentoNavio, Navio, UserAccess
from .uploads import validate_navio_document_upload


def valid_xlsx_bytes():
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as workbook:
        workbook.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types '
            'xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        workbook.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0"?><workbook '
            'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>',
        )
    return buffer.getvalue()


class NavioDocumentValidatorTests(SimpleTestCase):
    def test_accepts_pdf_xls_and_xlsx_signatures(self):
        uploads = (
            SimpleUploadedFile(
                "operacao.pdf",
                b"%PDF-1.7\nconteudo",
                content_type="application/pdf",
            ),
            SimpleUploadedFile(
                "operacao.xls",
                b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1conteudo",
                content_type="application/vnd.ms-excel",
            ),
            SimpleUploadedFile(
                "operacao.xlsx",
                valid_xlsx_bytes(),
                content_type=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
            ),
        )

        for upload in uploads:
            with self.subTest(filename=upload.name):
                validate_navio_document_upload(upload)
                self.assertEqual(upload.tell(), 0)

    def test_rejects_renamed_or_unsupported_documents(self):
        invalid_uploads = (
            SimpleUploadedFile("falso.xls", b"texto comum"),
            SimpleUploadedFile("falso.xlsx", b"PK\x03\x04zip incompleto"),
            SimpleUploadedFile("dados.csv", b"nome,valor"),
        )

        for upload in invalid_uploads:
            with self.subTest(filename=upload.name), self.assertRaises(ValidationError):
                validate_navio_document_upload(upload)

    def test_form_advertises_all_supported_document_types(self):
        html = DocumentoNavioForm().as_p()

        self.assertIn("application/pdf", html)
        self.assertIn(".xls", html)
        self.assertIn(".xlsx", html)


class ShipDocumentUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("operador_documentos", password="senha")
        UserAccess.objects.create(user=self.user)
        self.client.force_login(self.user)

    def test_ship_registration_saves_pdf_xls_and_xlsx(self):
        uploads = [
            SimpleUploadedFile(
                "operacao.pdf",
                b"%PDF-1.7\nconteudo",
                content_type="application/pdf",
            ),
            SimpleUploadedFile(
                "operacao.xls",
                b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1conteudo",
                content_type="application/vnd.ms-excel",
            ),
            SimpleUploadedFile(
                "operacao.xlsx",
                valid_xlsx_bytes(),
                content_type=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
            ),
        ]

        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(
                reverse("cadastrar_navio"),
                {"navio": "NAVIO COM PLANILHAS", "arquivos": uploads},
            )

            self.assertRedirects(
                response,
                reverse("cadastrar_navio") + "?sucesso=true",
            )
            navio = Navio.objects.get(navio="NAVIO COM PLANILHAS")
            documentos = list(
                DocumentoNavio.objects.filter(navio=navio).order_by("pk")
            )
            self.assertEqual(len(documentos), 3)
            self.assertEqual(
                {Path(documento.arquivo.name).suffix for documento in documentos},
                {".pdf", ".xls", ".xlsx"},
            )

    def test_ship_registration_rejects_fake_xlsx_atomically(self):
        fake_workbook = SimpleUploadedFile(
            "falso.xlsx",
            b"PK\x03\x04conteudo sem estrutura de planilha",
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

        response = self.client.post(
            reverse("cadastrar_navio"),
            {"navio": "NAVIO INVALIDO", "arquivos": fake_workbook},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "O conteúdo do documento não corresponde a um arquivo PDF, XLS ou XLSX válido.",
        )
        self.assertFalse(Navio.objects.filter(navio="NAVIO INVALIDO").exists())
