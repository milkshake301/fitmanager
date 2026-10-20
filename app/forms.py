from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction

from .models import Aluno, ItemLista, ListaExercicios, Matricula, Professor, Treino, Turma

TIPO_ALUNO = "aluno"
TIPO_PERSONAL = "personal"


class CadastroForm(UserCreationForm):
    tipo_conta = forms.ChoiceField(
        label="Tipo de conta",
        choices=[
            (TIPO_ALUNO, "Sou aluno"),
            (TIPO_PERSONAL, "Sou personal"),
        ],
        initial=TIPO_ALUNO,
        widget=forms.RadioSelect,
    )
    email = forms.EmailField(
        label="E-mail",
        required=True,
        widget=forms.EmailInput(attrs={"placeholder": "voce@exemplo.com"}),
    )
    nome = forms.CharField(
        label="Nome completo",
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Como seus alunos vão te ver"}),
    )
    especialidade = forms.CharField(
        label="Especialidade",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ex.: Musculação, funcional"}),
    )
    cref = forms.CharField(
        label="CREF",
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Opcional"}),
    )

    # Campos que só aparecem para quem escolhe "Sou personal"
    CAMPOS_PERSONAL = ("nome", "especialidade", "cref")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("tipo_conta", "username", "email")

    def clean(self):
        dados = super().clean()
        if dados.get("tipo_conta") == TIPO_PERSONAL and not (dados.get("nome") or "").strip():
            self.add_error("nome", "Informe seu nome para criar a conta de personal.")
        return dados

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe uma conta com este e-mail.")
        if Professor.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe um personal com este e-mail.")
        return email

    @property
    def eh_personal(self):
        return self.cleaned_data.get("tipo_conta") == TIPO_PERSONAL

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        nome = (self.cleaned_data.get("nome") or "").strip()
        if nome:
            partes = nome.split(" ", 1)
            user.first_name = partes[0][:150]
            user.last_name = partes[1][:150] if len(partes) > 1 else ""

        if commit:
            with transaction.atomic():
                user.save()
                if self.eh_personal:
                    Professor.objects.create(
                        usuario=user,
                        nome=nome or user.username,
                        email=user.email,
                        especialidade=self.cleaned_data.get("especialidade", ""),
                        cref=self.cleaned_data.get("cref", ""),
                    )
                else:
                    Aluno.objects.get_or_create(usuario=user)
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


# ---------------------------------------------------------------------------
# Personal: turmas
# ---------------------------------------------------------------------------

class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = ["nome", "horario", "valor_mensalidade", "dia_vencimento", "descricao", "ativa"]
        labels = {
            "nome": "Nome da turma",
            "horario": "Dias e horário",
            "valor_mensalidade": "Mensalidade (R$)",
            "dia_vencimento": "Dia de vencimento",
            "descricao": "Descrição",
            "ativa": "Turma ativa",
        }
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: Funcional manhã"}),
            "horario": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: Seg, Qua e Sex às 7h"}),
            "valor_mensalidade": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "0.01"}),
            "dia_vencimento": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 28}),
            "descricao": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "ativa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class AdicionarAlunoForm(forms.Form):
    """Coloca um aluno (que já tem conta) em uma turma, criando a matrícula."""

    identificador = forms.CharField(
        label="Usuário ou e-mail do aluno",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: joao ou joao@email.com"}),
    )
    valor_mensalidade = forms.DecimalField(
        label="Mensalidade (R$)",
        max_digits=8,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )
    dia_vencimento = forms.IntegerField(
        label="Vencimento (dia)",
        min_value=1,
        max_value=28,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    data_inicio = forms.DateField(
        label="Início",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
    )

    def __init__(self, *args, turma, **kwargs):
        self.turma = turma
        super().__init__(*args, **kwargs)

    def clean_identificador(self):
        valor = self.cleaned_data["identificador"].strip()
        usuario = User.objects.filter(username__iexact=valor).first() or User.objects.filter(
            email__iexact=valor
        ).first()
        if usuario is None:
            raise forms.ValidationError(
                "Nenhuma conta encontrada. Peça para o aluno criar a conta como aluno primeiro."
            )

        aluno = Aluno.objects.filter(usuario=usuario).first()
        if aluno is None:
            raise forms.ValidationError("Essa conta não é de aluno.")

        if Matricula.objects.filter(aluno=aluno, turma=self.turma, ativa=True).exists():
            raise forms.ValidationError("Esse aluno já está nesta turma.")

        self.cleaned_data["aluno"] = aluno
        return valor


# ---------------------------------------------------------------------------
# Personal: listas de exercícios
# ---------------------------------------------------------------------------

class ListaExerciciosForm(forms.ModelForm):
    class Meta:
        model = ListaExercicios
        fields = ["aluno", "titulo", "objetivo", "observacoes", "ativa"]
        labels = {
            "aluno": "Aluno",
            "titulo": "Título",
            "objetivo": "Objetivo",
            "observacoes": "Observações gerais",
            "ativa": "Lista ativa",
        }
        widgets = {
            "aluno": forms.Select(attrs={"class": "form-select"}),
            "titulo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: Treino A - Superiores"}),
            "objetivo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: Hipertrofia"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "ativa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, personal, **kwargs):
        super().__init__(*args, **kwargs)
        # O personal só pode montar listas para os próprios alunos
        alunos = Aluno.objects.filter(matriculas__turma__personal=personal).distinct()
        self.fields["aluno"].queryset = alunos.select_related("usuario").order_by("usuario__username")
        self.fields["aluno"].label_from_instance = (
            lambda a: a.usuario.get_full_name() or a.usuario.username
        )
        self.fields["aluno"].empty_label = "Selecione o aluno"


class ItemListaForm(forms.ModelForm):
    class Meta:
        model = ItemLista
        fields = ["exercicio", "series", "repeticoes", "carga", "descanso", "observacao"]
        labels = {
            "exercicio": "Exercício",
            "series": "Séries",
            "repeticoes": "Repetições",
            "carga": "Carga",
            "descanso": "Descanso",
            "observacao": "Observação",
        }
        widgets = {
            "exercicio": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: Supino reto"}),
            "series": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "repeticoes": forms.TextInput(attrs={"class": "form-control", "placeholder": "12"}),
            "carga": forms.TextInput(attrs={"class": "form-control", "placeholder": "20 kg"}),
            "descanso": forms.TextInput(attrs={"class": "form-control", "placeholder": "60 s"}),
            "observacao": forms.TextInput(attrs={"class": "form-control", "placeholder": "Opcional"}),
        }


ItemListaFormSet = forms.inlineformset_factory(
    ListaExercicios,
    ItemLista,
    form=ItemListaForm,
    extra=0,
    min_num=1,
    validate_min=True,
    can_delete=True,
)
