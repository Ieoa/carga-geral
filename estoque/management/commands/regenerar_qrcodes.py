from django.core.management.base import BaseCommand

from estoque.models import Equipamento


class Command(BaseCommand):
    help = "Regenera os QR Codes para que abram o PDF ativo dos materiais."

    def handle(self, *args, **options):
        total = 0
        for equipamento in Equipamento.objects.all().iterator():
            equipamento.gerar_qrcode(force=True)
            total += 1

        self.stdout.write(
            self.style.SUCCESS(f"{total} QR Code(s) regenerado(s) com sucesso.")
        )
