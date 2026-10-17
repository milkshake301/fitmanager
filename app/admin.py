from django.contrib import admin
from django.utils import timezone

from .models import Aluno, Matricula, Mensalidade


@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "telefone", "data_cadastro")
    search_fields = ("usuario__username", "usuario__email")


@admin.register(Matricula)
class MatriculaAdmin(admin.ModelAdmin):
    list_display = ("aluno", "plano", "valor_mensalidade", "dia_vencimento", "data_inicio", "ativa")
    list_filter = ("plano", "ativa")


@admin.register(Mensalidade)
class MensalidadeAdmin(admin.ModelAdmin):
    list_display = (
        "matricula",
        "competencia",
        "valor",
        "vencimento",
        "status",
        "data_pagamento",
        "mp_payment_id",
    )
    list_filter = ("status", "vencimento")
    search_fields = ("matricula__aluno__usuario__username", "mp_payment_id")
    readonly_fields = ("mp_payment_id",)
    actions = ["marcar_como_paga"]

    @admin.action(description="Marcar selecionadas como pagas (pagamento manual)")
    def marcar_como_paga(self, request, queryset):
        queryset.update(status="Paga", data_pagamento=timezone.localdate())
