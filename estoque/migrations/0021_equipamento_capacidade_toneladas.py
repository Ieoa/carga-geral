from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("estoque", "0020_movimentacaomaterial_data_prevista_devolucao_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="equipamento",
            name="capacidade_toneladas",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                validators=[MinValueValidator(Decimal("0.01"))],
                verbose_name="Capacidade em toneladas",
            ),
        ),
    ]
