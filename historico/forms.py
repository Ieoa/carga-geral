from django import forms
from django.core.validators import RegexValidator

from .models import Navio


class LoginForm(forms.Form):
    matricula = forms.CharField(
        label="Login",
        max_length=20,
        validators=[
            RegexValidator(
                regex=r"^[A-Za-z0-9._-]+$",
                message="Informe um login válido.",
            )
        ],
    )
    senha = forms.CharField(label="Senha", widget=forms.PasswordInput)

    def clean_matricula(self):
        return self.cleaned_data["matricula"].strip()


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        if not data:
            return []
        items = data if isinstance(data, (list, tuple)) else [data]
        return [super(MultipleFileField, self).clean(item, initial) for item in items]


class DocumentoNavioForm(forms.Form):
    arquivos = MultipleFileField(
        widget=MultipleFileInput(attrs={"multiple": True, "accept": "application/pdf"}),
        required=False,
        label="Selecionar PDFs",
    )


class NavioForm(forms.ModelForm):
    class Meta:
        model = Navio
        fields = [
            "navio",
            "boca",
            "loa",
            "armador",
            "agencia",
            "bordo",
            "eta",
            "pob",
            "inicio_operacao",
            "fim_operacao",
            "ternos",
            "tempo_operacao",
            "volume_descarga",
            "peso_descarga",
            "volume_embarque",
            "peso_embarque",
        ]
        # Widgets para campos com tipos especiais (data, hora, etc.)
        widgets = {
            "eta": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            ),
            "pob": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            ),
            "inicio_operacao": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            ),
            "fim_operacao": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            ),
            "tempo_operacao": forms.TextInput(attrs={"placeholder": "Ex.: 30:00:00"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        datetime_fields = [
            "eta",
            "pob",
            "inicio_operacao",
            "fim_operacao",
            "tempo_operacao",
        ]

        for field_name, field in self.fields.items():
            field.widget.attrs.update({"class": "form-control"})
            if field_name not in datetime_fields:
                field.widget.attrs.update({"placeholder": field.label})

        self.fields["navio"].required = True
        self.fields["ternos"].min_value = 1
        for field_name in ("eta", "pob", "inicio_operacao", "fim_operacao"):
            self.fields[field_name].input_formats = [
                "%Y-%m-%dT%H:%M",
                "%Y-%m-%dT%H:%M:%S",
            ]

    def clean(self):
        cleaned_data = super().clean()
        pob = cleaned_data.get("pob")
        inicio = cleaned_data.get("inicio_operacao")
        fim = cleaned_data.get("fim_operacao")
        if pob and inicio and inicio < pob:
            self.add_error(
                "inicio_operacao", "O início da operação não pode ser anterior ao POB."
            )
        if inicio and fim and fim < inicio:
            self.add_error(
                "fim_operacao", "O término não pode ser anterior ao início da operação."
            )
        return cleaned_data

    def clean_ternos(self):
        ternos = self.cleaned_data.get("ternos")
        if ternos is not None and ternos <= 0:
            raise forms.ValidationError(
                "A quantidade de ternos deve ser maior que zero."
            )
        return ternos
