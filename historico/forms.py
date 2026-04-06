from django import forms
from .models import Navio, FotoVideoNavio, Colaborador




# Agora defina os formulários que usam MultipleFileField
class LoginForm(forms.Form):
    matricula = forms.CharField(label="Matrícula", max_length=20)
    senha = forms.CharField(label="Senha", widget=forms.PasswordInput)



class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class DocumentoNavioForm(forms.Form):
    arquivos = forms.FileField(
        widget=MultipleFileInput(attrs={'multiple': True, 'accept': 'application/pdf'}),
        required=False,
        label="Selecionar PDFs"
    )

class NavioForm(forms.ModelForm):
    class Meta:
        model = Navio
        fields = [
            "navio", "boca", "loa", "armador", "agencia", "bordo", "eta", "pob",
            "inicio_operacao", "fim_operacao", "ternos", "tempo_operacao",
            "volume_descarga", "peso_descarga", "volume_embarque", "peso_embarque",
        ]
        # Widgets para campos com tipos especiais (data, hora, etc.)
        widgets = {
            "eta": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "pob": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "inicio_operacao": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "fim_operacao": forms.DateTimeInput(attrs={"type": "datetime-local"}), # Corrigido de TimeInput para DateTimeInput
            "tempo_operacao": forms.TimeInput(attrs={"type": "time", "step": 1}),
        }

    # ✅ PASSO 1: ADICIONE ESTE MÉTODO __init__
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Campos de data/hora já têm um label visível, então não precisam de form-floating
        datetime_fields = ['eta', 'pob', 'inicio_operacao', 'fim_operacao', 'tempo_operacao']

        for field_name, field in self.fields.items():
            # Adiciona a classe 'form-control' a todos
            field.widget.attrs.update({'class': 'form-control'})

            # Para campos que NÃO são de data/hora, adiciona um placeholder para o form-floating funcionar
            if field_name not in datetime_fields:
                field.widget.attrs.update({'placeholder': field.label})

# O seu FotoVideoNavioForm está bom, mas vamos garantir a classe para consistência
class FotoVideoNavioForm(forms.ModelForm):
    class Meta:
        model = FotoVideoNavio
        fields = ["arquivo", "observacao", "tipo_peca"]
        widgets = {
            "arquivo": forms.FileInput(attrs={'class': 'form-control'}),
            "observacao": forms.Textarea(attrs={"rows": 2, 'class': 'form-control', 'placeholder': 'Observações'}),
            "tipo_peca": forms.TextInput(attrs={"placeholder": "Ex: Foto do navio, Vídeo da operação", 'class': 'form-control'})
        }
        
        
class ColaboradorForm(forms.ModelForm):
    class Meta:
        model = Colaborador
        fields = ["nome", "sobrenome", "matricula", "cpf", "email", "cargo"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "sobrenome": forms.TextInput(attrs={"class": "form-control"}),
            "matricula": forms.TextInput(attrs={"class": "form-control"}),
            "cpf": forms.TextInput(attrs={
                "class": "form-control cpf-mask",  # Usaremos esta classe para o JS
                "placeholder": "000.000.000-00",
            }),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "exemplo@email.com"}),
            "cargo": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_matricula(self):
        matricula = self.cleaned_data.get('matricula')
        # Exclui o próprio objeto da verificação ao editar (útil para formulários de atualização)
        if self.instance and self.instance.pk:
            if Colaborador.objects.filter(matricula=matricula).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("Esta matrícula já está em uso.")
        elif Colaborador.objects.filter(matricula=matricula).exists():
            raise forms.ValidationError("Esta matrícula já está em uso.")
        return matricula

    def clean_cpf(self):
        cpf = self.cleaned_data.get('cpf')
        # Lógica similar para edição
        if self.instance and self.instance.pk:
            if Colaborador.objects.filter(cpf=cpf).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("Este CPF já está cadastrado.")
        elif Colaborador.objects.filter(cpf=cpf).exists():
            raise forms.ValidationError("Este CPF já está cadastrado.")
        return cpf