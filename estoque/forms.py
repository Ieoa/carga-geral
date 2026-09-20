import re

from django import forms
from django.contrib.auth.models import User

from historico.uploads import validate_image_upload, validate_pdf_upload

from .models import Certificacao, Colaborador, Equipamento


class ColaboradorForm(forms.ModelForm):
    class Meta:
        model = Colaborador
        fields = ["matricula", "nome", "area", "cargo"]
        widgets = {
            "nome": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Digite o nome completo"}
            ),
            "matricula": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Número de matrícula"}
            ),
            "area": forms.Select(attrs={"class": "form-select"}),
            "cargo": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_nome(self):
        nome = self.cleaned_data.get("nome")
        return " ".join(word.capitalize() for word in nome.split())

    def clean_matricula(self):
        matricula = self.cleaned_data.get("matricula", "").strip()
        if not re.fullmatch(r"[A-Za-z0-9._-]+", matricula):
            raise forms.ValidationError("Use apenas letras, números, ponto, hífen ou sublinhado.")

        # Ignorar o user vinculado se for edição
        if self.instance and self.instance.user:
            if (
                User.objects.filter(username=matricula)
                .exclude(pk=self.instance.user.pk)
                .exists()
            ):
                raise forms.ValidationError("Esta matrícula já está em uso.")
        else:
            existing_user = User.objects.filter(username__iexact=matricula).first()
            if existing_user:
                already_linked = Colaborador.objects.filter(user=existing_user).exists()
                if existing_user.has_usable_password() or already_linked:
                    raise forms.ValidationError("Esta matrícula já está em uso.")

        if (
            Colaborador.objects.filter(matricula=matricula)
            .exclude(pk=self.instance.pk if self.instance else None)
            .exists()
        ):
            raise forms.ValidationError("Esta matrícula já está cadastrada.")

        return matricula


class EquipamentoForm(forms.ModelForm):
    class Meta:
        model = Equipamento
        fields = [
            "equipamento",
            "identificador",
            "caracteristica",
            "descricao_uso",
            "tipo_equipamento",
            "quantidade",
            "localizacao",
            "foto",
        ]
        widgets = {
            "equipamento": forms.TextInput(attrs={"class": "form-control"}),
            "identificador": forms.TextInput(attrs={"class": "form-control"}),
            "caracteristica": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "descricao_uso": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "tipo_equipamento": forms.Select(attrs={"class": "form-select"}),
            "quantidade": forms.NumberInput(attrs={"class": "form-control"}),
            "localizacao": forms.TextInput(attrs={"class": "form-control"}),
            "foto": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def clean_equipamento(self):
        return self.cleaned_data["equipamento"].upper()

    def clean_localizacao(self):
        return self.cleaned_data["localizacao"].upper()

    def clean_foto(self):
        foto = self.cleaned_data.get("foto")
        validate_image_upload(foto)
        return foto


class CertificacaoForm(forms.ModelForm):
    class Meta:
        model = Certificacao
        fields = [
            "nome_certificado",
            "data_certificacao",
            "data_vencimento",
            "empresa_certificadora",
            "codigo_certificado",
            "detalhes",
            "anexo",
            "notificar_por_email",
            "email_notificacao",
        ]
        widgets = {
            "nome_certificado": forms.TextInput(attrs={"class": "form-control"}),
            "data_certificacao": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "data_vencimento": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "empresa_certificadora": forms.TextInput(attrs={"class": "form-control"}),
            "codigo_certificado": forms.TextInput(attrs={"class": "form-control"}),
            "detalhes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "anexo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "notificar_por_email": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "email_notificacao": forms.EmailInput(attrs={"class": "form-control"}),
        }
        labels = {
            "nome_certificado": "Nome do certificado",
            "data_certificacao": "Data de emissão",
            "data_vencimento": "Data de vencimento",
            "empresa_certificadora": "Empresa certificadora",
            "codigo_certificado": "Código do certificado",
            "detalhes": "Detalhes",
            "anexo": "Documento PDF",
            "notificar_por_email": "Notificar por e-mail",
            "email_notificacao": "E-mail para notificação",
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("notificar_por_email") and not cleaned_data.get(
            "email_notificacao"
        ):
            self.add_error(
                "email_notificacao", "Informe o e-mail que receberá o aviso."
            )
        if cleaned_data.get("notificar_por_email") and not cleaned_data.get(
            "data_vencimento"
        ):
            self.add_error(
                "data_vencimento", "Informe o vencimento para ativar o aviso."
            )
        data_certificacao = cleaned_data.get("data_certificacao")
        data_vencimento = cleaned_data.get("data_vencimento")
        if (
            data_certificacao
            and data_vencimento
            and data_vencimento < data_certificacao
        ):
            self.add_error(
                "data_vencimento", "O vencimento não pode ser anterior à emissão."
            )
        return cleaned_data

    def clean_anexo(self):
        anexo = self.cleaned_data.get("anexo")
        validate_pdf_upload(anexo, limit=10 * 1024 * 1024)
        return anexo


class CertificacaoEdicaoForm(CertificacaoForm):
    pass


class CertificacaoRenovacaoForm(CertificacaoForm):
    pass
