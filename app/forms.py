from django import forms

from .models import Treino


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