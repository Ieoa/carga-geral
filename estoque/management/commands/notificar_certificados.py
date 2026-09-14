from django.core.management.base import BaseCommand

from estoque.services.certificacoes import enviar_avisos_certificados


class Command(BaseCommand):
    help = 'Envia avisos de certificados que vencem nos próximos três meses.'

    def handle(self, *args, **options):
        resultado = enviar_avisos_certificados()
        enviados = resultado['enviados']
        erros = resultado['erros']

        self.stdout.write(self.style.SUCCESS(f'{enviados} aviso(s) enviado(s).'))
        if erros:
            self.stderr.write(self.style.ERROR(f'{len(erros)} aviso(s) não puderam ser enviados.'))
            for erro in erros:
                prefixo = f"Certificado #{erro['certificado']}: " if erro['certificado'] else ""
                self.stderr.write(f"{prefixo}{erro['erro']}")
