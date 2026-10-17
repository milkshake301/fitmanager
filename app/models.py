from decimal import Decimal

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


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
    nome = models.CharField(max_length=120)
    especialidade = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    telefone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.nome


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
        ]
    )
    data_inicio = models.DateField()
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
        from django.utils import timezone
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
