from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Treino


class CadastroForm(UserCreationForm):
    email = forms.EmailField(
        label="E-mail",
        required=True,
        widget=forms.EmailInput(attrs={"placeholder": "voce@exemplo.com"}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe uma conta com este e-mail.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class TreinoForm(forms.ModelForm):
    class Meta:
        model = Treino
        fields = ["nome", "objetivo", "duracao", "nivel", "descricao"]
        labels = {
            "nome": "Nome do treino",
            "objetivo": "Objetivo",
            "duracao": "Duração",
            "nivel": "Nível",
            "descricao": "Descrição",
        }
        widgets = {
            "nome": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex.: Peito e tríceps"}
            ),
            "objetivo": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex.: Hipertrofia"}
            ),
            "duracao": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "placeholder": "Ex.: 50"}
            ),
            "nivel": forms.Select(attrs={"class": "form-select"}),
            "descricao": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Anote exercícios, séries, repetições e observações",
                }
            ),
        }