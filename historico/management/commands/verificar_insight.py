from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from historico.models import Navio
from historico.services.insight import analyze_navios


class Command(BaseCommand):
    help = "Valida o LOGGERAL Insight e informa se o modelo local já pode ser ativado."

    def handle(self, *args, **options):
        if getattr(settings, "INSIGHT_ML_ENABLED", True):
            try:
                import sklearn
            except ImportError as exc:
                raise CommandError(
                    "scikit-learn não está instalado. Execute pip install -r requirements.txt."
                ) from exc
            self.stdout.write(f"Motor local disponível (scikit-learn {sklearn.__version__}).")
        else:
            self.stdout.write(self.style.WARNING("Modelo estatístico desativado; regras explicáveis permanecem ativas."))

        analysis = analyze_navios(Navio.objects.order_by("pk"))
        model = analysis["modelo"]
        self.stdout.write(
            f"LOGGERAL Insight: {analysis['resumo']['total']} registro(s); "
            f"estado do modelo: {model['status']}."
        )
        self.stdout.write(model["mensagem"])
        self.stdout.write(self.style.SUCCESS("Validação do LOGGERAL Insight concluída."))
