from decimal import Decimal

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Aluno(models.Model):
    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="perfil_aluno"
    )
    telefone = models.CharField(max_length=20, blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.usuario.username


class Professor(models.Model):
    """Personal trainer. Quem cria conta como personal ganha um Professor
    ligado ao próprio usuário (campo `usuario`)."""

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="perfil_personal",
    )
    nome = models.CharField(max_length=120)
    especialidade = models.CharField(max_length=100, blank=True)
    cref = models.CharField("CREF", max_length=30, blank=True)
    email = models.EmailField(unique=True)
    telefone = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name = "Personal"
        verbose_name_plural = "Personais"

    def __str__(self):
        return self.nome

    @property
    def alunos(self):
        """Alunos com matrícula ativa em alguma turma deste personal."""
        return Aluno.objects.filter(
            matriculas__turma__personal=self,
            matriculas__ativa=True,
        ).distinct()


class Turma(models.Model):
    personal = models.ForeignKey(
        Professor,
        on_delete=models.CASCADE,
        related_name="turmas",
    )
    nome = models.CharField(max_length=120)
    descricao = models.TextField(blank=True)
    horario = models.CharField(
        max_length=120,
        blank=True,
        help_text="Ex.: Seg, Qua e Sex às 7h",
    )
    valor_mensalidade = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("99.90"),
        help_text="Valor padrão para quem entra na turma",
    )
    dia_vencimento = models.PositiveSmallIntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(28)],
        help_text="Dia do mês do vencimento (1 a 28)",
    )
    ativa = models.BooleanField(default=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ativa", "nome"]

    def __str__(self):
        return self.nome

    @property
    def matriculas_ativas(self):
        return self.matriculas.filter(ativa=True).select_related("aluno__usuario")


class Treino(models.Model):
    nome = models.CharField(max_length=120)
    objetivo = models.CharField(max_length=200)
    duracao = models.PositiveIntegerField(
        help_text="Duração aproximada em minutos"
    )
    nivel = models.CharField(
        max_length=30,
        choices=[
            ("Iniciante", "Iniciante"),
            ("Intermediário", "Intermediário"),
            ("Avançado", "Avançado"),
        ],
        default="Iniciante",
    )
    descricao = models.TextField()
    professor = models.ForeignKey(
        Professor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="treinos"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome


class Exercicio(models.Model):
    nome = models.CharField(max_length=120)
    grupo_muscular = models.CharField(max_length=100)
    series = models.PositiveIntegerField(default=3)
    repeticoes = models.PositiveIntegerField(default=12)
    descricao = models.TextField(blank=True)
    treinos = models.ManyToManyField(
        Treino,
        related_name="exercicios",
        blank=True
    )

    def __str__(self):
        return self.nome


class Matricula(models.Model):
    aluno = models.ForeignKey(
        Aluno,
        on_delete=models.CASCADE,
        related_name="matriculas"
    )
    plano = models.CharField(
        max_length=30,
        choices=[
            ("Mensal", "Mensal"),
            ("Trimestral", "Trimestral"),
            ("Anual", "Anual"),
        ],
        default="Mensal",
    )
    turma = models.ForeignKey(
        "Turma",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="matriculas",
    )
    data_inicio = models.DateField(default=timezone.localdate)
    data_fim = models.DateField(null=True, blank=True)
    ativa = models.BooleanField(default=True)
    valor_mensalidade = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("99.90"),
        help_text="Valor cobrado a cada mês",
    )
    dia_vencimento = models.PositiveSmallIntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(28)],
        help_text="Dia do mês do vencimento (1 a 28)",
    )

    def __str__(self):
        return f"{self.aluno} - {self.plano}"


class Mensalidade(models.Model):
    STATUS_CHOICES = [
        ("Pendente", "Pendente"),
        ("Paga", "Paga"),
        ("Cancelada", "Cancelada"),
    ]

    matricula = models.ForeignKey(
        Matricula,
        on_delete=models.CASCADE,
        related_name="mensalidades"
    )
    competencia = models.DateField(
        help_text="Mês de referência (use o dia 1)"
    )
    valor = models.DecimalField(max_digits=8, decimal_places=2)
    vencimento = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Pendente",
    )
    data_pagamento = models.DateField(null=True, blank=True)
    mp_payment_id = models.CharField(
        "ID do pagamento (Mercado Pago)",
        max_length=40,
        blank=True,
    )

    class Meta:
        ordering = ["-competencia"]
        unique_together = [("matricula", "competencia")]

    def __str__(self):
        return f"{self.matricula.aluno} - {self.competencia:%m/%Y} ({self.status})"

    @property
    def em_atraso(self):
        return self.status == "Pendente" and self.vencimento < timezone.localdate()


class RegistroTreino(models.Model):
    aluno = models.ForeignKey(
        Aluno,
        on_delete=models.CASCADE,
        related_name="registros_treino"
    )
    treino = models.ForeignKey(
        Treino,
        on_delete=models.CASCADE,
        related_name="registros"
    )
    data_realizacao = models.DateTimeField(auto_now_add=True)
    duracao_real = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Duração realizada em minutos"
    )
    observacoes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.aluno} - {self.treino}"


class ListaExercicios(models.Model):
    """Lista de exercícios montada pelo personal para um aluno específico."""

    personal = models.ForeignKey(
        Professor,
        on_delete=models.CASCADE,
        related_name="listas",
    )
    aluno = models.ForeignKey(
        Aluno,
        on_delete=models.CASCADE,
        related_name="listas",
    )
    titulo = models.CharField(max_length=120)
    objetivo = models.CharField(max_length=200, blank=True)
    observacoes = models.TextField(blank=True)
    ativa = models.BooleanField(
        default=True,
        help_text="Desmarque para arquivar (o aluno deixa de ver na lista principal)",
    )
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-ativa", "-atualizada_em"]
        verbose_name = "Lista de exercícios"
        verbose_name_plural = "Listas de exercícios"

    def __str__(self):
        return f"{self.titulo} ({self.aluno})"


class ItemLista(models.Model):
    lista = models.ForeignKey(
        ListaExercicios,
        on_delete=models.CASCADE,
        related_name="itens",
    )
    ordem = models.PositiveSmallIntegerField(default=0)
    exercicio = models.CharField(max_length=120)
    series = models.PositiveSmallIntegerField(default=3)
    repeticoes = models.CharField(max_length=20, default="12", help_text="Ex.: 12 ou 8-10")
    carga = models.CharField(max_length=30, blank=True, help_text="Ex.: 20 kg")
    descanso = models.CharField(max_length=30, blank=True, help_text="Ex.: 60 s")
    observacao = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["ordem", "id"]

    def __str__(self):
        return f"{self.exercicio} {self.series}x{self.repeticoes}"